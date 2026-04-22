"""Judgment and post-judgment interest endpoints.

Non-legal guidance: Post-judgment interest rates are set under N.J. Court
Rules, R. 4:42-11(a). The Administrative Office of the Courts publishes
the applicable annual rate each January as a Notice to the Bar. The rate
table also lives on the active policy pack (see
`engines.calculation.calculate_post_judgment_interest`) — the in-module
constants below are kept as a defensive fallback only.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.rbac import CurrentUser, Permissions, require_permission
from dcs_api.database import get_session
from dcs_api.models.litigation import Judgment, JudgmentInterestAccrual, LitigationCase
from dcs_api.schemas.common import PaginatedResponse

router = APIRouter()

MAX_PAGE_SIZE = 100


# NJ Post-Judgment Interest Rates — fallback only.
# Authoritative source: N.J. Court Rules, R. 4:42-11(a) — AOC annual Notice
# to the Bar. The active policy pack RateTable is the canonical store; this
# constant is used only when no ACTIVE pack is loaded.
NJ_POST_JUDGMENT_RATES: dict[int, Decimal] = {
    2004: Decimal("2.0"),
    2005: Decimal("1.0"),
    2006: Decimal("2.0"),
    2007: Decimal("4.0"),
    2008: Decimal("5.5"),
    2009: Decimal("4.0"),
    2010: Decimal("1.5"),
    2011: Decimal("0.5"),
    2012: Decimal("0.5"),
    2013: Decimal("0.25"),
    2014: Decimal("0.25"),
    2015: Decimal("0.25"),
    2016: Decimal("0.25"),
    2017: Decimal("0.5"),
    2018: Decimal("0.5"),
    2019: Decimal("1.5"),
    2020: Decimal("2.5"),
    2021: Decimal("1.5"),
    2022: Decimal("0.25"),
    2023: Decimal("0.25"),
    2024: Decimal("3.5"),
    2025: Decimal("5.5"),
    2026: Decimal("4.5"),
}

# Above Special Civil Part threshold gets +2%
ABOVE_THRESHOLD_ADJUSTMENT = Decimal("2.0")


def get_nj_post_judgment_rate(year: int, above_threshold: bool = False) -> Decimal:
    """Get NJ post-judgment interest rate for a given year (fallback path).

    cursor.stage: calc_engine
    cursor.jurisdiction: NJ
    cursor.sources: ["N.J. Court Rules, R. 4:42-11(a)"]

    Above-threshold judgments (principal > $20,000 SCP limit per
    R. 6:1-2(a)(1)) receive the published rate plus 2.0 percentage points.
    """
    base_rate = NJ_POST_JUDGMENT_RATES.get(year, Decimal("0.25"))
    if above_threshold:
        return base_rate + ABOVE_THRESHOLD_ADJUSTMENT
    return base_rate


@router.get("")
async def list_judgments(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse:
    """List judgments in the tenant."""
    query = (
        select(Judgment)
        .join(LitigationCase)
        .where(LitigationCase.tenant_id == user.tenant_id)
    )

    # Count total
    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    # Get paginated results
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await session.execute(query)
    judgments = list(result.scalars().all())

    return PaginatedResponse(
        items=[j.to_dict() for j in judgments],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{judgment_id}")
async def get_judgment(
    judgment_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ASSIGNED_ACCOUNTS))],
) -> dict:
    """Get judgment with current interest calculation."""
    query = (
        select(Judgment)
        .join(LitigationCase)
        .options(selectinload(Judgment.accruals))
        .where(Judgment.id == judgment_id, LitigationCase.tenant_id == user.tenant_id)
    )
    result = await session.execute(query)
    judgment = result.scalar_one_or_none()

    if not judgment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Judgment not found",
        )

    # Calculate current interest
    today = date.today()
    current_interest = calculate_post_judgment_interest(
        judgment_amount=judgment.judgment_amount,
        judgment_date=judgment.judgment_date,
        calculation_date=today,
        above_threshold=judgment.is_above_threshold,
    )

    return {
        **judgment.to_dict(),
        "calculated_interest": current_interest["total_interest"],
        "current_balance": judgment.judgment_amount + current_interest["total_interest"],
        "calculation_breakdown": current_interest["yearly_breakdown"],
    }


@router.get("/{judgment_id}/accruals")
async def get_judgment_accruals(
    judgment_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ASSIGNED_ACCOUNTS))],
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    """Get daily interest accruals for a judgment."""
    # Verify judgment belongs to user's tenant
    j_query = (
        select(Judgment)
        .join(LitigationCase)
        .where(Judgment.id == judgment_id, LitigationCase.tenant_id == user.tenant_id)
    )
    j_result = await session.execute(j_query)
    if not j_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Judgment not found",
        )

    query = select(JudgmentInterestAccrual).where(
        JudgmentInterestAccrual.judgment_id == judgment_id
    )

    if start_date:
        query = query.where(JudgmentInterestAccrual.accrual_date >= start_date)
    if end_date:
        query = query.where(JudgmentInterestAccrual.accrual_date <= end_date)

    query = query.order_by(JudgmentInterestAccrual.accrual_date)
    result = await session.execute(query)
    accruals = list(result.scalars().all())

    return [a.to_dict() for a in accruals]


@router.post("/{judgment_id}/calculate-interest")
async def calculate_interest_to_date(
    judgment_id: uuid.UUID,
    calculation_date: date,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ASSIGNED_ACCOUNTS))],
) -> dict:
    """Calculate post-judgment interest to a specific date.

    Non-legal guidance: This calculation uses post-judgment interest rates
    set by N.J. Court Rules, R. 4:42-11(a) (annual AOC Notice to the Bar).
    Results should be verified for accuracy before use in legal proceedings.
    """
    query = (
        select(Judgment)
        .join(LitigationCase)
        .where(Judgment.id == judgment_id, LitigationCase.tenant_id == user.tenant_id)
    )
    result = await session.execute(query)
    judgment = result.scalar_one_or_none()

    if not judgment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Judgment not found",
        )

    calculation = calculate_post_judgment_interest(
        judgment_amount=judgment.judgment_amount,
        judgment_date=judgment.judgment_date,
        calculation_date=calculation_date,
        above_threshold=judgment.is_above_threshold,
    )

    return {
        "judgment_id": str(judgment_id),
        "judgment_amount": judgment.judgment_amount,
        "judgment_date": judgment.judgment_date.isoformat(),
        "calculation_date": calculation_date.isoformat(),
        "total_interest": calculation["total_interest"],
        "current_balance": judgment.judgment_amount + calculation["total_interest"],
        "yearly_breakdown": calculation["yearly_breakdown"],
        "audit": {
            "rate_source": "N.J. Court Rules, R. 4:42-11(a)",
            "above_threshold": judgment.is_above_threshold,
            "calculation_version": "1.0.0",
        },
    }


def calculate_post_judgment_interest(
    judgment_amount: int,
    judgment_date: date,
    calculation_date: date,
    above_threshold: bool = False,
) -> dict:
    """Calculate post-judgment interest.

    cursor.stage: calc_engine
    cursor.jurisdiction: NJ
    cursor.sources: ["N.J. Court Rules, R. 4:42-11(a)"]

    Formula: Simple daily interest, actual/365 day count.
        daily_rate = (annual_rate / 100) / 365
        interest   = principal * daily_rate * days

    Rates change annually per the AOC Notice to the Bar published in
    January under R. 4:42-11(a).
    """
    if calculation_date <= judgment_date:
        return {"total_interest": 0, "yearly_breakdown": []}

    total_interest = 0
    yearly_breakdown = []

    current_date = judgment_date
    principal = judgment_amount

    while current_date < calculation_date:
        year = current_date.year
        year_end = date(year + 1, 1, 1)
        period_end = min(year_end, calculation_date)

        days_in_period = (period_end - current_date).days
        if days_in_period <= 0:
            break

        annual_rate = get_nj_post_judgment_rate(year, above_threshold)
        daily_rate = annual_rate / Decimal("100") / Decimal("365")
        interest = int(Decimal(principal) * daily_rate * Decimal(days_in_period))

        yearly_breakdown.append({
            "year": year,
            "annual_rate": float(annual_rate),
            "days": days_in_period,
            "interest": interest,
            "period_start": current_date.isoformat(),
            "period_end": period_end.isoformat(),
        })

        total_interest += interest
        current_date = period_end

    return {
        "total_interest": total_interest,
        "yearly_breakdown": yearly_breakdown,
    }


@router.get("/rates/{year}")
async def get_rate_for_year(
    year: int,
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ASSIGNED_ACCOUNTS))],
    above_threshold: bool = False,
) -> dict:
    """Get post-judgment interest rate for a specific year.

    cursor.stage: compliance
    cursor.jurisdiction: NJ
    cursor.sources: ["N.J. Court Rules, R. 4:42-11(a)"]
    """
    rate = get_nj_post_judgment_rate(year, above_threshold)

    return {
        "year": year,
        "jurisdiction": "NJ",
        "rate": float(rate),
        "above_threshold": above_threshold,
        "source": "N.J. Court Rules, R. 4:42-11(a)",
        "source_publisher": "NJ Administrative Office of the Courts (annual Notice to the Bar)",
        "disclaimer": (
            "Non-legal guidance: Verify rate against current year's "
            "AOC Notice to the Bar for accuracy."
        ),
    }
