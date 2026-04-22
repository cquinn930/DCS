"""Client portal API routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, Permissions, require_permission
from dcs_api.database import get_session
from dcs_api.models.client_portal import ClientPortalUser
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.client_portal import (
    ClientPortalUserCreate,
    ClientPortalUserResponse,
    ClientPortalUserUpdate,
)

router = APIRouter()
MAX_PAGE_SIZE = 100


@router.get("", response_model=PaginatedResponse[ClientPortalUserResponse])
async def list_portal_users(
    user: Annotated[CurrentUser, Depends(require_permission("integrations:configure"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    client_id: str | None = None,
):
    q = select(ClientPortalUser).where(ClientPortalUser.tenant_id == user.tenant_id)
    if client_id:
        q = q.where(ClientPortalUser.client_id == client_id)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).order_by(ClientPortalUser.name))
    items = [ClientPortalUserResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/{portal_user_id}", response_model=ClientPortalUserResponse)
async def get_portal_user(
    portal_user_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("integrations:configure"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(ClientPortalUser).where(ClientPortalUser.id == portal_user_id, ClientPortalUser.tenant_id == user.tenant_id)
    )
    pu = result.scalar_one_or_none()
    if not pu:
        raise HTTPException(status_code=404, detail="Portal user not found")
    return ClientPortalUserResponse.model_validate(pu)


@router.post("", response_model=ClientPortalUserResponse, status_code=status.HTTP_201_CREATED)
async def create_portal_user(
    body: ClientPortalUserCreate,
    user: Annotated[CurrentUser, Depends(require_permission("integrations:configure"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    import bcrypt
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    data = body.model_dump(exclude={"password"})
    pu = ClientPortalUser(**data, password_hash=pw_hash, tenant_id=user.tenant_id)
    session.add(pu)
    await session.flush()
    await session.refresh(pu)
    return ClientPortalUserResponse.model_validate(pu)


@router.patch("/{portal_user_id}", response_model=ClientPortalUserResponse)
async def update_portal_user(
    portal_user_id: str,
    body: ClientPortalUserUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("integrations:configure"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(ClientPortalUser).where(ClientPortalUser.id == portal_user_id, ClientPortalUser.tenant_id == user.tenant_id)
    )
    pu = result.scalar_one_or_none()
    if not pu:
        raise HTTPException(status_code=404, detail="Portal user not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(pu, k, v)
    await session.flush()
    await session.refresh(pu)
    return ClientPortalUserResponse.model_validate(pu)


@router.delete("/{portal_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portal_user(
    portal_user_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("integrations:configure"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(ClientPortalUser).where(ClientPortalUser.id == portal_user_id, ClientPortalUser.tenant_id == user.tenant_id)
    )
    pu = result.scalar_one_or_none()
    if not pu:
        raise HTTPException(status_code=404, detail="Portal user not found")
    await session.delete(pu)
    await session.flush()
