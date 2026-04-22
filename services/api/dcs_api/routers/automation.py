"""Event rules, event logs, and scheduled job endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.automation import (
    EventLog,
    EventRule,
    ExecutionStatus,
    JobExecution,
    ScheduledJob,
)
from dcs_api.schemas.automation import (
    EventLogResponse,
    EventRuleCreate,
    EventRuleResponse,
    EventRuleUpdate,
    JobExecutionResponse,
    ScheduledJobCreate,
    ScheduledJobResponse,
    ScheduledJobUpdate,
)
from dcs_api.schemas.common import PaginatedResponse

router = APIRouter()

MAX_PAGE_SIZE = 100

PERM = "automation:manage"


async def _get_event_rule(
    session: AsyncSession, rule_id: uuid.UUID, user: CurrentUser
) -> EventRule | None:
    q = select(EventRule).where(EventRule.id == rule_id)
    if not user.is_master:
        q = q.where(EventRule.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


async def _get_scheduled_job(
    session: AsyncSession, job_id: uuid.UUID, user: CurrentUser
) -> ScheduledJob | None:
    q = select(ScheduledJob).where(ScheduledJob.id == job_id)
    if not user.is_master:
        q = q.where(ScheduledJob.tenant_id == user.tenant_id)
    r = await session.execute(q)
    return r.scalar_one_or_none()


# --- Event rules ---


@router.get("/event-rules", response_model=PaginatedResponse[EventRuleResponse])
async def list_event_rules(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    entity_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[EventRuleResponse]:
    """List event rules, optionally filtered by entity type."""
    count_q = select(func.count()).select_from(EventRule)
    if not user.is_master:
        count_q = count_q.where(EventRule.tenant_id == user.tenant_id)
    if entity_type:
        count_q = count_q.where(EventRule.entity_type == entity_type)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(EventRule)
    if not user.is_master:
        q = q.where(EventRule.tenant_id == user.tenant_id)
    if entity_type:
        q = q.where(EventRule.entity_type == entity_type)
    q = q.order_by(EventRule.priority, EventRule.name).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[EventRuleResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/event-rules/{rule_id}", response_model=EventRuleResponse)
async def get_event_rule(
    rule_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> EventRuleResponse:
    """Get an event rule by ID."""
    rule = await _get_event_rule(session, rule_id, user)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event rule not found")
    return EventRuleResponse.model_validate(rule)


@router.post("/event-rules", response_model=EventRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_event_rule(
    data: EventRuleCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> EventRuleResponse:
    """Create an event rule."""
    rule = EventRule(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        entity_type=data.entity_type,
        field_name=data.field_name,
        trigger_type=data.trigger_type,
        conditions=data.conditions,
        actions=data.actions,
        priority=data.priority,
        is_active=data.is_active,
        is_system=data.is_system,
        apply_to_closed=data.apply_to_closed,
        created_by_id=data.created_by_id or user.user_id,
    )
    session.add(rule)
    await session.flush()
    await session.refresh(rule)
    return EventRuleResponse.model_validate(rule)


@router.patch("/event-rules/{rule_id}", response_model=EventRuleResponse)
async def update_event_rule(
    rule_id: uuid.UUID,
    data: EventRuleUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> EventRuleResponse:
    """Update an event rule."""
    rule = await _get_event_rule(session, rule_id, user)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event rule not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    await session.flush()
    return EventRuleResponse.model_validate(rule)


# --- Event logs (read-only) ---


@router.get("/event-logs", response_model=PaginatedResponse[EventLogResponse])
async def list_event_logs(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    rule_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[EventLogResponse]:
    """List event logs (read-only)."""
    count_q = select(func.count()).select_from(EventLog)
    if not user.is_master:
        count_q = count_q.where(EventLog.tenant_id == user.tenant_id)
    if rule_id:
        count_q = count_q.where(EventLog.rule_id == rule_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(EventLog)
    if not user.is_master:
        q = q.where(EventLog.tenant_id == user.tenant_id)
    if rule_id:
        q = q.where(EventLog.rule_id == rule_id)
    q = q.order_by(EventLog.created_at.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[EventLogResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/event-logs/{log_id}", response_model=EventLogResponse)
async def get_event_log(
    log_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> EventLogResponse:
    """Get a single event log entry (read-only)."""
    q = select(EventLog).where(EventLog.id == log_id)
    if not user.is_master:
        q = q.where(EventLog.tenant_id == user.tenant_id)
    r = await session.execute(q)
    log = r.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event log not found")
    return EventLogResponse.model_validate(log)


# --- Scheduled jobs ---


@router.get("/scheduled-jobs", response_model=PaginatedResponse[ScheduledJobResponse])
async def list_scheduled_jobs(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[ScheduledJobResponse]:
    """List scheduled jobs (interval_seconds, run_at_time, run_on_days — no cron)."""
    count_q = select(func.count()).select_from(ScheduledJob)
    if not user.is_master:
        count_q = count_q.where(ScheduledJob.tenant_id == user.tenant_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(ScheduledJob)
    if not user.is_master:
        q = q.where(ScheduledJob.tenant_id == user.tenant_id)
    q = q.order_by(ScheduledJob.name).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[ScheduledJobResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/scheduled-jobs/{job_id}", response_model=ScheduledJobResponse)
async def get_scheduled_job(
    job_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> ScheduledJobResponse:
    """Get a scheduled job by ID."""
    job = await _get_scheduled_job(session, job_id, user)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled job not found")
    return ScheduledJobResponse.model_validate(job)


@router.post("/scheduled-jobs", response_model=ScheduledJobResponse, status_code=status.HTTP_201_CREATED)
async def create_scheduled_job(
    data: ScheduledJobCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> ScheduledJobResponse:
    """Create a scheduled job."""
    job = ScheduledJob(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        job_type=data.job_type,
        schedule_type=data.schedule_type,
        interval_seconds=data.interval_seconds,
        run_at_time=data.run_at_time,
        run_on_days=data.run_on_days,
        run_on_day_of_month=data.run_on_day_of_month,
        timezone=data.timezone,
        status=data.status,
        parameters=data.parameters,
        last_run_at=data.last_run_at,
        next_run_at=data.next_run_at,
        last_duration_ms=data.last_duration_ms,
        consecutive_failures=data.consecutive_failures,
        max_retries=data.max_retries,
        created_by_id=data.created_by_id or user.user_id,
        is_system=data.is_system,
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)
    return ScheduledJobResponse.model_validate(job)


@router.patch("/scheduled-jobs/{job_id}", response_model=ScheduledJobResponse)
async def update_scheduled_job(
    job_id: uuid.UUID,
    data: ScheduledJobUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> ScheduledJobResponse:
    """Update a scheduled job."""
    job = await _get_scheduled_job(session, job_id, user)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled job not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(job, k, v)
    await session.flush()
    return ScheduledJobResponse.model_validate(job)


# --- Job executions (read-only) + manual trigger ---


@router.get("/job-executions", response_model=PaginatedResponse[JobExecutionResponse])
async def list_job_executions(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
    job_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponse[JobExecutionResponse]:
    """List job executions (read-only)."""
    count_q = select(func.count()).select_from(JobExecution)
    if not user.is_master:
        count_q = count_q.where(JobExecution.tenant_id == user.tenant_id)
    if job_id:
        count_q = count_q.where(JobExecution.job_id == job_id)
    total = (await session.execute(count_q)).scalar_one()
    offset = (page - 1) * page_size
    q = select(JobExecution)
    if not user.is_master:
        q = q.where(JobExecution.tenant_id == user.tenant_id)
    if job_id:
        q = q.where(JobExecution.job_id == job_id)
    q = q.order_by(JobExecution.started_at.desc()).offset(offset).limit(page_size)
    rows = list((await session.execute(q)).scalars().all())
    return PaginatedResponse(
        items=[JobExecutionResponse.model_validate(x) for x in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/job-executions/{execution_id}", response_model=JobExecutionResponse)
async def get_job_execution(
    execution_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> JobExecutionResponse:
    """Get a job execution by ID (read-only)."""
    q = select(JobExecution).where(JobExecution.id == execution_id)
    if not user.is_master:
        q = q.where(JobExecution.tenant_id == user.tenant_id)
    r = await session.execute(q)
    ex = r.scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job execution not found")
    return JobExecutionResponse.model_validate(ex)


@router.post("/scheduled-jobs/{job_id}/trigger", response_model=JobExecutionResponse)
async def trigger_scheduled_job(
    job_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(PERM))],
) -> JobExecutionResponse:
    """Manually enqueue a job run (creates an execution record)."""
    job = await _get_scheduled_job(session, job_id, user)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled job not found")

    now = datetime.now(timezone.utc)
    ex = JobExecution(
        tenant_id=job.tenant_id,
        job_id=job.id,
        status=ExecutionStatus.RUNNING,
        started_at=now,
        finished_at=None,
        duration_ms=None,
        records_processed=0,
        records_succeeded=0,
        records_failed=0,
        output={},
        error_message=None,
        error_trace=None,
        triggered_by="manual",
    )
    session.add(ex)
    await session.flush()
    await session.refresh(ex)
    return JobExecutionResponse.model_validate(ex)