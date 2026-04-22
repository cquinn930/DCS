"""Dispute management endpoints.

Non-legal guidance: Dispute handling must comply with CFPB Regulation F
requirements including timelines and consumer communication rules.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, Permissions, get_current_user, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import Account, AccountStatus, Dispute, DisputeStatus
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.dispute import DisputeCreate, DisputeResponse, DisputeUpdate

router = APIRouter()

MAX_PAGE_SIZE = 100


@router.get("", response_model=PaginatedResponse[DisputeResponse])
async def list_disputes(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_DISPUTES))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    status_filter: DisputeStatus | None = None,
    account_id: uuid.UUID | None = None,
) -> PaginatedResponse[DisputeResponse]:
    """List disputes in the tenant."""
    query = select(Dispute).where(Dispute.tenant_id == user.tenant_id)

    if status_filter:
        query = query.where(Dispute.status == status_filter)
    if account_id:
        query = query.where(Dispute.account_id == account_id)

    # Count total
    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    # Get paginated results
    offset = (page - 1) * page_size
    query = query.order_by(Dispute.filed_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    disputes = list(result.scalars().all())

    return PaginatedResponse(
        items=[DisputeResponse.model_validate(d) for d in disputes],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/overdue", response_model=list[DisputeResponse])
async def list_overdue_disputes(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_DISPUTES))],
) -> list[DisputeResponse]:
    """List disputes past their response due date.

    Non-legal guidance: Overdue disputes may indicate Reg F compliance risk.
    """
    now = datetime.now(timezone.utc)
    query = select(Dispute).where(
        Dispute.tenant_id == user.tenant_id,
        Dispute.status.in_([DisputeStatus.PENDING, DisputeStatus.UNDER_REVIEW]),
        Dispute.response_due_date < now,
    )
    result = await session.execute(query)
    disputes = list(result.scalars().all())

    return [DisputeResponse.model_validate(d) for d in disputes]


@router.get("/{dispute_id}", response_model=DisputeResponse)
async def get_dispute(
    dispute_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_DISPUTES))],
) -> DisputeResponse:
    """Get dispute by ID."""
    query = select(Dispute).where(
        Dispute.id == dispute_id, Dispute.tenant_id == user.tenant_id
    )
    result = await session.execute(query)
    dispute = result.scalar_one_or_none()

    if not dispute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispute not found",
        )

    return DisputeResponse.model_validate(dispute)


@router.post("", response_model=DisputeResponse, status_code=status.HTTP_201_CREATED)
async def create_dispute(
    data: DisputeCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.MANAGE_DISPUTES))],
) -> DisputeResponse:
    """Create a new dispute.

    Non-legal guidance: Filing a dispute automatically:
    1. Applies legal hold to the account
    2. Pauses outbound contact attempts
    3. Starts the Reg F response timeline
    """
    # Verify account exists and get current status
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
    # Reg F requires response within 30 days (configurable via policy pack)
    response_due = now + timedelta(days=30)

    dispute = Dispute(
        tenant_id=user.tenant_id,
        account_id=data.account_id,
        reason=data.reason,
        description=data.description,
        documents=data.documents,
        filed_at=now,
        response_due_date=response_due,
    )
    session.add(dispute)

    # Apply legal hold to account
    account.legal_hold = True
    account.legal_hold_reason = f"Dispute filed: {data.reason.value}"
    account.legal_hold_date = now
    account.status = AccountStatus.LEGAL_HOLD

    await session.flush()
    return DisputeResponse.model_validate(dispute)


@router.patch("/{dispute_id}", response_model=DisputeResponse)
async def update_dispute(
    dispute_id: uuid.UUID,
    data: DisputeUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.APPROVE_DISPUTE_RESOLUTION))],
) -> DisputeResponse:
    """Update dispute status.

    Non-legal guidance: Only supervisors and legal reviewers can approve resolutions.
    """
    query = select(Dispute).where(
        Dispute.id == dispute_id, Dispute.tenant_id == user.tenant_id
    )
    result = await session.execute(query)
    dispute = result.scalar_one_or_none()

    if not dispute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispute not found",
        )

    now = datetime.now(timezone.utc)

    # Apply updates
    if data.status:
        dispute.status = data.status

        # Record response/resolution timestamps
        if data.status == DisputeStatus.UNDER_REVIEW and not dispute.responded_at:
            dispute.responded_at = now
        elif data.status in [DisputeStatus.RESOLVED_VALID, DisputeStatus.RESOLVED_INVALID]:
            dispute.resolved_at = now
            dispute.resolved_by_id = user.user_id

    if data.resolution_notes:
        dispute.resolution_notes = data.resolution_notes

    await session.flush()
    return DisputeResponse.model_validate(dispute)
