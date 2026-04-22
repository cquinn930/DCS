"""SubPlan API routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.rbac import CurrentUser, Permissions, require_permission
from dcs_api.database import get_session
from dcs_api.models.subplans import SubPlan, SubPlanStep
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.subplans import (
    SubPlanCreate,
    SubPlanResponse,
    SubPlanStepCreate,
    SubPlanStepResponse,
    SubPlanUpdate,
)

router = APIRouter()
MAX_PAGE_SIZE = 100


@router.get("", response_model=PaginatedResponse[SubPlanResponse])
async def list_subplans(
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    category: str | None = None,
):
    q = select(SubPlan).where(SubPlan.tenant_id == user.tenant_id)
    if category:
        q = q.where(SubPlan.category == category)
    total_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    rows = await session.execute(q.offset(offset).limit(page_size).options(selectinload(SubPlan.steps)).order_by(SubPlan.name))
    items = [SubPlanResponse.model_validate(r) for r in rows.scalars().all()]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/{subplan_id}", response_model=SubPlanResponse)
async def get_subplan(
    subplan_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(SubPlan).where(SubPlan.id == subplan_id, SubPlan.tenant_id == user.tenant_id)
        .options(selectinload(SubPlan.steps))
    )
    sp = result.scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="SubPlan not found")
    return SubPlanResponse.model_validate(sp)


@router.post("", response_model=SubPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_subplan(
    body: SubPlanCreate,
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    steps_data = body.steps
    sp = SubPlan(**body.model_dump(exclude={"steps"}), tenant_id=user.tenant_id)
    session.add(sp)
    await session.flush()
    for step_data in steps_data:
        step = SubPlanStep(**step_data.model_dump(), sub_plan_id=sp.id, tenant_id=user.tenant_id)
        session.add(step)
    await session.flush()
    result = await session.execute(
        select(SubPlan).where(SubPlan.id == sp.id).options(selectinload(SubPlan.steps))
    )
    return SubPlanResponse.model_validate(result.scalar_one())


@router.patch("/{subplan_id}", response_model=SubPlanResponse)
async def update_subplan(
    subplan_id: str,
    body: SubPlanUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(SubPlan).where(SubPlan.id == subplan_id, SubPlan.tenant_id == user.tenant_id)
    )
    sp = result.scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="SubPlan not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(sp, k, v)
    await session.flush()
    await session.refresh(sp)
    return SubPlanResponse.model_validate(sp)


@router.delete("/{subplan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subplan(
    subplan_id: str,
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(SubPlan).where(SubPlan.id == subplan_id, SubPlan.tenant_id == user.tenant_id)
    )
    sp = result.scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="SubPlan not found")
    await session.delete(sp)
    await session.flush()


@router.post("/{subplan_id}/steps", response_model=SubPlanStepResponse, status_code=status.HTTP_201_CREATED)
async def add_step(
    subplan_id: str,
    body: SubPlanStepCreate,
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(SubPlan).where(SubPlan.id == subplan_id, SubPlan.tenant_id == user.tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="SubPlan not found")
    step = SubPlanStep(**body.model_dump(), sub_plan_id=subplan_id, tenant_id=user.tenant_id)
    session.add(step)
    await session.flush()
    await session.refresh(step)
    return SubPlanStepResponse.model_validate(step)
