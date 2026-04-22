"""Calculation engine endpoints.

cursor.stage: calc_engine
cursor.jurisdiction: NJ
cursor.sources: []

Non-legal guidance: All calculations include audit metadata for defensibility.
Results should be verified by qualified personnel before use.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, get_current_user
from dcs_api.database import get_session
from dcs_api.models.calculation import CalculationRequest as CalcRequestModel
from dcs_api.models.calculation import CalculationResult as CalcResultModel
from dcs_api.models.calculation import CalculationType
from dcs_api.schemas.calculation import (
    InterestCalculationRequest,
    InterestCalculationResponse,
    PaymentAllocationRequest,
    PaymentAllocationResponse,
    PostJudgmentInterestRequest,
    PostJudgmentInterestResponse,
)
from dcs_api.schemas.common import AuditMetadata

router = APIRouter()

MAX_PAGE_SIZE = 100

# Engine version for audit tracking
ENGINE_VERSION = "1.0.0"


@router.post("/simple-interest", response_model=InterestCalculationResponse)
async def calculate_simple_interest(
    request: InterestCalculationRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterestCalculationResponse:
    """Calculate simple or compound interest.

    Formulas (from 06_calculation_engine.md):
    - Simple: interest = principal * (rate/100/365) * days
    - Compound: amount = principal * (1 + r/n)^(n*years)
    """
    start_time = datetime.now(timezone.utc)

    days = (request.end_date - request.start_date).days
    if days <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after start date",
        )

    principal = Decimal(request.principal)
    rate = request.annual_rate
    steps = []

    if request.interest_type == "simple":
        # Simple daily interest
        daily_rate = rate / Decimal("100") / Decimal("365")
        interest = principal * daily_rate * Decimal(days)

        steps = [
            {
                "description": "Calculate daily rate",
                "formula": "annual_rate / 100 / 365",
                "values": f"{rate} / 100 / 365",
                "result": str(daily_rate),
            },
            {
                "description": "Calculate interest",
                "formula": "principal * daily_rate * days",
                "values": f"{principal} * {daily_rate} * {days}",
                "result": str(interest),
            },
        ]
        formula = "principal * (annual_rate / 100 / 365) * days"

    else:
        # Compound interest
        r = rate / Decimal("100")
        n_map = {
            "compound_daily": 365,
            "compound_monthly": 12,
            "compound_annually": 1,
        }
        n = n_map.get(request.interest_type, 365)
        years = Decimal(days) / Decimal("365")
        amount = principal * (1 + r / Decimal(n)) ** (Decimal(n) * years)
        interest = amount - principal

        steps = [
            {
                "description": "Calculate rate per period",
                "formula": "r / n",
                "values": f"{r} / {n}",
                "result": str(r / Decimal(n)),
            },
            {
                "description": "Calculate compound amount",
                "formula": "principal * (1 + r/n)^(n*years)",
                "values": f"{principal} * (1 + {r}/{n})^({n}*{years})",
                "result": str(amount),
            },
            {
                "description": "Calculate interest",
                "formula": "amount - principal",
                "values": f"{amount} - {principal}",
                "result": str(interest),
            },
        ]
        formula = "principal * (1 + annual_rate/100/n)^(n*years) - principal"
        daily_rate = r / Decimal(n)

    # Apply rounding rule
    if request.rounding_rule == "final_step":
        interest_cents = int(interest.quantize(Decimal("1")))
    else:
        interest_cents = int(interest)

    total_amount = request.principal + interest_cents

    # Record calculation for audit
    calc_request = CalcRequestModel(
        tenant_id=user.tenant_id,
        calculation_type=CalculationType.SIMPLE_INTEREST,
        inputs=request.model_dump(mode="json"),
        engine_version=ENGINE_VERSION,
        requested_at=start_time,
        requested_by=user.user_id,
    )
    session.add(calc_request)
    await session.flush()

    calc_result = CalcResultModel(
        tenant_id=user.tenant_id,
        request_id=calc_request.id,
        outputs={
            "interest_amount": interest_cents,
            "total_amount": total_amount,
            "daily_rate": str(daily_rate),
        },
        breakdown={"steps": steps},
        is_valid=True,
        completed_at=datetime.now(timezone.utc),
        duration_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
    )
    session.add(calc_result)

    return InterestCalculationResponse(
        principal=request.principal,
        annual_rate=rate,
        interest_type=request.interest_type,
        start_date=request.start_date,
        end_date=request.end_date,
        days=days,
        interest_amount=interest_cents,
        total_amount=total_amount,
        daily_rate=daily_rate,
        formula=formula,
        steps=steps,
        audit=AuditMetadata(
            calculation_version=ENGINE_VERSION,
        ),
    )


@router.post("/payment-allocation", response_model=PaymentAllocationResponse)
async def calculate_payment_allocation(
    request: PaymentAllocationRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> PaymentAllocationResponse:
    """Calculate payment allocation.

    Default allocation order: interest -> principal -> fees
    Configurable per tenant unless jurisdiction forbids changes.
    """
    remaining = request.payment_amount
    allocations = {}
    balances = {
        "interest": request.current_interest,
        "principal": request.current_principal,
        "fees": request.current_fees,
    }

    for target in request.allocation_order:
        if remaining <= 0:
            break
        if target not in balances:
            continue

        allocated = min(remaining, balances[target])
        allocations[target] = allocated
        balances[target] -= allocated
        remaining -= allocated

    # Remaining is overpayment
    overpayment = remaining

    return PaymentAllocationResponse(
        payment_amount=request.payment_amount,
        allocations=allocations,
        remaining_balances=balances,
        overpayment=overpayment,
        audit=AuditMetadata(
            calculation_version=ENGINE_VERSION,
        ),
    )


@router.post("/post-judgment-interest", response_model=PostJudgmentInterestResponse)
async def calculate_post_judgment_interest(
    request: PostJudgmentInterestRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> PostJudgmentInterestResponse:
    """Calculate post-judgment interest using jurisdiction-specific rates.

    cursor.stage: calc_engine
    cursor.jurisdiction: NJ
    cursor.sources: ["N.J. Court Rules, R. 4:42-11(a)"]
    """
    from dcs_api.routers.judgments import (
        calculate_post_judgment_interest as calc_interest,
        get_nj_post_judgment_rate,
    )

    # Determine if above threshold (would come from policy pack in production)
    # NJ Special Civil Part threshold is approximately $20,000
    SPECIAL_CIVIL_THRESHOLD = 2000000  # cents
    above_threshold = (
        request.is_above_threshold
        if request.is_above_threshold is not None
        else request.judgment_amount > SPECIAL_CIVIL_THRESHOLD
    )

    result = calc_interest(
        judgment_amount=request.judgment_amount,
        judgment_date=request.judgment_date,
        calculation_date=request.calculation_date,
        above_threshold=above_threshold,
    )

    return PostJudgmentInterestResponse(
        judgment_amount=request.judgment_amount,
        judgment_date=request.judgment_date,
        calculation_date=request.calculation_date,
        days_accrued=(request.calculation_date - request.judgment_date).days,
        total_interest=result["total_interest"],
        current_balance=request.judgment_amount + result["total_interest"],
        rates_applied=result["yearly_breakdown"],
        is_above_threshold=above_threshold,
        threshold_amount=SPECIAL_CIVIL_THRESHOLD,
        audit=AuditMetadata(
            calculation_version=ENGINE_VERSION,
        ),
    )


@router.get("/history")
async def get_calculation_history(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    calculation_type: CalculationType | None = None,
    account_id: uuid.UUID | None = None,
) -> dict:
    """Get calculation history for audit purposes."""
    from sqlalchemy import select

    query = select(CalcRequestModel).where(CalcRequestModel.tenant_id == user.tenant_id)

    if calculation_type:
        query = query.where(CalcRequestModel.calculation_type == calculation_type)
    if account_id:
        query = query.where(CalcRequestModel.account_id == account_id)

    query = query.order_by(CalcRequestModel.requested_at.desc())

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await session.execute(query)
    calculations = list(result.scalars().all())

    return {
        "items": [c.to_dict() for c in calculations],
        "page": page,
        "page_size": page_size,
    }
