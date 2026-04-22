"""Cost entries, disbursements, and client billing endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import Account
from dcs_api.models.costs import CostBilling, CostDisbursement, CostEntry
from dcs_api.models.trust import TrustAccount
from dcs_api.schemas.costs import (
    CostBillingCreate,
    CostBillingResponse,
    CostBillingUpdate,
    CostDisbursementCreate,
    CostDisbursementResponse,
    CostDisbursementUpdate,
    CostEntryCreate,
    CostEntryResponse,
    CostEntryUpdate,
)
from dcs_api.schemas.common import PaginatedResponse

router = APIRouter()

MAX_PAGE_SIZE = 100

PERM = "costs:manage"


async def _get_cost_entry(
    session: AsyncSession, entry_id: uuid.UUID, user: CurrentUser
) -> CostEntry | None:
    q = select(CostEntry).where(CostEntry.id == entry_id)
    if not user.is_master:
        q = q.where(CostEntry.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


async def _get_trust_for_cost(
    session: AsyncSession, trust_id: uuid.UUID, user: CurrentUser
) -> TrustAccount | None:
    q = select(TrustAccount).where(TrustAccount.id == trust_id)
    if not user.is_master:
        q = q.where(TrustAccount.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


# --- Cost entries ---


@router.get("/entries", response_model=PaginatedResponse[CostEntryResponse])
async def list_cost_entries(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    account_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[CostEntryResponse]:
    """List cost entries, optionally filtered by account."""
    count_q = select(func.count()).select_from(CostEntry)
    if not user.is_master:
        count_q = count_q.where(CostEntry.tenant_id == user.tenant_id)
    if account_id:
        count_q = count_q.where(CostEntry.account_id == account_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(CostEntry)
    if not user.is_master:
        q = q.where(CostEntry.tenant_id == user.tenant_id)
    if account_id:
        q = q.where(CostEntry.account_id == account_id)
    q = q.order_by(CostEntry.incurred_date.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[CostEntryResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/entries/{entry_id}", response_model=CostEntryResponse)
async def get_cost_entry(
    entry_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> CostEntryResponse:
    """Get a cost entry by ID."""
    entry = await _get_cost_entry(session, entry_id, user)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cost entry not found")
    return CostEntryResponse.model_validate(entry)


@router.post("/entries", response_model=CostEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_cost_entry(
    data: CostEntryCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> CostEntryResponse:
    """Create a cost entry."""
    aq = select(Account).where(Account.id == data.account_id)
    if not user.is_master:
        aq = aq.where(Account.tenant_id == user.tenant_id)
    ar = await session.execute(aq)
    if not ar.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    entry = CostEntry(
        tenant_id=user.tenant_id,
        account_id=data.account_id,
        cost_type=data.cost_type,
        status=data.status,
        amount=data.amount,
        recovered_amount=data.recovered_amount,
        is_recoverable=data.is_recoverable,
        is_firm_cost=data.is_firm_cost,
        vendor_name=data.vendor_name,
        vendor_reference=data.vendor_reference,
        description=data.description,
        incurred_date=data.incurred_date,
        approved_by_id=data.approved_by_id,
        approved_at=data.approved_at,
        trust_account_id=data.trust_account_id,
    )
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return CostEntryResponse.model_validate(entry)


@router.patch("/entries/{entry_id}", response_model=CostEntryResponse)
async def update_cost_entry(
    entry_id: uuid.UUID,
    data: CostEntryUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> CostEntryResponse:
    """Update a cost entry."""
    entry = await _get_cost_entry(session, entry_id, user)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cost entry not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(entry, k, v)
    await session.flush()
    return CostEntryResponse.model_validate(entry)


# --- Disbursements ---


async def _get_disbursement(
    session: AsyncSession, disb_id: uuid.UUID, user: CurrentUser
) -> CostDisbursement | None:
    q = select(CostDisbursement).where(CostDisbursement.id == disb_id)
    if not user.is_master:
        q = q.where(CostDisbursement.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


@router.get("/disbursements", response_model=PaginatedResponse[CostDisbursementResponse])
async def list_cost_disbursements(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    cost_entry_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[CostDisbursementResponse]:
    """List cost disbursements."""
    count_q = select(func.count()).select_from(CostDisbursement)
    if not user.is_master:
        count_q = count_q.where(CostDisbursement.tenant_id == user.tenant_id)
    if cost_entry_id:
        count_q = count_q.where(CostDisbursement.cost_entry_id == cost_entry_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(CostDisbursement)
    if not user.is_master:
        q = q.where(CostDisbursement.tenant_id == user.tenant_id)
    if cost_entry_id:
        q = q.where(CostDisbursement.cost_entry_id == cost_entry_id)
    q = q.order_by(CostDisbursement.disbursed_at.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[CostDisbursementResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/disbursements/{disbursement_id}", response_model=CostDisbursementResponse)
async def get_cost_disbursement(
    disbursement_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> CostDisbursementResponse:
    """Get a cost disbursement by ID."""
    d = await _get_disbursement(session, disbursement_id, user)
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Disbursement not found")
    return CostDisbursementResponse.model_validate(d)


@router.post(
    "/disbursements",
    response_model=CostDisbursementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_cost_disbursement(
    data: CostDisbursementCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> CostDisbursementResponse:
    """Create a cost disbursement; validates trust account balance when a trust account is linked."""
    entry = await _get_cost_entry(session, data.cost_entry_id, user)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cost entry not found")

    if entry.trust_account_id:
        ta = await _get_trust_for_cost(session, entry.trust_account_id, user)
        if not ta:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trust account not found")
        if ta.current_balance < data.amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient balance in linked trust account for this disbursement",
            )

    disb = CostDisbursement(
        tenant_id=entry.tenant_id,
        cost_entry_id=data.cost_entry_id,
        amount=data.amount,
        method=data.method,
        check_number=data.check_number,
        reference_number=data.reference_number,
        payee=data.payee,
        disbursed_at=data.disbursed_at,
        disbursed_by_id=data.disbursed_by_id or user.user_id,
        trust_transaction_id=data.trust_transaction_id,
    )
    session.add(disb)
    await session.flush()
    await session.refresh(disb)
    return CostDisbursementResponse.model_validate(disb)


@router.patch("/disbursements/{disbursement_id}", response_model=CostDisbursementResponse)
async def update_cost_disbursement(
    disbursement_id: uuid.UUID,
    data: CostDisbursementUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> CostDisbursementResponse:
    """Update a cost disbursement."""
    disb = await _get_disbursement(session, disbursement_id, user)
    if not disb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Disbursement not found")

    entry = await _get_cost_entry(session, disb.cost_entry_id, user)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cost entry not found")

    new_amount = data.amount if data.amount is not None else disb.amount
    if entry.trust_account_id:
        ta = await _get_trust_for_cost(session, entry.trust_account_id, user)
        if ta and ta.current_balance < new_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient balance in linked trust account for this disbursement amount",
            )

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(disb, k, v)
    await session.flush()
    return CostDisbursementResponse.model_validate(disb)


# --- Client billing ---


async def _get_billing(
    session: AsyncSession, billing_id: uuid.UUID, user: CurrentUser
) -> CostBilling | None:
    q = select(CostBilling).where(CostBilling.id == billing_id)
    if not user.is_master:
        q = q.where(CostBilling.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


@router.get("/billings", response_model=PaginatedResponse[CostBillingResponse])
async def list_cost_billings(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[CostBillingResponse]:
    """List client cost billings."""
    count_q = select(func.count()).select_from(CostBilling)
    if not user.is_master:
        count_q = count_q.where(CostBilling.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(CostBilling)
    if not user.is_master:
        q = q.where(CostBilling.tenant_id == user.tenant_id)
    q = q.order_by(CostBilling.created_at.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[CostBillingResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/billings/{billing_id}", response_model=CostBillingResponse)
async def get_cost_billing(
    billing_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> CostBillingResponse:
    """Get a cost billing by ID."""
    bill = await _get_billing(session, billing_id, user)
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cost billing not found")
    return CostBillingResponse.model_validate(bill)


@router.post("/billings", response_model=CostBillingResponse, status_code=status.HTTP_201_CREATED)
async def create_cost_billing(
    data: CostBillingCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> CostBillingResponse:
    """Create a client cost billing."""
    bill = CostBilling(
        tenant_id=user.tenant_id,
        client_name=data.client_name,
        client_reference=data.client_reference,
        status=data.status,
        total_amount=data.total_amount,
        paid_amount=data.paid_amount,
        line_items=data.line_items,
        billing_period_start=data.billing_period_start,
        billing_period_end=data.billing_period_end,
        sent_at=data.sent_at,
        due_date=data.due_date,
        paid_at=data.paid_at,
        notes=data.notes,
    )
    session.add(bill)
    await session.flush()
    await session.refresh(bill)
    return CostBillingResponse.model_validate(bill)


@router.patch("/billings/{billing_id}", response_model=CostBillingResponse)
async def update_cost_billing(
    billing_id: uuid.UUID,
    data: CostBillingUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> CostBillingResponse:
    """Update a client cost billing."""
    bill = await _get_billing(session, billing_id, user)
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cost billing not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(bill, k, v)
    await session.flush()
    return CostBillingResponse.model_validate(bill)
