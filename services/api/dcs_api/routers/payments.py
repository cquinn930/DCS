"""Payment processing endpoints.

Non-legal guidance: All payments are tokenized via Tratta to minimize PCI scope.
No PAN (card numbers) are stored in the system.
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.rbac import CurrentUser, Permissions, get_current_user, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import (
    Account,
    AccountStatus,
    AllocationTarget,
    Payment,
    PaymentAllocation,
    PaymentStatus,
)
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.payment import PaymentCreate, PaymentResponse

router = APIRouter()

MAX_PAGE_SIZE = 100


@router.get("", response_model=PaginatedResponse[PaymentResponse])
async def list_payments(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ALL_ACCOUNTS))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    account_id: uuid.UUID | None = None,
    status_filter: PaymentStatus | None = None,
) -> PaginatedResponse[PaymentResponse]:
    """List payments in the tenant."""
    query = select(Payment).where(Payment.tenant_id == user.tenant_id)

    if account_id:
        query = query.where(Payment.account_id == account_id)
    if status_filter:
        query = query.where(Payment.status == status_filter)

    # Count total
    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    # Get paginated results
    offset = (page - 1) * page_size
    query = (
        query.options(selectinload(Payment.allocations))
        .order_by(Payment.received_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(query)
    payments = list(result.scalars().all())

    return PaginatedResponse(
        items=[PaymentResponse.model_validate(p) for p in payments],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_ASSIGNED_ACCOUNTS))],
) -> PaymentResponse:
    """Get payment by ID."""
    query = (
        select(Payment)
        .where(Payment.id == payment_id, Payment.tenant_id == user.tenant_id)
        .options(selectinload(Payment.allocations))
    )
    result = await session.execute(query)
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    return PaymentResponse.model_validate(payment)


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    data: PaymentCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> PaymentResponse:
    """Record a new payment.

    Non-legal guidance: Payments are processed via Tratta tokenization.
    Allocation follows tenant configuration (default: interest -> principal -> fees).
    """
    # Verify account exists
    account_query = select(Account).where(
        Account.id == data.account_id, Account.tenant_id == user.tenant_id
    )
    account_result = await session.execute(account_query)
    account = account_result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    now = datetime.now(timezone.utc)

    payment = Payment(
        tenant_id=user.tenant_id,
        account_id=data.account_id,
        amount=data.amount,
        method=data.method,
        status=PaymentStatus.PENDING,
        processor_reference=None,  # Set by payment processor
        received_at=now,
        source=data.source,
    )
    session.add(payment)
    await session.flush()

    # Calculate allocations (default: interest -> principal -> fees)
    remaining = data.amount
    allocation_order = [
        (AllocationTarget.INTEREST, account.current_interest),
        (AllocationTarget.PRINCIPAL, account.current_principal),
        (AllocationTarget.FEES, account.current_fees),
    ]

    allocations = []
    for order, (target, balance) in enumerate(allocation_order):
        if remaining <= 0:
            break
        allocated = min(remaining, balance)
        if allocated > 0:
            allocation = PaymentAllocation(
                tenant_id=user.tenant_id,
                payment_id=payment.id,
                target=target,
                amount=allocated,
                order=order,
            )
            session.add(allocation)
            allocations.append(allocation)
            remaining -= allocated

    # Update account balances
    for allocation in allocations:
        if allocation.target == AllocationTarget.INTEREST:
            account.current_interest -= allocation.amount
        elif allocation.target == AllocationTarget.PRINCIPAL:
            account.current_principal -= allocation.amount
        elif allocation.target == AllocationTarget.FEES:
            account.current_fees -= allocation.amount

    account.total_balance = (
        account.current_principal + account.current_interest + account.current_fees
    )

    # Check if paid in full
    if account.total_balance <= 0:
        account.status = AccountStatus.PAID_IN_FULL

    # Mark payment as completed (in production, this would happen after processor confirmation)
    payment.status = PaymentStatus.COMPLETED
    payment.processed_at = now

    await session.flush()
    await session.refresh(payment)

    # Reload with allocations
    query = (
        select(Payment)
        .where(Payment.id == payment.id)
        .options(selectinload(Payment.allocations))
    )
    result = await session.execute(query)
    payment = result.scalar_one()

    return PaymentResponse.model_validate(payment)


@router.post("/{payment_id}/reverse")
async def reverse_payment(
    payment_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.EDIT_BALANCES_FEES))],
) -> dict:
    """Reverse a payment.

    Non-legal guidance: Reversals should be used for returned checks, NSF, or chargebacks.
    """
    query = (
        select(Payment)
        .where(Payment.id == payment_id, Payment.tenant_id == user.tenant_id)
        .options(selectinload(Payment.allocations))
    )
    result = await session.execute(query)
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    if payment.status == PaymentStatus.REVERSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment already reversed",
        )

    # Get account
    account = await session.get(Account, payment.account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    # Reverse allocations
    for allocation in payment.allocations:
        if allocation.target == AllocationTarget.INTEREST:
            account.current_interest += allocation.amount
        elif allocation.target == AllocationTarget.PRINCIPAL:
            account.current_principal += allocation.amount
        elif allocation.target == AllocationTarget.FEES:
            account.current_fees += allocation.amount

    account.total_balance = (
        account.current_principal + account.current_interest + account.current_fees
    )

    # Reactivate account if it was paid in full
    if account.status == AccountStatus.PAID_IN_FULL:
        account.status = AccountStatus.ACTIVE

    payment.status = PaymentStatus.REVERSED

    await session.flush()
    return {"message": "Payment reversed", "payment_id": str(payment_id)}
