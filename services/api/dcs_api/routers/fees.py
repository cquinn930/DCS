"""Fee endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import Account, Fee
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.fee import FeeApplyRequest, FeeCreate, FeeResponse, FeeUpdate

router = APIRouter()

MAX_PAGE_SIZE = 100


def _validate_fee_for_jurisdiction(account: Account, amount_cents: int) -> tuple[bool, str | None]:
    """Validate fee against account jurisdiction (placeholder rules)."""
    _ = amount_cents
    jurisdiction = (account.jurisdiction or "").upper()
    if len(jurisdiction) != 2:
        return False, "invalid_jurisdiction_code"
    return True, jurisdiction


@router.get("", response_model=PaginatedResponse[FeeResponse])
async def list_fees(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("accounts:edit_balances"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    account_id: uuid.UUID | None = None,
) -> PaginatedResponse[FeeResponse]:
    """List fees in the tenant."""
    query = select(Fee).where(Fee.tenant_id == user.tenant_id)
    if account_id:
        query = query.where(Fee.account_id == account_id)

    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Fee.applied_at.desc())
    result = await session.execute(query)
    fees = list(result.scalars().all())

    return PaginatedResponse(
        items=[FeeResponse.model_validate(f) for f in fees],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.post("/apply", response_model=FeeResponse, status_code=status.HTTP_201_CREATED)
async def apply_fee_to_account(
    data: FeeApplyRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("accounts:edit_balances"))],
) -> FeeResponse:
    """Apply a fee to an account with jurisdiction validation."""
    acc_query = select(Account).where(
        Account.id == data.account_id,
        Account.tenant_id == user.tenant_id,
    )
    acc_result = await session.execute(acc_query)
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    allowed, rule = _validate_fee_for_jurisdiction(account, data.amount)
    applied_at = datetime.now(timezone.utc)
    fee = Fee(
        tenant_id=user.tenant_id,
        account_id=data.account_id,
        fee_type=data.fee_type,
        amount=data.amount,
        description=data.description,
        is_allowed=allowed,
        jurisdiction_validated=allowed,
        validation_rule=rule,
        applied_at=applied_at,
        applied_by_id=user.user_id,
    )
    session.add(fee)
    await session.flush()
    await session.refresh(fee)
    return FeeResponse.model_validate(fee)


@router.get("/{fee_id}", response_model=FeeResponse)
async def get_fee(
    fee_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("accounts:edit_balances"))],
) -> FeeResponse:
    """Get fee by ID."""
    query = select(Fee).where(Fee.id == fee_id, Fee.tenant_id == user.tenant_id)
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee not found",
        )
    return FeeResponse.model_validate(row)


@router.post("", response_model=FeeResponse, status_code=status.HTTP_201_CREATED)
async def create_fee(
    data: FeeCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("accounts:edit_balances"))],
) -> FeeResponse:
    """Create a fee record."""
    acc_query = select(Account).where(
        Account.id == data.account_id,
        Account.tenant_id == user.tenant_id,
    )
    acc_result = await session.execute(acc_query)
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    applied_at = data.applied_at or datetime.now(timezone.utc)
    fee = Fee(
        tenant_id=user.tenant_id,
        account_id=data.account_id,
        fee_type=data.fee_type,
        amount=data.amount,
        description=data.description,
        is_allowed=data.is_allowed,
        jurisdiction_validated=data.jurisdiction_validated,
        validation_rule=data.validation_rule,
        applied_at=applied_at,
        applied_by_id=data.applied_by_id or user.user_id,
    )
    session.add(fee)
    await session.flush()
    await session.refresh(fee)
    return FeeResponse.model_validate(fee)


@router.patch("/{fee_id}", response_model=FeeResponse)
async def update_fee(
    fee_id: uuid.UUID,
    data: FeeUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("accounts:edit_balances"))],
) -> FeeResponse:
    """Update fee."""
    query = select(Fee).where(Fee.id == fee_id, Fee.tenant_id == user.tenant_id)
    result = await session.execute(query)
    fee = result.scalar_one_or_none()
    if not fee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(fee, key, value)

    await session.flush()
    await session.refresh(fee)
    return FeeResponse.model_validate(fee)


@router.delete("/{fee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fee(
    fee_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("accounts:edit_balances"))],
) -> None:
    """Delete fee."""
    query = select(Fee).where(Fee.id == fee_id, Fee.tenant_id == user.tenant_id)
    result = await session.execute(query)
    fee = result.scalar_one_or_none()
    if not fee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee not found",
        )
    await session.delete(fee)
    await session.flush()
