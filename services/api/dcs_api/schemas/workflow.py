"""Workflow, activity, and queue schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.workflow import (
    ActivityCategory,
    ActivityPriority,
    ActivityStatus,
    QueueEntryStatus,
    QueuePriority,
    QueueType,
)
from dcs_api.schemas.common import TimestampSchema


class ActivityCodeCreate(BaseModel):
    """Create activity code."""

    code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=255)
    description: str | None = None
    category: ActivityCategory = ActivityCategory.CUSTOM
    priority: ActivityPriority = ActivityPriority.NORMAL
    span_days: int = Field(default=0, ge=0)
    document_template_id: uuid.UUID | None = None
    target_queue_id: uuid.UUID | None = None
    next_activity_code_id: uuid.UUID | None = None
    auto_execute: bool = False
    is_system: bool = False
    is_active: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class ActivityCodeUpdate(BaseModel):
    """Update activity code."""

    name: str | None = Field(None, max_length=255)
    description: str | None = None
    category: ActivityCategory | None = None
    priority: ActivityPriority | None = None
    span_days: int | None = Field(None, ge=0)
    document_template_id: uuid.UUID | None = None
    target_queue_id: uuid.UUID | None = None
    next_activity_code_id: uuid.UUID | None = None
    auto_execute: bool | None = None
    is_system: bool | None = None
    is_active: bool | None = None
    config: dict[str, Any] | None = None


class ActivityCodeResponse(TimestampSchema):
    """Activity code response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    category: ActivityCategory
    priority: ActivityPriority
    span_days: int
    document_template_id: uuid.UUID | None = None
    target_queue_id: uuid.UUID | None = None
    next_activity_code_id: uuid.UUID | None = None
    auto_execute: bool
    is_system: bool
    is_active: bool
    config: dict[str, Any]


class ActivityEntryCreate(BaseModel):
    """Create activity entry."""

    account_id: uuid.UUID
    activity_code_id: uuid.UUID | None = None
    assigned_to_id: uuid.UUID | None = None
    status: ActivityStatus = ActivityStatus.SCHEDULED
    priority: ActivityPriority = ActivityPriority.NORMAL
    scheduled_date: datetime
    notes: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    parent_entry_id: uuid.UUID | None = None


class ActivityEntryUpdate(BaseModel):
    """Update activity entry."""

    assigned_to_id: uuid.UUID | None = None
    status: ActivityStatus | None = None
    priority: ActivityPriority | None = None
    scheduled_date: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    notes: str | None = None
    result: dict[str, Any] | None = None


class ActivityEntryResponse(TimestampSchema):
    """Activity entry response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID
    activity_code_id: uuid.UUID | None = None
    assigned_to_id: uuid.UUID | None = None
    status: ActivityStatus
    priority: ActivityPriority
    scheduled_date: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    notes: str | None = None
    result: dict[str, Any]
    parent_entry_id: uuid.UUID | None = None


class WorkflowChainStepCreate(BaseModel):
    """Create workflow chain step."""

    activity_code_id: uuid.UUID
    step_order: int = Field(..., ge=0)
    delay_days: int = Field(default=0, ge=0)
    condition: dict[str, Any] = Field(default_factory=dict)
    on_failure: str = Field(default="continue", max_length=20)


class WorkflowChainCreate(BaseModel):
    """Create workflow chain."""

    name: str = Field(..., max_length=255)
    description: str | None = None
    is_active: bool = True
    is_system: bool = False
    steps: list[WorkflowChainStepCreate] = Field(default_factory=list)


class WorkflowChainUpdate(BaseModel):
    """Update workflow chain."""

    name: str | None = Field(None, max_length=255)
    description: str | None = None
    is_active: bool | None = None
    is_system: bool | None = None


class WorkflowChainStepResponse(TimestampSchema):
    """Workflow chain step response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    chain_id: uuid.UUID
    activity_code_id: uuid.UUID
    step_order: int
    delay_days: int
    condition: dict[str, Any]
    on_failure: str


class WorkflowChainResponse(TimestampSchema):
    """Workflow chain response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool
    is_system: bool
    steps: list[WorkflowChainStepResponse] = Field(default_factory=list)


class WorkQueueCreate(BaseModel):
    """Create work queue."""

    name: str = Field(..., max_length=100)
    description: str | None = None
    queue_type: QueueType = QueueType.COLLECTOR
    priority: QueuePriority = QueuePriority.NORMAL
    assigned_to_id: uuid.UUID | None = None
    auto_populate_rules: dict[str, Any] = Field(default_factory=dict)
    max_size: int | None = Field(None, ge=0)
    sla_hours: int | None = Field(None, ge=0)
    is_active: bool = True


class WorkQueueUpdate(BaseModel):
    """Update work queue."""

    name: str | None = Field(None, max_length=100)
    description: str | None = None
    queue_type: QueueType | None = None
    priority: QueuePriority | None = None
    assigned_to_id: uuid.UUID | None = None
    auto_populate_rules: dict[str, Any] | None = None
    max_size: int | None = Field(None, ge=0)
    sla_hours: int | None = Field(None, ge=0)
    is_active: bool | None = None


class WorkQueueResponse(TimestampSchema):
    """Work queue response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    queue_type: QueueType
    priority: QueuePriority
    assigned_to_id: uuid.UUID | None = None
    auto_populate_rules: dict[str, Any]
    max_size: int | None = None
    sla_hours: int | None = None
    is_active: bool


class QueueEntryCreate(BaseModel):
    """Add account to queue."""

    account_id: uuid.UUID
    assigned_to_id: uuid.UUID | None = None
    status: QueueEntryStatus = QueueEntryStatus.PENDING
    priority: int = Field(default=5, ge=0)
    notes: str | None = None
    entered_at: datetime | None = None


class QueueEntryUpdate(BaseModel):
    """Update queue entry."""

    assigned_to_id: uuid.UUID | None = None
    status: QueueEntryStatus | None = None
    priority: int | None = Field(None, ge=0)
    assigned_at: datetime | None = None
    completed_at: datetime | None = None
    notes: str | None = None


class QueueEntryResponse(TimestampSchema):
    """Queue entry response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    queue_id: uuid.UUID
    account_id: uuid.UUID
    assigned_to_id: uuid.UUID | None = None
    status: QueueEntryStatus
    priority: int
    entered_at: datetime
    assigned_at: datetime | None = None
    completed_at: datetime | None = None
    notes: str | None = None


class ProcessMaturedResponse(BaseModel):
    """Result of processing matured activities."""

    processed_count: int
    entry_ids: list[uuid.UUID]
