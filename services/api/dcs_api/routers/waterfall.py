"""Payment waterfall and allocation rule endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.waterfall import CollectionPhase, PaymentWaterfall, WaterfallRule
from dcs_api.schemas.waterfall import (
    PaymentWaterfallCreate,
    PaymentWaterfallResponse,
    PaymentWaterfallUpdate,
    WaterfallRuleCreate,
    WaterfallRuleResponse,
    WaterfallRuleUpdate,
)
from dcs_api.schemas.common import PaginatedResponse

router = APIRouter()

MAX_PAGE_SIZE = 100

PERM = "waterfall:manage"


async def _get_waterfall(
    session: AsyncSession, waterfall_id: uuid.UUID, user: CurrentUser
) -> PaymentWaterfall | None:
    q = select(PaymentWaterfall).where(PaymentWaterfall.id == waterfall_id)
    if not user.is_master:
        q = q.where(PaymentWaterfall.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


@router.get("", response_model=PaginatedResponse[PaymentWaterfallResponse])
async def list_waterfalls(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[PaymentWaterfallResponse]:
    """List payment waterfalls in the tenant."""
    count_q = select(func.count()).select_from(PaymentWaterfall)
    if not user.is_master:
        count_q = count_q.where(PaymentWaterfall.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(PaymentWaterfall)
    if not user.is_master:
        q = q.where(PaymentWaterfall.tenant_id == user.tenant_id)
    q = q.order_by(PaymentWaterfall.name).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[PaymentWaterfallResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/{waterfall_id}", response_model=PaymentWaterfallResponse)
async def get_waterfall(
    waterfall_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> PaymentWaterfallResponse:
    """Get a payment waterfall by ID."""
    wf = await _get_waterfall(session, waterfall_id, user)
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waterfall not found")
    return PaymentWaterfallResponse.model_validate(wf)


@router.post("", response_model=PaymentWaterfallResponse, status_code=status.HTTP_201_CREATED)
async def create_waterfall(
    data: PaymentWaterfallCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> PaymentWaterfallResponse:
    """Create a payment waterfall."""
    wf = PaymentWaterfall(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        jurisdiction=data.jurisdiction,
        is_default=data.is_default,
        is_active=data.is_active,
        is_system=data.is_system,
        overpayment_handling=data.overpayment_handling,
        config=data.config,
    )
    session.add(wf)
    await session.flush()
    await session.refresh(wf)
    return PaymentWaterfallResponse.model_validate(wf)


@router.patch("/{waterfall_id}", response_model=PaymentWaterfallResponse)
async def update_waterfall(
    waterfall_id: uuid.UUID,
    data: PaymentWaterfallUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> PaymentWaterfallResponse:
    """Update a payment waterfall."""
    wf = await _get_waterfall(session, waterfall_id, user)
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waterfall not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(wf, k, v)
    await session.flush()
    return PaymentWaterfallResponse.model_validate(wf)


@router.get("/{waterfall_id}/rules", response_model=PaginatedResponse[WaterfallRuleResponse])
async def list_waterfall_rules(
    waterfall_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[WaterfallRuleResponse]:
    """List rules for a waterfall."""
    wf = await _get_waterfall(session, waterfall_id, user)
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waterfall not found")

    count_q = (
        select(func.count())
        .select_from(WaterfallRule)
        .where(WaterfallRule.waterfall_id == waterfall_id)
    )
    if not user.is_master:
        count_q = count_q.where(WaterfallRule.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(WaterfallRule).where(WaterfallRule.waterfall_id == waterfall_id)
    if not user.is_master:
        q = q.where(WaterfallRule.tenant_id == user.tenant_id)
    q = q.order_by(WaterfallRule.phase, WaterfallRule.priority).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[WaterfallRuleResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


async def _get_rule(
    session: AsyncSession,
    waterfall_id: uuid.UUID,
    rule_id: uuid.UUID,
    user: CurrentUser,
) -> WaterfallRule | None:
    q = select(WaterfallRule).where(
        WaterfallRule.id == rule_id,
        WaterfallRule.waterfall_id == waterfall_id,
    )
    if not user.is_master:
        q = q.where(WaterfallRule.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


@router.get("/{waterfall_id}/rules/{rule_id}", response_model=WaterfallRuleResponse)
async def get_waterfall_rule(
    waterfall_id: uuid.UUID,
    rule_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> WaterfallRuleResponse:
    """Get a single waterfall rule."""
    rule = await _get_rule(session, waterfall_id, rule_id, user)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waterfall rule not found")
    return WaterfallRuleResponse.model_validate(rule)


@router.post(
    "/{waterfall_id}/rules",
    response_model=WaterfallRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_waterfall_rule(
    waterfall_id: uuid.UUID,
    data: WaterfallRuleCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> WaterfallRuleResponse:
    """Create a rule under a waterfall."""
    wf = await _get_waterfall(session, waterfall_id, user)
    if not wf or data.waterfall_id != waterfall_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Waterfall not found or ID mismatch",
        )

    rule = WaterfallRule(
        tenant_id=wf.tenant_id,
        waterfall_id=waterfall_id,
        phase=data.phase,
        bucket=data.bucket,
        priority=data.priority,
        max_percentage=data.max_percentage,
        max_amount=data.max_amount,
        conditions=data.conditions,
    )
    session.add(rule)
    await session.flush()
    await session.refresh(rule)
    return WaterfallRuleResponse.model_validate(rule)


@router.patch("/{waterfall_id}/rules/{rule_id}", response_model=WaterfallRuleResponse)
async def update_waterfall_rule(
    waterfall_id: uuid.UUID,
    rule_id: uuid.UUID,
    data: WaterfallRuleUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> WaterfallRuleResponse:
    """Update a waterfall rule."""
    rule = await _get_rule(session, waterfall_id, rule_id, user)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waterfall rule not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    await session.flush()
    return WaterfallRuleResponse.model_validate(rule)


class WaterfallAllocationTestRequest(BaseModel):
    """Simulate allocation for a payment amount (cents)."""

    amount_cents: int = Field(..., ge=0)
    phase: CollectionPhase | None = None


class WaterfallAllocationTestResponse(BaseModel):
    """Per-bucket simulated allocations."""

    amount_cents: int
    phase_filter: CollectionPhase | None
    allocations: dict[str, int]
    remainder_cents: int


def _simulate_allocation(
    rules: list[WaterfallRule],
    amount_cents: int,
    phase: CollectionPhase | None,
) -> tuple[dict[str, int], int]:
    filtered = [r for r in rules if phase is None or r.phase == phase]
    ordered = sorted(filtered, key=lambda r: (r.phase.value, r.priority))
    remaining = amount_cents
    allocations: dict[str, int] = {}
    for rule in ordered:
        if remaining <= 0:
            break
        cap = remaining
        if rule.max_amount is not None:
            cap = min(cap, rule.max_amount)
        if rule.max_percentage is not None:
            cap = min(cap, (amount_cents * rule.max_percentage) // 100)
        alloc = max(0, min(remaining, cap))
        key = rule.bucket.value
        allocations[key] = allocations.get(key, 0) + alloc
        remaining -= alloc
    return allocations, remaining


@router.post("/{waterfall_id}/test-allocation", response_model=WaterfallAllocationTestResponse)
async def test_waterfall_allocation(
    waterfall_id: uuid.UUID,
    body: WaterfallAllocationTestRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> WaterfallAllocationTestResponse:
    """Simulate how a payment would be allocated using the waterfall's rules."""
    wf = await _get_waterfall(session, waterfall_id, user)
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waterfall not found")

    q = select(WaterfallRule).where(WaterfallRule.waterfall_id == waterfall_id)
    if not user.is_master:
        q = q.where(WaterfallRule.tenant_id == user.tenant_id)
    rules = list((await session.execute(q)).scalars().all())
    allocations, remainder = _simulate_allocation(rules, body.amount_cents, body.phase)
    return WaterfallAllocationTestResponse(
        amount_cents=body.amount_cents,
        phase_filter=body.phase,
        allocations=allocations,
        remainder_cents=remainder,
    )
