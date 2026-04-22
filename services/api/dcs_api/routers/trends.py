"""Trends / Year-over-Year analytics API routes."""
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import Account, Payment
from dcs_api.models.litigation import LitigationCase

router = APIRouter()


@router.get("/inventory")
async def inventory_trends(
    user: Annotated[CurrentUser, Depends(require_permission("performance:view"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    years: int = Query(3, ge=1, le=10),
) -> dict[str, Any]:
    results: dict[str, Any] = {"labels": [], "new_accounts": [], "closed_accounts": [], "active_accounts": []}
    from datetime import datetime, timezone
    current_year = datetime.now(timezone.utc).year
    for y in range(current_year - years + 1, current_year + 1):
        results["labels"].append(str(y))
        for month in range(1, 13):
            pass
        new_q = select(func.count()).select_from(Account).where(
            Account.tenant_id == user.tenant_id,
            extract("year", Account.created_at) == y,
        )
        new_count = (await session.execute(new_q)).scalar() or 0
        results["new_accounts"].append(new_count)
        results["closed_accounts"].append(0)
        results["active_accounts"].append(0)
    return results


@router.get("/payments")
async def payment_trends(
    user: Annotated[CurrentUser, Depends(require_permission("performance:view"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    years: int = Query(3, ge=1, le=10),
) -> dict[str, Any]:
    from datetime import datetime, timezone
    current_year = datetime.now(timezone.utc).year
    results: dict[str, Any] = {"labels": [], "total_collected": [], "payment_count": []}
    for y in range(current_year - years + 1, current_year + 1):
        results["labels"].append(str(y))
        sum_q = select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.tenant_id == user.tenant_id,
            extract("year", Payment.created_at) == y,
        )
        total = (await session.execute(sum_q)).scalar() or 0
        results["total_collected"].append(float(total))
        count_q = select(func.count()).select_from(Payment).where(
            Payment.tenant_id == user.tenant_id,
            extract("year", Payment.created_at) == y,
        )
        count = (await session.execute(count_q)).scalar() or 0
        results["payment_count"].append(count)
    return results


@router.get("/legal")
async def legal_trends(
    user: Annotated[CurrentUser, Depends(require_permission("performance:view"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    years: int = Query(3, ge=1, le=10),
) -> dict[str, Any]:
    from datetime import datetime, timezone
    current_year = datetime.now(timezone.utc).year
    results: dict[str, Any] = {"labels": [], "cases_filed": []}
    for y in range(current_year - years + 1, current_year + 1):
        results["labels"].append(str(y))
        q = select(func.count()).select_from(LitigationCase).where(
            LitigationCase.tenant_id == user.tenant_id,
            extract("year", LitigationCase.created_at) == y,
        )
        count = (await session.execute(q)).scalar() or 0
        results["cases_filed"].append(count)
    return results


@router.get("/summary")
async def trends_summary(
    user: Annotated[CurrentUser, Depends(require_permission("performance:view"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    from datetime import datetime, timezone
    current_year = datetime.now(timezone.utc).year
    prev_year = current_year - 1

    current_accounts = (await session.execute(
        select(func.count()).select_from(Account).where(
            Account.tenant_id == user.tenant_id, extract("year", Account.created_at) == current_year
        )
    )).scalar() or 0

    prev_accounts = (await session.execute(
        select(func.count()).select_from(Account).where(
            Account.tenant_id == user.tenant_id, extract("year", Account.created_at) == prev_year
        )
    )).scalar() or 0

    current_payments = float((await session.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.tenant_id == user.tenant_id, extract("year", Payment.created_at) == current_year
        )
    )).scalar() or 0)

    prev_payments = float((await session.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.tenant_id == user.tenant_id, extract("year", Payment.created_at) == prev_year
        )
    )).scalar() or 0)

    return {
        "current_year": current_year,
        "previous_year": prev_year,
        "accounts": {"current": current_accounts, "previous": prev_accounts, "change_pct": round(((current_accounts - prev_accounts) / max(prev_accounts, 1)) * 100, 1)},
        "payments": {"current": current_payments, "previous": prev_payments, "change_pct": round(((current_payments - prev_payments) / max(prev_payments, 1)) * 100, 1)},
    }
