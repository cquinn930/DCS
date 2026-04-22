"""Tag definitions and account tag assignments."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import Account
from dcs_api.models.tags import TagAssignment, TagDefinition
from dcs_api.schemas.tags import (
    TagAssignmentCreate,
    TagAssignmentResponse,
    TagAssignmentUpdate,
    TagDefinitionCreate,
    TagDefinitionResponse,
    TagDefinitionUpdate,
)
from dcs_api.schemas.common import PaginatedResponse

router = APIRouter()

MAX_PAGE_SIZE = 100

PERM = "tags:manage"


async def _get_tag_definition(
    session: AsyncSession, tag_id: uuid.UUID, user: CurrentUser
) -> TagDefinition | None:
    q = select(TagDefinition).where(TagDefinition.id == tag_id)
    if not user.is_master:
        q = q.where(TagDefinition.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


async def _get_assignment(
    session: AsyncSession, assignment_id: uuid.UUID, user: CurrentUser
) -> TagAssignment | None:
    q = select(TagAssignment).where(TagAssignment.id == assignment_id)
    if not user.is_master:
        q = q.where(TagAssignment.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


# --- Tag definitions ---


@router.get("/definitions", response_model=PaginatedResponse[TagDefinitionResponse])
async def list_tag_definitions(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[TagDefinitionResponse]:
    """List tag definitions."""
    count_q = select(func.count()).select_from(TagDefinition)
    if not user.is_master:
        count_q = count_q.where(TagDefinition.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(TagDefinition)
    if not user.is_master:
        q = q.where(TagDefinition.tenant_id == user.tenant_id)
    q = q.order_by(TagDefinition.code).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[TagDefinitionResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/definitions/{definition_id}", response_model=TagDefinitionResponse)
async def get_tag_definition(
    definition_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> TagDefinitionResponse:
    """Get a tag definition by ID."""
    td = await _get_tag_definition(session, definition_id, user)
    if not td:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag definition not found")
    return TagDefinitionResponse.model_validate(td)


@router.post("/definitions", response_model=TagDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_tag_definition(
    data: TagDefinitionCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> TagDefinitionResponse:
    """Create a tag definition."""
    td = TagDefinition(
        tenant_id=user.tenant_id,
        code=data.code,
        name=data.name,
        description=data.description,
        category=data.category,
        visibility=data.visibility,
        color=data.color,
        auto_activity_code_id=data.auto_activity_code_id,
        auto_status_change=data.auto_status_change,
        auto_queue_id=data.auto_queue_id,
        triggers=data.triggers,
        is_active=data.is_active,
        is_system=data.is_system,
    )
    session.add(td)
    await session.flush()
    await session.refresh(td)
    return TagDefinitionResponse.model_validate(td)


@router.patch("/definitions/{definition_id}", response_model=TagDefinitionResponse)
async def update_tag_definition(
    definition_id: uuid.UUID,
    data: TagDefinitionUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> TagDefinitionResponse:
    """Update a tag definition."""
    td = await _get_tag_definition(session, definition_id, user)
    if not td:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag definition not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(td, k, v)
    await session.flush()
    return TagDefinitionResponse.model_validate(td)


# --- Assignments ---


@router.post("/assignments", response_model=TagAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def apply_tag_to_account(
    data: TagAssignmentCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> TagAssignmentResponse:
    """Apply a tag to an account."""
    td = await _get_tag_definition(session, data.tag_definition_id, user)
    if not td:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag definition not found")

    aq = select(Account).where(Account.id == data.account_id)
    if not user.is_master:
        aq = aq.where(Account.tenant_id == user.tenant_id)
    if not (await session.execute(aq)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    dup_q = select(TagAssignment).where(
        TagAssignment.account_id == data.account_id,
        TagAssignment.tag_definition_id == data.tag_definition_id,
        TagAssignment.removed_at.is_(None),
    )
    if not user.is_master:
        dup_q = dup_q.where(TagAssignment.tenant_id == user.tenant_id)
    if (await session.execute(dup_q)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tag already assigned to this account",
        )

    now = data.applied_at or datetime.now(timezone.utc)
    ta = TagAssignment(
        tenant_id=td.tenant_id,
        account_id=data.account_id,
        tag_definition_id=data.tag_definition_id,
        applied_at=now,
        applied_by_id=data.applied_by_id or user.user_id,
        removed_at=data.removed_at,
        removed_by_id=data.removed_by_id,
        notes=data.notes,
        tag_metadata=data.tag_metadata,
    )
    session.add(ta)
    await session.flush()
    await session.refresh(ta)
    return TagAssignmentResponse.model_validate(ta)


@router.delete("/assignments/{assignment_id}")
async def remove_tag_assignment(
    assignment_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> dict[str, str]:
    """Remove a tag assignment (hard delete)."""
    ta = await _get_assignment(session, assignment_id, user)
    if not ta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag assignment not found")
    await session.delete(ta)
    await session.flush()
    return {"message": "Tag assignment removed", "assignment_id": str(assignment_id)}


@router.patch("/assignments/{assignment_id}", response_model=TagAssignmentResponse)
async def update_tag_assignment(
    assignment_id: uuid.UUID,
    data: TagAssignmentUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> TagAssignmentResponse:
    """Update a tag assignment (e.g. soft-remove via removed_at)."""
    ta = await _get_assignment(session, assignment_id, user)
    if not ta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag assignment not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(ta, k, v)
    await session.flush()
    return TagAssignmentResponse.model_validate(ta)


@router.get(
    "/accounts/{account_id}/tags",
    response_model=PaginatedResponse[TagAssignmentResponse],
)
async def list_tags_on_account(
    account_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[TagAssignmentResponse]:
    """List tag assignments on an account."""
    aq = select(Account).where(Account.id == account_id)
    if not user.is_master:
        aq = aq.where(Account.tenant_id == user.tenant_id)
    if not (await session.execute(aq)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    count_q = (
        select(func.count())
        .select_from(TagAssignment)
        .where(TagAssignment.account_id == account_id, TagAssignment.removed_at.is_(None))
    )
    if not user.is_master:
        count_q = count_q.where(TagAssignment.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(TagAssignment).where(
        TagAssignment.account_id == account_id,
        TagAssignment.removed_at.is_(None),
    )
    if not user.is_master:
        q = q.where(TagAssignment.tenant_id == user.tenant_id)
    q = q.order_by(TagAssignment.applied_at.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[TagAssignmentResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get(
    "/definitions/{tag_id}/accounts",
    response_model=PaginatedResponse[TagAssignmentResponse],
)
async def list_accounts_with_tag(
    tag_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[TagAssignmentResponse]:
    """List accounts that have a given tag (active assignments)."""
    if not await _get_tag_definition(session, tag_id, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag definition not found")

    count_q = (
        select(func.count())
        .select_from(TagAssignment)
        .where(
            TagAssignment.tag_definition_id == tag_id,
            TagAssignment.removed_at.is_(None),
        )
    )
    if not user.is_master:
        count_q = count_q.where(TagAssignment.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(TagAssignment).where(
        TagAssignment.tag_definition_id == tag_id,
        TagAssignment.removed_at.is_(None),
    )
    if not user.is_master:
        q = q.where(TagAssignment.tenant_id == user.tenant_id)
    q = q.order_by(TagAssignment.applied_at.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[TagAssignmentResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


class BulkTagRequest(BaseModel):
    account_ids: list[uuid.UUID] = Field(..., min_length=1)
    tag_definition_id: uuid.UUID


@router.post("/bulk-apply", response_model=list[TagAssignmentResponse])
async def bulk_apply_tag(
    body: BulkTagRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> list[TagAssignmentResponse]:
    """Apply a tag to many accounts."""
    td = await _get_tag_definition(session, body.tag_definition_id, user)
    if not td:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag definition not found")

    now = datetime.now(timezone.utc)
    out: list[TagAssignment] = []
    for aid in body.account_ids:
        aq = select(Account).where(Account.id == aid)
        if not user.is_master:
            aq = aq.where(Account.tenant_id == user.tenant_id)
        if not (await session.execute(aq)).scalar_one_or_none():
            continue
        ta = TagAssignment(
            tenant_id=td.tenant_id,
            account_id=aid,
            tag_definition_id=body.tag_definition_id,
            applied_at=now,
            applied_by_id=user.user_id,
            metadata={},
        )
        session.add(ta)
        out.append(ta)
    await session.flush()
    for ta in out:
        await session.refresh(ta)
    return [TagAssignmentResponse.model_validate(x) for x in out]


@router.post("/bulk-remove")
async def bulk_remove_tag(
    body: BulkTagRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> dict[str, int]:
    """Remove a tag from many accounts (deletes matching active assignments)."""
    if not await _get_tag_definition(session, body.tag_definition_id, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag definition not found")

    removed = 0
    for aid in body.account_ids:
        q = select(TagAssignment).where(
            TagAssignment.account_id == aid,
            TagAssignment.tag_definition_id == body.tag_definition_id,
            TagAssignment.removed_at.is_(None),
        )
        if not user.is_master:
            q = q.where(TagAssignment.tenant_id == user.tenant_id)
        r = await session.execute(q)
        for ta in r.scalars().all():
            await session.delete(ta)
            removed += 1
    await session.flush()
    return {"removed": removed}
