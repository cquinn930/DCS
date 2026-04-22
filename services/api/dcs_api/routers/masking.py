"""Field masking policy endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.masking import MaskingPolicy
from dcs_api.schemas.masking import (
    MaskingPolicyCreate,
    MaskingPolicyResponse,
    MaskingPolicyUpdate,
)
from dcs_api.schemas.common import PaginatedResponse

router = APIRouter()

MAX_PAGE_SIZE = 100

PERM = "masking:manage"


async def _get_policy(
    session: AsyncSession, policy_id: uuid.UUID, user: CurrentUser
) -> MaskingPolicy | None:
    q = select(MaskingPolicy).where(MaskingPolicy.id == policy_id)
    if not user.is_master:
        q = q.where(MaskingPolicy.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


@router.get("/policies", response_model=PaginatedResponse[MaskingPolicyResponse])
async def list_masking_policies(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[MaskingPolicyResponse]:
    """List masking policies."""
    count_q = select(func.count()).select_from(MaskingPolicy)
    if not user.is_master:
        count_q = count_q.where(MaskingPolicy.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(MaskingPolicy)
    if not user.is_master:
        q = q.where(MaskingPolicy.tenant_id == user.tenant_id)
    q = q.order_by(MaskingPolicy.entity_type, MaskingPolicy.field_name).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[MaskingPolicyResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/policies/{policy_id}", response_model=MaskingPolicyResponse)
async def get_masking_policy(
    policy_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> MaskingPolicyResponse:
    """Get a masking policy by ID."""
    pol = await _get_policy(session, policy_id, user)
    if not pol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Masking policy not found")
    return MaskingPolicyResponse.model_validate(pol)


@router.post("/policies", response_model=MaskingPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_masking_policy(
    data: MaskingPolicyCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> MaskingPolicyResponse:
    """Create a masking policy."""
    pol = MaskingPolicy(
        tenant_id=user.tenant_id,
        entity_type=data.entity_type,
        field_name=data.field_name,
        mask_type=data.mask_type,
        mask_character=data.mask_character,
        visible_chars=data.visible_chars,
        exempt_roles=data.exempt_roles,
        apply_to_exports=data.apply_to_exports,
        apply_to_api=data.apply_to_api,
        apply_to_logs=data.apply_to_logs,
        is_active=data.is_active,
        description=data.description,
    )
    session.add(pol)
    await session.flush()
    await session.refresh(pol)
    return MaskingPolicyResponse.model_validate(pol)


@router.patch("/policies/{policy_id}", response_model=MaskingPolicyResponse)
async def update_masking_policy(
    policy_id: uuid.UUID,
    data: MaskingPolicyUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> MaskingPolicyResponse:
    """Update a masking policy."""
    pol = await _get_policy(session, policy_id, user)
    if not pol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Masking policy not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(pol, k, v)
    await session.flush()
    return MaskingPolicyResponse.model_validate(pol)
