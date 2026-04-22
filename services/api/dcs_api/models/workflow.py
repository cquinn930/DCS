"""Workflow models: activities, work queues, and automation chains.

Activities are scheduled tasks on accounts (similar to diary entries in legacy
systems). They form chains that automate the collection lifecycle:
activity → document → next activity.

Work queues organize accounts for collectors and supervisors.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import TenantScopedModel


class ActivityStatus(str, Enum):
    SCHEDULED = "scheduled"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ActivityPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ActivityCategory(str, Enum):
    LETTER = "letter"
    CALL = "call"
    REVIEW = "review"
    LEGAL = "legal"
    FINANCIAL = "financial"
    COMPLIANCE = "compliance"
    SKIP_TRACE = "skip_trace"
    SYSTEM = "system"
    CUSTOM = "custom"


class ActivityCode(TenantScopedModel):
    """Reusable activity type definition.

    Defines what happens when an activity matures — which documents to
    generate, which queue to assign, and what the next chained activity is.
    """

    __tablename__ = "activity_codes"
    __table_args__ = (
        Index("ix_activity_codes_tenant_code", "tenant_id", "code", unique=True),
    )

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[ActivityCategory] = mapped_column(
        SQLEnum(ActivityCategory), default=ActivityCategory.CUSTOM, nullable=False
    )
    priority: Mapped[ActivityPriority] = mapped_column(
        SQLEnum(ActivityPriority), default=ActivityPriority.NORMAL, nullable=False
    )

    span_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    document_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    target_queue_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    next_activity_code_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activity_codes.id")
    )

    auto_execute: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    next_activity_code: Mapped["ActivityCode | None"] = relationship(
        "ActivityCode", remote_side="ActivityCode.id"
    )
    entries: Mapped[list["ActivityEntry"]] = relationship(
        "ActivityEntry", back_populates="activity_code"
    )


class ActivityEntry(TenantScopedModel):
    """A single scheduled activity on an account.

    When the scheduled_date arrives (or is past), the activity is "ready"
    and can be processed manually or by the automated activity runner.
    """

    __tablename__ = "activity_entries"
    __table_args__ = (
        Index("ix_activity_entries_tenant_status", "tenant_id", "status"),
        Index("ix_activity_entries_account", "account_id"),
        Index("ix_activity_entries_scheduled", "tenant_id", "scheduled_date", "status"),
        Index("ix_activity_entries_assigned", "assigned_to_id"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    activity_code_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activity_codes.id"), nullable=True
    )
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    status: Mapped[ActivityStatus] = mapped_column(
        SQLEnum(ActivityStatus), default=ActivityStatus.SCHEDULED, nullable=False
    )
    priority: Mapped[ActivityPriority] = mapped_column(
        SQLEnum(ActivityPriority), default=ActivityPriority.NORMAL, nullable=False
    )

    scheduled_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    notes: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    parent_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activity_entries.id")
    )

    activity_code: Mapped["ActivityCode"] = relationship(
        "ActivityCode", back_populates="entries"
    )


class WorkflowChain(TenantScopedModel):
    """Named sequence of activity codes forming an automated workflow.

    For example a "Standard Collection" chain: validation notice → 30-day
    wait → demand letter → phone call → escalation review.
    """

    __tablename__ = "workflow_chains"
    __table_args__ = (
        Index("ix_workflow_chains_tenant_name", "tenant_id", "name", unique=True),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    steps: Mapped[list["WorkflowChainStep"]] = relationship(
        "WorkflowChainStep", back_populates="chain", order_by="WorkflowChainStep.step_order"
    )


class WorkflowChainStep(TenantScopedModel):
    """A single step in a workflow chain."""

    __tablename__ = "workflow_chain_steps"
    __table_args__ = (
        Index("ix_chain_steps_chain_order", "chain_id", "step_order", unique=True),
    )

    chain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_chains.id", ondelete="CASCADE"), nullable=False
    )
    activity_code_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activity_codes.id"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)

    delay_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    condition: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    on_failure: Mapped[str] = mapped_column(String(20), default="continue", nullable=False)

    chain: Mapped["WorkflowChain"] = relationship("WorkflowChain", back_populates="steps")


class QueueType(str, Enum):
    COLLECTOR = "collector"
    SUPERVISOR = "supervisor"
    LEGAL = "legal"
    COMPLIANCE = "compliance"
    SYSTEM = "system"
    CUSTOM = "custom"


class QueuePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class WorkQueue(TenantScopedModel):
    """Work queue that organises accounts for processing.

    Queues can be auto-populated by rules or manually assigned.
    """

    __tablename__ = "work_queues"
    __table_args__ = (
        Index("ix_work_queues_tenant_name", "tenant_id", "name", unique=True),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    queue_type: Mapped[QueueType] = mapped_column(
        SQLEnum(QueueType), default=QueueType.COLLECTOR, nullable=False
    )
    priority: Mapped[QueuePriority] = mapped_column(
        SQLEnum(QueuePriority), default=QueuePriority.NORMAL, nullable=False
    )

    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    auto_populate_rules: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    max_size: Mapped[int | None] = mapped_column(Integer)
    sla_hours: Mapped[int | None] = mapped_column(Integer)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    entries: Mapped[list["QueueEntry"]] = relationship(
        "QueueEntry", back_populates="queue"
    )


class QueueEntryStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DEFERRED = "deferred"
    REMOVED = "removed"


class QueueEntry(TenantScopedModel):
    """An account placed into a work queue."""

    __tablename__ = "queue_entries"
    __table_args__ = (
        Index("ix_queue_entries_queue_status", "queue_id", "status"),
        Index("ix_queue_entries_account", "account_id"),
    )

    queue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_queues.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    status: Mapped[QueueEntryStatus] = mapped_column(
        SQLEnum(QueueEntryStatus), default=QueueEntryStatus.PENDING, nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    notes: Mapped[str | None] = mapped_column(Text)

    queue: Mapped["WorkQueue"] = relationship("WorkQueue", back_populates="entries")
