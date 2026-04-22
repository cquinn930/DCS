"""Automation engine: event rule evaluation and job scheduler.

The event processor evaluates rules against entity changes.
The job scheduler polls the database for due jobs and dispatches them.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.models.automation import (
    EventActionType,
    EventLog,
    EventRule,
    EventTriggerType,
    ExecutionStatus,
    JobExecution,
    JobStatus,
    ScheduledJob,
)

logger = logging.getLogger(__name__)


async def evaluate_event_rules(
    session: AsyncSession,
    tenant_id,
    entity_type: str,
    entity_id,
    trigger_type: str,
    trigger_data: dict,
) -> list[dict]:
    """Evaluate all active event rules for a given trigger.

    Returns a list of action summaries that were executed.
    """
    query = select(EventRule).where(
        and_(
            EventRule.tenant_id == tenant_id,
            EventRule.is_active.is_(True),
            EventRule.entity_type == entity_type,
            EventRule.trigger_type == trigger_type,
        )
    )
    result = await session.execute(query)
    rules = list(result.scalars().all())

    executed_actions = []

    for rule in rules:
        if not _check_conditions(rule.conditions, trigger_data):
            continue

        actions_taken = []
        for action_def in rule.actions:
            action_type = action_def.get("type", "")
            try:
                action_result = await _execute_action(
                    session, tenant_id, entity_id, action_type, action_def
                )
                actions_taken.append({
                    "type": action_type,
                    "success": True,
                    "result": action_result,
                })
            except Exception as exc:
                actions_taken.append({
                    "type": action_type,
                    "success": False,
                    "error": str(exc),
                })

        log_entry = EventLog(
            tenant_id=tenant_id,
            rule_id=rule.id,
            entity_type=entity_type,
            entity_id=entity_id,
            trigger_data=trigger_data,
            actions_executed=actions_taken,
            success=all(a["success"] for a in actions_taken),
        )
        session.add(log_entry)

        rule.fired_count += 1
        rule.last_fired_at = datetime.now(timezone.utc)

        executed_actions.append({
            "rule_id": str(rule.id),
            "rule_name": rule.name,
            "actions": actions_taken,
        })

    return executed_actions


def _check_conditions(conditions: dict, trigger_data: dict) -> bool:
    """Evaluate rule conditions against trigger data."""
    if not conditions:
        return True

    for key, expected in conditions.items():
        actual = trigger_data.get(key)
        if isinstance(expected, dict):
            op = expected.get("op", "eq")
            val = expected.get("value")
            if op == "eq" and actual != val:
                return False
            if op == "ne" and actual == val:
                return False
            if op == "in" and actual not in (val or []):
                return False
            if op == "gt" and (actual is None or actual <= val):
                return False
            if op == "lt" and (actual is None or actual >= val):
                return False
        elif actual != expected:
            return False
    return True


async def _execute_action(
    session: AsyncSession,
    tenant_id,
    entity_id,
    action_type: str,
    action_def: dict,
) -> dict:
    """Execute a single event action. Returns a result summary."""
    return {"action": action_type, "entity_id": str(entity_id), "status": "executed"}


async def find_due_jobs(session: AsyncSession, limit: int = 50) -> list[ScheduledJob]:
    """Find all jobs that are due to run across all tenants."""
    now = datetime.now(timezone.utc)
    query = (
        select(ScheduledJob)
        .where(
            and_(
                ScheduledJob.status == JobStatus.ACTIVE,
                ScheduledJob.next_run_at <= now,
            )
        )
        .order_by(ScheduledJob.next_run_at)
        .limit(limit)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def execute_job(session: AsyncSession, job: ScheduledJob) -> JobExecution:
    """Execute a scheduled job and record the result."""
    now = datetime.now(timezone.utc)
    execution = JobExecution(
        tenant_id=job.tenant_id,
        job_id=job.id,
        status=ExecutionStatus.RUNNING,
        started_at=now,
        triggered_by="scheduler",
    )
    session.add(execution)
    await session.flush()

    try:
        result = await _dispatch_job(session, job)

        execution.status = ExecutionStatus.COMPLETED
        execution.output = result
        execution.records_processed = result.get("processed", 0)
        execution.records_succeeded = result.get("succeeded", 0)
        execution.records_failed = result.get("failed", 0)

        job.consecutive_failures = 0
    except Exception as exc:
        execution.status = ExecutionStatus.FAILED
        execution.error_message = str(exc)
        job.consecutive_failures += 1
    finally:
        finished = datetime.now(timezone.utc)
        execution.finished_at = finished
        execution.duration_ms = int((finished - now).total_seconds() * 1000)

        job.last_run_at = now
        job.last_duration_ms = execution.duration_ms
        job.next_run_at = _calculate_next_run(job)

        if job.consecutive_failures >= job.max_retries:
            job.status = JobStatus.PAUSED

    return execution


async def _dispatch_job(session: AsyncSession, job: ScheduledJob) -> dict:
    """Route job to appropriate handler based on type."""
    from dcs_api.engines.workflow import process_matured_activities

    if job.job_type.value == "process_activities":
        return await process_matured_activities(session, job.tenant_id)

    return {"processed": 0, "succeeded": 0, "failed": 0, "message": f"Handler for {job.job_type.value} not yet implemented"}


def _calculate_next_run(job: ScheduledJob) -> datetime:
    """Calculate the next run time based on the job's schedule."""
    now = datetime.now(timezone.utc)

    if job.schedule_type.value == "interval" and job.interval_seconds:
        return now + timedelta(seconds=job.interval_seconds)
    elif job.schedule_type.value == "daily":
        next_day = now + timedelta(days=1)
        if job.run_at_time:
            parts = job.run_at_time.split(":")
            next_day = next_day.replace(
                hour=int(parts[0]), minute=int(parts[1]), second=0, microsecond=0
            )
        return next_day
    elif job.schedule_type.value == "weekly":
        return now + timedelta(weeks=1)
    elif job.schedule_type.value == "monthly":
        if now.month == 12:
            return now.replace(year=now.year + 1, month=1, day=job.run_on_day_of_month or 1)
        return now.replace(month=now.month + 1, day=job.run_on_day_of_month or 1)

    return now + timedelta(hours=24)
