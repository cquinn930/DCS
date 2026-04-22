"""Workflow, activity, and queue endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.rbac import CurrentUser, require_permission
from dcs_api.database import get_session
from dcs_api.models.account import Account
from dcs_api.models.workflow import (
    ActivityCode,
    ActivityEntry,
    ActivityStatus,
    QueueEntry,
    QueueEntryStatus,
    WorkflowChain,
    WorkflowChainStep,
    WorkQueue,
)
from dcs_api.schemas.common import PaginatedResponse
from dcs_api.schemas.workflow import (
    ActivityCodeCreate,
    ActivityCodeResponse,
    ActivityCodeUpdate,
    ActivityEntryCreate,
    ActivityEntryResponse,
    ActivityEntryUpdate,
    ProcessMaturedResponse,
    QueueEntryCreate,
    QueueEntryResponse,
    QueueEntryUpdate,
    WorkflowChainCreate,
    WorkflowChainResponse,
    WorkflowChainStepResponse,
    WorkflowChainUpdate,
    WorkQueueCreate,
    WorkQueueResponse,
    WorkQueueUpdate,
)

router = APIRouter()

MAX_PAGE_SIZE = 100


def _chain_to_response(chain: WorkflowChain) -> WorkflowChainResponse:
    steps = sorted(chain.steps, key=lambda s: s.step_order)
    return WorkflowChainResponse(
        id=chain.id,
        tenant_id=chain.tenant_id,
        name=chain.name,
        description=chain.description,
        is_active=chain.is_active,
        is_system=chain.is_system,
        created_at=chain.created_at,
        updated_at=chain.updated_at,
        steps=[WorkflowChainStepResponse.model_validate(s) for s in steps],
    )


# --- Activity codes ---


@router.get("/activity-codes", response_model=PaginatedResponse[ActivityCodeResponse])
async def list_activity_codes(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("activities:manage"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    is_active: bool | None = None,
) -> PaginatedResponse[ActivityCodeResponse]:
    """List activity codes."""
    query = select(ActivityCode).where(ActivityCode.tenant_id == user.tenant_id)
    if is_active is not None:
        query = query.where(ActivityCode.is_active == is_active)

    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(ActivityCode.code)
    result = await session.execute(query)
    rows = list(result.scalars().all())

    return PaginatedResponse(
        items=[ActivityCodeResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/activity-codes/{code_id}", response_model=ActivityCodeResponse)
async def get_activity_code(
    code_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("activities:manage"))],
) -> ActivityCodeResponse:
    """Get activity code by ID."""
    query = select(ActivityCode).where(
        ActivityCode.id == code_id,
        ActivityCode.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity code not found")
    return ActivityCodeResponse.model_validate(row)


@router.post(
    "/activity-codes",
    response_model=ActivityCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_activity_code(
    data: ActivityCodeCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("activities:manage"))],
) -> ActivityCodeResponse:
    """Create activity code."""
    code = ActivityCode(
        tenant_id=user.tenant_id,
        code=data.code,
        name=data.name,
        description=data.description,
        category=data.category,
        priority=data.priority,
        span_days=data.span_days,
        document_template_id=data.document_template_id,
        target_queue_id=data.target_queue_id,
        next_activity_code_id=data.next_activity_code_id,
        auto_execute=data.auto_execute,
        is_system=data.is_system,
        is_active=data.is_active,
        config=data.config,
    )
    session.add(code)
    await session.flush()
    await session.refresh(code)
    return ActivityCodeResponse.model_validate(code)


@router.patch("/activity-codes/{code_id}", response_model=ActivityCodeResponse)
async def update_activity_code(
    code_id: uuid.UUID,
    data: ActivityCodeUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("activities:manage"))],
) -> ActivityCodeResponse:
    """Update activity code."""
    query = select(ActivityCode).where(
        ActivityCode.id == code_id,
        ActivityCode.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity code not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await session.flush()
    await session.refresh(row)
    return ActivityCodeResponse.model_validate(row)


@router.delete("/activity-codes/{code_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity_code(
    code_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("activities:manage"))],
) -> None:
    """Delete activity code."""
    query = select(ActivityCode).where(
        ActivityCode.id == code_id,
        ActivityCode.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity code not found")
    await session.delete(row)
    await session.flush()


# --- Activity entries ---


@router.get("/activity-entries", response_model=PaginatedResponse[ActivityEntryResponse])
async def list_activity_entries(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("activities:manage"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    account_id: uuid.UUID | None = None,
    status_filter: ActivityStatus | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> PaginatedResponse[ActivityEntryResponse]:
    """List activity entries with filters."""
    query = select(ActivityEntry).where(ActivityEntry.tenant_id == user.tenant_id)
    if account_id:
        query = query.where(ActivityEntry.account_id == account_id)
    if status_filter:
        query = query.where(ActivityEntry.status == status_filter)
    if date_from:
        query = query.where(ActivityEntry.scheduled_date >= date_from)
    if date_to:
        query = query.where(ActivityEntry.scheduled_date <= date_to)

    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(ActivityEntry.scheduled_date.asc())
    result = await session.execute(query)
    rows = list(result.scalars().all())

    return PaginatedResponse(
        items=[ActivityEntryResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.post("/activity-entries/process-matured", response_model=ProcessMaturedResponse)
async def process_matured_activities(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
) -> ProcessMaturedResponse:
    """Mark scheduled activities whose scheduled date has passed as ready."""
    now = datetime.now(timezone.utc)
    q = select(ActivityEntry).where(
        ActivityEntry.tenant_id == user.tenant_id,
        ActivityEntry.status == ActivityStatus.SCHEDULED,
        ActivityEntry.scheduled_date <= now,
    )
    result = await session.execute(q)
    entries = list(result.scalars().all())
    ids: list[uuid.UUID] = []
    for entry in entries:
        entry.status = ActivityStatus.READY
        ids.append(entry.id)
    await session.flush()
    return ProcessMaturedResponse(processed_count=len(ids), entry_ids=ids)


@router.get("/activity-entries/{entry_id}", response_model=ActivityEntryResponse)
async def get_activity_entry(
    entry_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("activities:manage"))],
) -> ActivityEntryResponse:
    """Get activity entry by ID."""
    query = select(ActivityEntry).where(
        ActivityEntry.id == entry_id,
        ActivityEntry.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity entry not found")
    return ActivityEntryResponse.model_validate(row)


@router.post(
    "/activity-entries",
    response_model=ActivityEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_activity_entry(
    data: ActivityEntryCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("activities:manage"))],
) -> ActivityEntryResponse:
    """Create activity entry."""
    acc = await session.execute(
        select(Account).where(Account.id == data.account_id, Account.tenant_id == user.tenant_id)
    )
    if not acc.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    if data.activity_code_id is not None:
        ac = await session.execute(
            select(ActivityCode).where(
                ActivityCode.id == data.activity_code_id,
                ActivityCode.tenant_id == user.tenant_id,
            )
        )
        if not ac.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity code not found")

    entry = ActivityEntry(
        tenant_id=user.tenant_id,
        account_id=data.account_id,
        activity_code_id=data.activity_code_id,
        assigned_to_id=data.assigned_to_id,
        status=data.status,
        priority=data.priority,
        scheduled_date=data.scheduled_date,
        notes=data.notes,
        result=data.result,
        parent_entry_id=data.parent_entry_id,
    )
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return ActivityEntryResponse.model_validate(entry)


@router.patch("/activity-entries/{entry_id}", response_model=ActivityEntryResponse)
async def update_activity_entry(
    entry_id: uuid.UUID,
    data: ActivityEntryUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("activities:manage"))],
) -> ActivityEntryResponse:
    """Update activity entry."""
    query = select(ActivityEntry).where(
        ActivityEntry.id == entry_id,
        ActivityEntry.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity entry not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await session.flush()
    await session.refresh(row)
    return ActivityEntryResponse.model_validate(row)


@router.delete("/activity-entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity_entry(
    entry_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("activities:manage"))],
) -> None:
    """Delete activity entry."""
    query = select(ActivityEntry).where(
        ActivityEntry.id == entry_id,
        ActivityEntry.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity entry not found")
    await session.delete(row)
    await session.flush()


# --- Workflow chains ---


@router.get("/workflow-chains", response_model=PaginatedResponse[WorkflowChainResponse])
async def list_workflow_chains(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    is_active: bool | None = None,
) -> PaginatedResponse[WorkflowChainResponse]:
    """List workflow chains."""
    base = select(WorkflowChain).where(WorkflowChain.tenant_id == user.tenant_id)
    if is_active is not None:
        base = base.where(WorkflowChain.is_active == is_active)

    count_result = await session.execute(base)
    total = len(list(count_result.scalars().all()))

    offset = (page - 1) * page_size
    query = (
        base.options(selectinload(WorkflowChain.steps))
        .offset(offset)
        .limit(page_size)
        .order_by(WorkflowChain.name)
    )
    result = await session.execute(query)
    chains = list(result.scalars().all())

    return PaginatedResponse(
        items=[_chain_to_response(c) for c in chains],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/workflow-chains/{chain_id}", response_model=WorkflowChainResponse)
async def get_workflow_chain(
    chain_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
) -> WorkflowChainResponse:
    """Get workflow chain by ID."""
    query = (
        select(WorkflowChain)
        .where(WorkflowChain.id == chain_id, WorkflowChain.tenant_id == user.tenant_id)
        .options(selectinload(WorkflowChain.steps))
    )
    result = await session.execute(query)
    chain = result.scalar_one_or_none()
    if not chain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow chain not found")
    return _chain_to_response(chain)


@router.post(
    "/workflow-chains",
    response_model=WorkflowChainResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_chain(
    data: WorkflowChainCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
) -> WorkflowChainResponse:
    """Create workflow chain with steps."""
    chain = WorkflowChain(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        is_active=data.is_active,
        is_system=data.is_system,
    )
    session.add(chain)
    await session.flush()

    for step in data.steps:
        ac = await session.execute(
            select(ActivityCode).where(
                ActivityCode.id == step.activity_code_id,
                ActivityCode.tenant_id == user.tenant_id,
            )
        )
        if not ac.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activity code not found: {step.activity_code_id}",
            )
        st = WorkflowChainStep(
            tenant_id=user.tenant_id,
            chain_id=chain.id,
            activity_code_id=step.activity_code_id,
            step_order=step.step_order,
            delay_days=step.delay_days,
            condition=step.condition,
            on_failure=step.on_failure,
        )
        session.add(st)

    await session.flush()
    result = await session.execute(
        select(WorkflowChain)
        .where(WorkflowChain.id == chain.id)
        .options(selectinload(WorkflowChain.steps))
    )
    chain = result.scalar_one()
    return _chain_to_response(chain)


@router.patch("/workflow-chains/{chain_id}", response_model=WorkflowChainResponse)
async def update_workflow_chain(
    chain_id: uuid.UUID,
    data: WorkflowChainUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
) -> WorkflowChainResponse:
    """Update workflow chain metadata."""
    query = (
        select(WorkflowChain)
        .where(WorkflowChain.id == chain_id, WorkflowChain.tenant_id == user.tenant_id)
        .options(selectinload(WorkflowChain.steps))
    )
    result = await session.execute(query)
    chain = result.scalar_one_or_none()
    if not chain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow chain not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(chain, key, value)
    await session.flush()
    result = await session.execute(
        select(WorkflowChain)
        .where(WorkflowChain.id == chain.id)
        .options(selectinload(WorkflowChain.steps))
    )
    chain = result.scalar_one()
    return _chain_to_response(chain)


@router.delete("/workflow-chains/{chain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow_chain(
    chain_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("workflow:manage"))],
) -> None:
    """Delete workflow chain (cascade steps)."""
    query = select(WorkflowChain).where(
        WorkflowChain.id == chain_id,
        WorkflowChain.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    chain = result.scalar_one_or_none()
    if not chain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow chain not found")
    await session.delete(chain)
    await session.flush()


# --- Work queues ---


@router.get("/work-queues", response_model=PaginatedResponse[WorkQueueResponse])
async def list_work_queues(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("queues:manage"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    is_active: bool | None = None,
) -> PaginatedResponse[WorkQueueResponse]:
    """List work queues."""
    query = select(WorkQueue).where(WorkQueue.tenant_id == user.tenant_id)
    if is_active is not None:
        query = query.where(WorkQueue.is_active == is_active)

    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(WorkQueue.name)
    result = await session.execute(query)
    rows = list(result.scalars().all())

    return PaginatedResponse(
        items=[WorkQueueResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.get("/work-queues/{queue_id}/next", response_model=QueueEntryResponse | None)
async def get_next_queue_entry(
    queue_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("queues:manage"))],
) -> QueueEntryResponse | None:
    """Next account entry in the queue (priority desc, then entered_at asc)."""
    q = select(WorkQueue).where(WorkQueue.id == queue_id, WorkQueue.tenant_id == user.tenant_id)
    if not (await session.execute(q)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work queue not found")

    qe = (
        select(QueueEntry)
        .where(
            QueueEntry.queue_id == queue_id,
            QueueEntry.tenant_id == user.tenant_id,
            QueueEntry.status.in_(
                [QueueEntryStatus.PENDING, QueueEntryStatus.ASSIGNED, QueueEntryStatus.IN_PROGRESS]
            ),
        )
        .order_by(QueueEntry.priority.desc(), QueueEntry.entered_at.asc())
        .limit(1)
    )
    result = await session.execute(qe)
    row = result.scalar_one_or_none()
    return QueueEntryResponse.model_validate(row) if row else None


@router.get("/work-queues/{queue_id}/entries", response_model=PaginatedResponse[QueueEntryResponse])
async def list_queue_entries(
    queue_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("queues:manage"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    account_id: uuid.UUID | None = None,
    status_filter: QueueEntryStatus | None = None,
) -> PaginatedResponse[QueueEntryResponse]:
    """List entries in a work queue."""
    q = select(WorkQueue).where(WorkQueue.id == queue_id, WorkQueue.tenant_id == user.tenant_id)
    if not (await session.execute(q)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work queue not found")

    query = select(QueueEntry).where(
        QueueEntry.queue_id == queue_id,
        QueueEntry.tenant_id == user.tenant_id,
    )
    if account_id:
        query = query.where(QueueEntry.account_id == account_id)
    if status_filter:
        query = query.where(QueueEntry.status == status_filter)

    count_result = await session.execute(query)
    total = len(list(count_result.scalars().all()))

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(QueueEntry.entered_at.desc())
    result = await session.execute(query)
    rows = list(result.scalars().all())

    return PaginatedResponse(
        items=[QueueEntryResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size else 0,
    )


@router.post(
    "/work-queues/{queue_id}/entries",
    response_model=QueueEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_queue_entry(
    queue_id: uuid.UUID,
    data: QueueEntryCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("queues:manage"))],
) -> QueueEntryResponse:
    """Add an account to a work queue."""
    q = select(WorkQueue).where(WorkQueue.id == queue_id, WorkQueue.tenant_id == user.tenant_id)
    if not (await session.execute(q)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work queue not found")

    acc = await session.execute(
        select(Account).where(Account.id == data.account_id, Account.tenant_id == user.tenant_id)
    )
    if not acc.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    entered_at = data.entered_at or datetime.now(timezone.utc)
    entry = QueueEntry(
        tenant_id=user.tenant_id,
        queue_id=queue_id,
        account_id=data.account_id,
        assigned_to_id=data.assigned_to_id,
        status=data.status,
        priority=data.priority,
        entered_at=entered_at,
        notes=data.notes,
    )
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return QueueEntryResponse.model_validate(entry)


@router.get("/work-queues/{queue_id}/entries/{entry_id}", response_model=QueueEntryResponse)
async def get_queue_entry(
    queue_id: uuid.UUID,
    entry_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("queues:manage"))],
) -> QueueEntryResponse:
    """Get queue entry by ID."""
    query = select(QueueEntry).where(
        QueueEntry.id == entry_id,
        QueueEntry.queue_id == queue_id,
        QueueEntry.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue entry not found")
    return QueueEntryResponse.model_validate(row)


@router.patch("/work-queues/{queue_id}/entries/{entry_id}", response_model=QueueEntryResponse)
async def update_queue_entry(
    queue_id: uuid.UUID,
    entry_id: uuid.UUID,
    data: QueueEntryUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("queues:manage"))],
) -> QueueEntryResponse:
    """Update queue entry."""
    query = select(QueueEntry).where(
        QueueEntry.id == entry_id,
        QueueEntry.queue_id == queue_id,
        QueueEntry.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue entry not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await session.flush()
    await session.refresh(row)
    return QueueEntryResponse.model_validate(row)


@router.delete("/work-queues/{queue_id}/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_queue_entry(
    queue_id: uuid.UUID,
    entry_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("queues:manage"))],
) -> None:
    """Remove account from queue (delete entry)."""
    query = select(QueueEntry).where(
        QueueEntry.id == entry_id,
        QueueEntry.queue_id == queue_id,
        QueueEntry.tenant_id == user.tenant_id,
    )
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue entry not found")
    await session.delete(row)
    await session.flush()


@router.get("/work-queues/{queue_id}", response_model=WorkQueueResponse)
async def get_work_queue(
    queue_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("queues:manage"))],
) -> WorkQueueResponse:
    """Get work queue by ID."""
    query = select(WorkQueue).where(WorkQueue.id == queue_id, WorkQueue.tenant_id == user.tenant_id)
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work queue not found")
    return WorkQueueResponse.model_validate(row)


@router.post(
    "/work-queues",
    response_model=WorkQueueResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_work_queue(
    data: WorkQueueCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("queues:manage"))],
) -> WorkQueueResponse:
    """Create work queue."""
    wq = WorkQueue(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        queue_type=data.queue_type,
        priority=data.priority,
        assigned_to_id=data.assigned_to_id,
        auto_populate_rules=data.auto_populate_rules,
        max_size=data.max_size,
        sla_hours=data.sla_hours,
        is_active=data.is_active,
    )
    session.add(wq)
    await session.flush()
    await session.refresh(wq)
    return WorkQueueResponse.model_validate(wq)


@router.patch("/work-queues/{queue_id}", response_model=WorkQueueResponse)
async def update_work_queue(
    queue_id: uuid.UUID,
    data: WorkQueueUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("queues:manage"))],
) -> WorkQueueResponse:
    """Update work queue."""
    query = select(WorkQueue).where(WorkQueue.id == queue_id, WorkQueue.tenant_id == user.tenant_id)
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work queue not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await session.flush()
    await session.refresh(row)
    return WorkQueueResponse.model_validate(row)


@router.delete("/work-queues/{queue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_queue(
    queue_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission("queues:manage"))],
) -> None:
    """Delete work queue (cascade entries)."""
    query = select(WorkQueue).where(WorkQueue.id == queue_id, WorkQueue.tenant_id == user.tenant_id)
    result = await session.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work queue not found")
    await session.delete(row)
    await session.flush()
