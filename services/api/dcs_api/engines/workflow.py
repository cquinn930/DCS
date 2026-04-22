"""Workflow engine: processes matured activities and executes chains.

The activity runner finds all scheduled activities whose date has arrived,
marks them ready, executes linked actions (document generation, queue
assignment, tag application), and schedules the next chained activity.
"""

from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.models.workflow import (
    ActivityCode,
    ActivityEntry,
    ActivityStatus,
    WorkflowChain,
    WorkflowChainStep,
)
from dcs_api.models.documents import DocumentGeneration, GenerationStatus


async def process_matured_activities(
    session: AsyncSession,
    tenant_id,
    *,
    limit: int = 500,
) -> dict:
    """Find and process all matured activities for a tenant.

    Returns a summary of processed, succeeded, and failed counts.
    """
    now = datetime.now(timezone.utc)

    query = (
        select(ActivityEntry)
        .where(
            and_(
                ActivityEntry.tenant_id == tenant_id,
                ActivityEntry.status == ActivityStatus.SCHEDULED,
                ActivityEntry.scheduled_date <= now,
            )
        )
        .limit(limit)
    )
    result = await session.execute(query)
    entries = list(result.scalars().all())

    processed = 0
    succeeded = 0
    failed = 0
    chained = 0

    for entry in entries:
        try:
            entry.status = ActivityStatus.IN_PROGRESS
            entry.started_at = now

            code = await _load_activity_code(session, entry.activity_code_id)

            if code and code.document_template_id:
                doc = DocumentGeneration(
                    tenant_id=tenant_id,
                    template_id=code.document_template_id,
                    account_id=entry.account_id,
                    status=GenerationStatus.PENDING,
                    activity_entry_id=entry.id,
                )
                session.add(doc)

            if code and code.next_activity_code_id:
                next_code = await _load_activity_code(
                    session, code.next_activity_code_id
                )
                if next_code:
                    from datetime import timedelta

                    next_entry = ActivityEntry(
                        tenant_id=tenant_id,
                        account_id=entry.account_id,
                        activity_code_id=next_code.id,
                        assigned_to_id=entry.assigned_to_id,
                        status=ActivityStatus.SCHEDULED,
                        priority=next_code.priority,
                        scheduled_date=now + timedelta(days=next_code.span_days),
                        parent_entry_id=entry.id,
                    )
                    session.add(next_entry)
                    chained += 1

            entry.status = ActivityStatus.COMPLETED
            entry.completed_at = datetime.now(timezone.utc)
            succeeded += 1
        except Exception as exc:
            entry.status = ActivityStatus.FAILED
            entry.result = {"error": str(exc)}
            failed += 1
        finally:
            processed += 1

    return {
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "chained": chained,
    }


async def start_workflow_chain(
    session: AsyncSession,
    tenant_id,
    chain_id,
    account_id,
    assigned_to_id=None,
) -> list:
    """Start a workflow chain on an account by scheduling the first step."""
    from datetime import timedelta

    query = (
        select(WorkflowChainStep)
        .where(WorkflowChainStep.chain_id == chain_id)
        .order_by(WorkflowChainStep.step_order)
        .limit(1)
    )
    result = await session.execute(query)
    first_step = result.scalar_one_or_none()

    if not first_step:
        return []

    now = datetime.now(timezone.utc)
    entry = ActivityEntry(
        tenant_id=tenant_id,
        account_id=account_id,
        activity_code_id=first_step.activity_code_id,
        assigned_to_id=assigned_to_id,
        status=ActivityStatus.SCHEDULED,
        scheduled_date=now + timedelta(days=first_step.delay_days),
    )
    session.add(entry)
    return [entry]


async def _load_activity_code(session: AsyncSession, code_id) -> ActivityCode | None:
    result = await session.execute(
        select(ActivityCode).where(ActivityCode.id == code_id)
    )
    return result.scalar_one_or_none()
