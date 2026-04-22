"""Financial safeguard API routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, Permissions, require_permission
from dcs_api.database import get_session
from dcs_api.models.safeguards import FinancialNote, TemporaryHold, TransactionLimit
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.safeguards import (
    FinancialNoteCreate,
    FinancialNoteResponse,
    TemporaryHoldCreate,
    TemporaryHoldResponse,
    TemporaryHoldUpdate,
    TransactionLimitCreate,
    TransactionLimitResponse,
    TransactionLimitUpdate,
)

router = APIRouter()
MAX_PAGE_SIZE = 100


@router.get("/limits", response_model=PaginatedResponse[TransactionLimitResponse])
async def list_limits(
    user: Annotated[CurrentUser, Depends(require_permission("trust:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
):
    q = select(TransactionLimit).where(TransactionLimit.tenant_id == user.tenant_id)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size))
    items = [TransactionLimitResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.post("/limits", response_model=TransactionLimitResponse, status_code=status.HTTP_201_CREATED)
async def create_limit(
    body: TransactionLimitCreate,
    user: Annotated[CurrentUser, Depends(require_permission("trust:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    limit = TransactionLimit(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(limit)
    await session.flush()
    await session.refresh(limit)
    return TransactionLimitResponse.model_validate(limit)


@router.patch("/limits/{limit_id}", response_model=TransactionLimitResponse)
async def update_limit(
    limit_id: str,
    body: TransactionLimitUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("trust:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(TransactionLimit).where(TransactionLimit.id == limit_id, TransactionLimit.tenant_id == user.tenant_id)
    )
    limit = result.scalar_one_or_none()
    if not limit:
        raise HTTPException(status_code=404, detail="Limit not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(limit, k, v)
    await session.flush()
    await session.refresh(limit)
    return TransactionLimitResponse.model_validate(limit)


@router.delete("/limits/{limit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_limit(
    limit_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("trust:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(TransactionLimit).where(TransactionLimit.id == limit_id, TransactionLimit.tenant_id == user.tenant_id)
    )
    limit = result.scalar_one_or_none()
    if not limit:
        raise HTTPException(status_code=404, detail="Limit not found")
    await session.delete(limit)
    await session.flush()


@router.get("/notes", response_model=PaginatedResponse[FinancialNoteResponse])
async def list_notes(
    user: Annotated[CurrentUser, Depends(require_permission("trust:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    account_id: str | None = None,
):
    q = select(FinancialNote).where(FinancialNote.tenant_id == user.tenant_id)
    if account_id:
        q = q.where(FinancialNote.account_id == account_id)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).order_by(FinancialNote.created_at.desc()))
    items = [FinancialNoteResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.post("/notes", response_model=FinancialNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    body: FinancialNoteCreate,
    user: Annotated[CurrentUser, Depends(require_permission("trust:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    note = FinancialNote(**body.model_dump(), tenant_id=user.tenant_id, created_by=user.id)
    session.add(note)
    await session.flush()
    await session.refresh(note)
    return FinancialNoteResponse.model_validate(note)


@router.post("/notes/{note_id}/acknowledge", response_model=FinancialNoteResponse)
async def acknowledge_note(
    note_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("trust:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    from datetime import datetime, timezone
    result = await session.execute(
        select(FinancialNote).where(FinancialNote.id == note_id, FinancialNote.tenant_id == user.tenant_id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    note.acknowledged_by = user.id
    note.acknowledged_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(note)
    return FinancialNoteResponse.model_validate(note)


@router.get("/holds", response_model=PaginatedResponse[TemporaryHoldResponse])
async def list_holds(
    user: Annotated[CurrentUser, Depends(require_permission("trust:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    account_id: str | None = None,
    active_only: bool = True,
):
    q = select(TemporaryHold).where(TemporaryHold.tenant_id == user.tenant_id)
    if account_id:
        q = q.where(TemporaryHold.account_id == account_id)
    if active_only:
        q = q.where(TemporaryHold.is_active == True)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).order_by(TemporaryHold.created_at.desc()))
    items = [TemporaryHoldResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.post("/holds", response_model=TemporaryHoldResponse, status_code=status.HTTP_201_CREATED)
async def create_hold(
    body: TemporaryHoldCreate,
    user: Annotated[CurrentUser, Depends(require_permission("trust:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    hold = TemporaryHold(**body.model_dump(), tenant_id=user.tenant_id, placed_by=user.id)
    session.add(hold)
    await session.flush()
    await session.refresh(hold)
    return TemporaryHoldResponse.model_validate(hold)


@router.patch("/holds/{hold_id}", response_model=TemporaryHoldResponse)
async def update_hold(
    hold_id: str,
    body: TemporaryHoldUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("trust:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(TemporaryHold).where(TemporaryHold.id == hold_id, TemporaryHold.tenant_id == user.tenant_id)
    )
    hold = result.scalar_one_or_none()
    if not hold:
        raise HTTPException(status_code=404, detail="Hold not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(hold, k, v)
    await session.flush()
    await session.refresh(hold)
    return TemporaryHoldResponse.model_validate(hold)


@router.post("/holds/{hold_id}/release", response_model=TemporaryHoldResponse)
async def release_hold(
    hold_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("trust:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    from datetime import datetime, timezone
    result = await session.execute(
        select(TemporaryHold).where(TemporaryHold.id == hold_id, TemporaryHold.tenant_id == user.tenant_id)
    )
    hold = result.scalar_one_or_none()
    if not hold:
        raise HTTPException(status_code=404, detail="Hold not found")
    hold.is_active = False
    hold.released_by = user.id
    hold.released_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(hold)
    return TemporaryHoldResponse.model_validate(hold)
