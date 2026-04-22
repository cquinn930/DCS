"""Notice endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import Account, Notice, NoticeStatus, NoticeType
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.notice import NoticeCreate, NoticeResponse, NoticeUpdate

router = APIRouter()

MAX_PAGE_SIZE = 100


@router.get("", response_model=PaginatedResponse[NoticeResponse])
async def list_notices(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("notices:manage"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    account_id: uuid.UUID | None = None,
    notice_type: NoticeType | None = None,
    status_filter: NoticeStatus | None = None,
) -> PaginatedResponse[NoticeResponse]:
    """List notices in the tenant (optionally by account)."""
    query = select(Notice).where(Notice.tenant_id == user.tenant_id)
    if account_id:
        query = query.where(Notice.account_id == account_id)
    if notice_type:
        query = query.where(Notice.notice_type == notice_type)
    if status_filter:
        query = query.where(Notice.status == status_filter)

    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Notice.created_at.desc())
    result = await session.execute(query)
    notices = list(result.scalars().all())

    return PaginatedResponse(
        items=[NoticeResponse.model_validate(n) for n in notices],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/{notice_id}", response_model=NoticeResponse)
async def get_notice(
    notice_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("notices:manage"))],
) -> NoticeResponse:
    """Get notice by ID."""
    query = select(Notice).where(Notice.id == notice_id, Notice.tenant_id == user.tenant_id)
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )
    return NoticeResponse.model_validate(row)


@router.post("", response_model=NoticeResponse, status_code=status.HTTP_201_CREATED)
async def create_notice(
    data: NoticeCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("notices:manage"))],
) -> NoticeResponse:
    """Create a notice."""
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

    notice = Notice(
        tenant_id=user.tenant_id,
        account_id=data.account_id,
        notice_type=data.notice_type,
        status=data.status,
        template_id=data.template_id,
        template_version=data.template_version,
        channel=data.channel,
        recipient=data.recipient,
        content_hash=data.content_hash,
        scheduled_at=data.scheduled_at,
    )
    session.add(notice)
    await session.flush()
    await session.refresh(notice)
    return NoticeResponse.model_validate(notice)


@router.patch("/{notice_id}", response_model=NoticeResponse)
async def update_notice(
    notice_id: uuid.UUID,
    data: NoticeUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("notices:manage"))],
) -> NoticeResponse:
    """Update notice."""
    query = select(Notice).where(Notice.id == notice_id, Notice.tenant_id == user.tenant_id)
    result = await session.execute(query)
    notice = result.scalar_one_or_none()
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(notice, key, value)

    await session.flush()
    await session.refresh(notice)
    return NoticeResponse.model_validate(notice)


@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notice(
    notice_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("notices:manage"))],
) -> None:
    """Delete notice."""
    query = select(Notice).where(Notice.id == notice_id, Notice.tenant_id == user.tenant_id)
    result = await session.execute(query)
    notice = result.scalar_one_or_none()
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )
    await session.delete(notice)
    await session.flush()


@router.post("/{notice_id}/send", response_model=NoticeResponse)
async def send_notice(
    notice_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("notices:manage"))],
) -> NoticeResponse:
    """Mark notice as sent (dispatch hook would integrate with mail/SMS providers)."""
    query = select(Notice).where(Notice.id == notice_id, Notice.tenant_id == user.tenant_id)
    result = await session.execute(query)
    notice = result.scalar_one_or_none()
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )
    now = datetime.now(timezone.utc)
    notice.status = NoticeStatus.SENT
    notice.sent_at = now
    notice.error_message = None
    await session.flush()
    await session.refresh(notice)
    return NoticeResponse.model_validate(notice)
