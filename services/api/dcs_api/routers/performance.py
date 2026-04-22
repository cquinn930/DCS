"""Collector performance, goals, and snapshot endpoints."""

import uuid
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.performance import CollectorGoal, GoalGroup, PerformanceSnapshot
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.performance import (
    CollectorGoalCreate,
    CollectorGoalResponse,
    CollectorGoalUpdate,
    GoalGroupCreate,
    GoalGroupResponse,
    GoalGroupUpdate,
    PerformanceSnapshotCreate,
    PerformanceSnapshotResponse,
    PerformanceSnapshotUpdate,
)

router = APIRouter()
MAX_PAGE_SIZE = 100


class PerformanceSummaryResponse(BaseModel):
    """Aggregated collector performance stats for the tenant scope."""

    tenant_id: uuid.UUID
    generated_at: datetime
    distinct_collectors: int = Field(ge=0)
    snapshot_rows: int = Field(ge=0)
    total_collected_cents: int
    total_calls_made: int = Field(ge=0)
    total_accounts_worked: int = Field(ge=0)
    goal_rows: int = Field(ge=0)
    goals_met_or_exceeded: int = Field(ge=0)


@router.get(
    "/goal-groups",
    response_model=PaginatedResponse[GoalGroupResponse],
)
async def list_goal_groups(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:view"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[GoalGroupResponse]:
    """List goal groups."""
    base = select(GoalGroup)
    if not user.is_master:
        base = base.where(GoalGroup.tenant_id == user.tenant_id)
    count_q = select(func.count()).select_from(GoalGroup)
    if not user.is_master:
        count_q = count_q.where(GoalGroup.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = base.order_by(GoalGroup.name).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[GoalGroupResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.post(
    "/goal-groups",
    response_model=GoalGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_goal_group(
    data: GoalGroupCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:manage"))],
) -> GoalGroupResponse:
    """Create a goal group."""
    row = GoalGroup(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        filter_criteria=data.filter_criteria,
        is_active=data.is_active,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return GoalGroupResponse.model_validate(row)


@router.get("/goal-groups/{goal_group_id}", response_model=GoalGroupResponse)
async def get_goal_group(
    goal_group_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:view"))],
) -> GoalGroupResponse:
    """Get goal group by ID."""
    q = select(GoalGroup).where(GoalGroup.id == goal_group_id)
    if not user.is_master:
        q = q.where(GoalGroup.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal group not found")
    return GoalGroupResponse.model_validate(row)


@router.patch("/goal-groups/{goal_group_id}", response_model=GoalGroupResponse)
async def update_goal_group(
    goal_group_id: uuid.UUID,
    data: GoalGroupUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:manage"))],
) -> GoalGroupResponse:
    """Update a goal group."""
    q = select(GoalGroup).where(GoalGroup.id == goal_group_id)
    if not user.is_master:
        q = q.where(GoalGroup.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal group not found")
    payload = data.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(row, k, v)
    await session.flush()
    await session.refresh(row)
    return GoalGroupResponse.model_validate(row)


@router.delete("/goal-groups/{goal_group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal_group(
    goal_group_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:manage"))],
) -> None:
    """Delete a goal group."""
    q = select(GoalGroup).where(GoalGroup.id == goal_group_id)
    if not user.is_master:
        q = q.where(GoalGroup.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal group not found")
    await session.delete(row)


@router.get(
    "/collector-goals",
    response_model=PaginatedResponse[CollectorGoalResponse],
)
async def list_collector_goals(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:view"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    collector_id: uuid.UUID | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> PaginatedResponse[CollectorGoalResponse]:
    """List collector goals; filter by collector and/or period overlap."""
    base = select(CollectorGoal)
    if not user.is_master:
        base = base.where(CollectorGoal.tenant_id == user.tenant_id)
    if collector_id:
        base = base.where(CollectorGoal.collector_id == collector_id)
    if period_start is not None:
        base = base.where(CollectorGoal.period_end >= period_start)
    if period_end is not None:
        base = base.where(CollectorGoal.period_start <= period_end)
    count_q = select(func.count()).select_from(CollectorGoal)
    if not user.is_master:
        count_q = count_q.where(CollectorGoal.tenant_id == user.tenant_id)
    if collector_id:
        count_q = count_q.where(CollectorGoal.collector_id == collector_id)
    if period_start is not None:
        count_q = count_q.where(CollectorGoal.period_end >= period_start)
    if period_end is not None:
        count_q = count_q.where(CollectorGoal.period_start <= period_end)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = base.order_by(CollectorGoal.period_start.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[CollectorGoalResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.post(
    "/collector-goals",
    response_model=CollectorGoalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_collector_goal(
    data: CollectorGoalCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:manage"))],
) -> CollectorGoalResponse:
    """Create a collector goal."""
    row = CollectorGoal(
        tenant_id=user.tenant_id,
        collector_id=data.collector_id,
        goal_group_id=data.goal_group_id,
        goal_type=data.goal_type,
        period=data.period,
        target_amount=data.target_amount,
        actual_amount=data.actual_amount,
        goal_factor=data.goal_factor,
        period_start=data.period_start,
        period_end=data.period_end,
        notes=data.notes,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return CollectorGoalResponse.model_validate(row)


@router.get("/collector-goals/{goal_id}", response_model=CollectorGoalResponse)
async def get_collector_goal(
    goal_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:view"))],
) -> CollectorGoalResponse:
    """Get collector goal by ID."""
    q = select(CollectorGoal).where(CollectorGoal.id == goal_id)
    if not user.is_master:
        q = q.where(CollectorGoal.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collector goal not found")
    return CollectorGoalResponse.model_validate(row)


@router.patch("/collector-goals/{goal_id}", response_model=CollectorGoalResponse)
async def update_collector_goal(
    goal_id: uuid.UUID,
    data: CollectorGoalUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:manage"))],
) -> CollectorGoalResponse:
    """Update a collector goal."""
    q = select(CollectorGoal).where(CollectorGoal.id == goal_id)
    if not user.is_master:
        q = q.where(CollectorGoal.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collector goal not found")
    payload = data.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(row, k, v)
    await session.flush()
    await session.refresh(row)
    return CollectorGoalResponse.model_validate(row)


@router.delete("/collector-goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collector_goal(
    goal_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:manage"))],
) -> None:
    """Delete a collector goal."""
    q = select(CollectorGoal).where(CollectorGoal.id == goal_id)
    if not user.is_master:
        q = q.where(CollectorGoal.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collector goal not found")
    await session.delete(row)


@router.get(
    "/snapshots",
    response_model=PaginatedResponse[PerformanceSnapshotResponse],
)
async def list_performance_snapshots(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:view"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    collector_id: uuid.UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> PaginatedResponse[PerformanceSnapshotResponse]:
    """List performance snapshots; filter by collector and snapshot date range."""
    base = select(PerformanceSnapshot)
    if not user.is_master:
        base = base.where(PerformanceSnapshot.tenant_id == user.tenant_id)
    if collector_id:
        base = base.where(PerformanceSnapshot.collector_id == collector_id)
    if start_date is not None:
        base = base.where(PerformanceSnapshot.snapshot_date >= start_date)
    if end_date is not None:
        base = base.where(PerformanceSnapshot.snapshot_date <= end_date)
    count_q = select(func.count()).select_from(PerformanceSnapshot)
    if not user.is_master:
        count_q = count_q.where(PerformanceSnapshot.tenant_id == user.tenant_id)
    if collector_id:
        count_q = count_q.where(PerformanceSnapshot.collector_id == collector_id)
    if start_date is not None:
        count_q = count_q.where(PerformanceSnapshot.snapshot_date >= start_date)
    if end_date is not None:
        count_q = count_q.where(PerformanceSnapshot.snapshot_date <= end_date)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = base.order_by(PerformanceSnapshot.snapshot_date.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[PerformanceSnapshotResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.post(
    "/snapshots",
    response_model=PerformanceSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_performance_snapshot(
    data: PerformanceSnapshotCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:manage"))],
) -> PerformanceSnapshotResponse:
    """Create a performance snapshot."""
    row = PerformanceSnapshot(
        tenant_id=user.tenant_id,
        collector_id=data.collector_id,
        snapshot_date=data.snapshot_date,
        accounts_worked=data.accounts_worked,
        calls_made=data.calls_made,
        calls_connected=data.calls_connected,
        promises_obtained=data.promises_obtained,
        payments_secured=data.payments_secured,
        total_collected=data.total_collected,
        activities_completed=data.activities_completed,
        documents_generated=data.documents_generated,
        queue_depth_start=data.queue_depth_start,
        queue_depth_end=data.queue_depth_end,
        extra_metrics=data.extra_metrics,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return PerformanceSnapshotResponse.model_validate(row)


@router.get("/snapshots/{snapshot_id}", response_model=PerformanceSnapshotResponse)
async def get_performance_snapshot(
    snapshot_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:view"))],
) -> PerformanceSnapshotResponse:
    """Get performance snapshot by ID."""
    q = select(PerformanceSnapshot).where(PerformanceSnapshot.id == snapshot_id)
    if not user.is_master:
        q = q.where(PerformanceSnapshot.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
    return PerformanceSnapshotResponse.model_validate(row)


@router.patch("/snapshots/{snapshot_id}", response_model=PerformanceSnapshotResponse)
async def update_performance_snapshot(
    snapshot_id: uuid.UUID,
    data: PerformanceSnapshotUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:manage"))],
) -> PerformanceSnapshotResponse:
    """Update a performance snapshot."""
    q = select(PerformanceSnapshot).where(PerformanceSnapshot.id == snapshot_id)
    if not user.is_master:
        q = q.where(PerformanceSnapshot.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
    payload = data.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(row, k, v)
    await session.flush()
    await session.refresh(row)
    return PerformanceSnapshotResponse.model_validate(row)


@router.delete("/snapshots/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_performance_snapshot(
    snapshot_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:manage"))],
) -> None:
    """Delete a performance snapshot."""
    q = select(PerformanceSnapshot).where(PerformanceSnapshot.id == snapshot_id)
    if not user.is_master:
        q = q.where(PerformanceSnapshot.tenant_id == user.tenant_id)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
    await session.delete(row)


@router.get("/summary", response_model=PerformanceSummaryResponse)
async def performance_summary(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("performance:view"))],
    collector_id: uuid.UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> PerformanceSummaryResponse:
    """Aggregate collector performance statistics."""
    snap_q = select(
        func.count(func.distinct(PerformanceSnapshot.collector_id)),
        func.count(PerformanceSnapshot.id),
        func.coalesce(func.sum(PerformanceSnapshot.total_collected), 0),
        func.coalesce(func.sum(PerformanceSnapshot.calls_made), 0),
        func.coalesce(func.sum(PerformanceSnapshot.accounts_worked), 0),
    )
    if not user.is_master:
        snap_q = snap_q.where(PerformanceSnapshot.tenant_id == user.tenant_id)
    if collector_id:
        snap_q = snap_q.where(PerformanceSnapshot.collector_id == collector_id)
    if start_date is not None:
        snap_q = snap_q.where(PerformanceSnapshot.snapshot_date >= start_date)
    if end_date is not None:
        snap_q = snap_q.where(PerformanceSnapshot.snapshot_date <= end_date)
    snap_row = (await session.execute(snap_q)).one()

    goal_base = select(CollectorGoal)
    if not user.is_master:
        goal_base = goal_base.where(CollectorGoal.tenant_id == user.tenant_id)
    if collector_id:
        goal_base = goal_base.where(CollectorGoal.collector_id == collector_id)
    if start_date is not None:
        goal_base = goal_base.where(CollectorGoal.period_end >= start_date)
    if end_date is not None:
        goal_base = goal_base.where(CollectorGoal.period_start <= end_date)
    goal_rows = list((await session.execute(goal_base)).scalars().all())
    goal_count = len(goal_rows)
    goals_met = sum(1 for g in goal_rows if g.actual_amount >= g.target_amount)

    return PerformanceSummaryResponse(
        tenant_id=user.tenant_id,
        generated_at=datetime.now(timezone.utc),
        distinct_collectors=int(snap_row[0] or 0),
        snapshot_rows=int(snap_row[1] or 0),
        total_collected_cents=int(snap_row[2] or 0),
        total_calls_made=int(snap_row[3] or 0),
        total_accounts_worked=int(snap_row[4] or 0),
        goal_rows=goal_count,
        goals_met_or_exceeded=goals_met,
    )
