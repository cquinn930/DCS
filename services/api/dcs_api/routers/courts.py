"""Court management API routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.rbac import CurrentUser, Permissions, require_permission
from dcs_api.database import get_session
from dcs_api.models.courts import Court, CourtCostOverride, CourtRepresentative
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.courts import (
    CourtCostOverrideCreate,
    CourtCostOverrideResponse,
    CourtCreate,
    CourtRepresentativeCreate,
    CourtRepresentativeResponse,
    CourtResponse,
    CourtUpdate,
)

router = APIRouter()
MAX_PAGE_SIZE = 100


@router.get("", response_model=PaginatedResponse[CourtResponse])
async def list_courts(
    user: Annotated[CurrentUser, Depends(require_permission("courts:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    search: str | None = None,
    state: str | None = None,
):
    q = select(Court).where(Court.tenant_id == user.tenant_id)
    if search:
        q = q.where(Court.name.ilike(f"%{search}%"))
    if state:
        q = q.where(Court.state == state)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).order_by(Court.name))
    items = [CourtResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/{court_id}", response_model=CourtResponse)
async def get_court(
    court_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("courts:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(Court).where(Court.id == court_id, Court.tenant_id == user.tenant_id)
    )
    court = result.scalar_one_or_none()
    if not court:
        raise HTTPException(status_code=404, detail="Court not found")
    return CourtResponse.model_validate(court)


@router.post("", response_model=CourtResponse, status_code=status.HTTP_201_CREATED)
async def create_court(
    body: CourtCreate,
    user: Annotated[CurrentUser, Depends(require_permission("courts:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    court = Court(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(court)
    await session.flush()
    await session.refresh(court)
    return CourtResponse.model_validate(court)


@router.patch("/{court_id}", response_model=CourtResponse)
async def update_court(
    court_id: str,
    body: CourtUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("courts:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(Court).where(Court.id == court_id, Court.tenant_id == user.tenant_id)
    )
    court = result.scalar_one_or_none()
    if not court:
        raise HTTPException(status_code=404, detail="Court not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(court, k, v)
    await session.flush()
    await session.refresh(court)
    return CourtResponse.model_validate(court)


@router.delete("/{court_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_court(
    court_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("courts:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(Court).where(Court.id == court_id, Court.tenant_id == user.tenant_id)
    )
    court = result.scalar_one_or_none()
    if not court:
        raise HTTPException(status_code=404, detail="Court not found")
    await session.delete(court)
    await session.flush()


@router.get("/{court_id}/costs", response_model=list[CourtCostOverrideResponse])
async def list_cost_overrides(
    court_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("courts:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(CourtCostOverride).where(CourtCostOverride.court_id == court_id, CourtCostOverride.tenant_id == user.tenant_id)
    )
    return [CourtCostOverrideResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/{court_id}/costs", response_model=CourtCostOverrideResponse, status_code=status.HTTP_201_CREATED)
async def create_cost_override(
    court_id: str,
    body: CourtCostOverrideCreate,
    user: Annotated[CurrentUser, Depends(require_permission("courts:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    override = CourtCostOverride(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(override)
    await session.flush()
    await session.refresh(override)
    return CourtCostOverrideResponse.model_validate(override)


@router.get("/{court_id}/representatives", response_model=list[CourtRepresentativeResponse])
async def list_representatives(
    court_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("courts:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(CourtRepresentative).where(CourtRepresentative.court_id == court_id, CourtRepresentative.tenant_id == user.tenant_id)
    )
    return [CourtRepresentativeResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/{court_id}/representatives", response_model=CourtRepresentativeResponse, status_code=status.HTTP_201_CREATED)
async def create_representative(
    court_id: str,
    body: CourtRepresentativeCreate,
    user: Annotated[CurrentUser, Depends(require_permission("courts:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    rep = CourtRepresentative(**body.model_dump(), tenant_id=user.tenant_id)
    session.add(rep)
    await session.flush()
    await session.refresh(rep)
    return CourtRepresentativeResponse.model_validate(rep)
