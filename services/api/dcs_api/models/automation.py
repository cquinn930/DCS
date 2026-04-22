"""Automation models: event rules, triggers, and the DB-driven job scheduler.

Event rules fire when entity fields change (reactive automation).
Scheduled jobs run on configurable intervals without external cron.
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


# ---------------------------------------------------------------------------
# Event rules (field-level triggers)
# ---------------------------------------------------------------------------

class EventTriggerType(str, Enum):
    FIELD_CHANGE = "field_change"
    RECORD_CREATE = "record_create"
    RECORD_UPDATE = "record_update"
    STATUS_CHANGE = "status_change"
    PAYMENT_POSTED = "payment_posted"
    ACTIVITY_COMPLETED = "activity_completed"
    DISPUTE_FILED = "dispute_filed"
    DOCUMENT_GENERATED = "document_generated"
    QUEUE_ASSIGNED = "queue_assigned"
    TAG_ADDED = "tag_added"
    TAG_REMOVED = "tag_removed"
    CUSTOM = "custom"


class EventActionType(str, Enum):
    ADD_ACTIVITY = "add_activity"
    REMOVE_ACTIVITY = "remove_activity"
    ADD_TAG = "add_tag"
    REMOVE_TAG = "remove_tag"
    SEND_NOTICE = "send_notice"
    GENERATE_DOCUMENT = "generate_document"
    UPDATE_FIELD = "update_field"
    ASSIGN_QUEUE = "assign_queue"
    RUN_SCRIPT = "run_script"
    SEND_WEBHOOK = "send_webhook"
    LOG_EVENT = "log_event"
    CHANGE_STATUS = "change_status"


class EventRule(TenantScopedModel):
    """A reactive automation rule.

    When the trigger condition is met on the specified entity/field,
    the configured actions execute automatically.
    """

    __tablename__ = "event_rules"
    __table_args__ = (
        Index("ix_event_rules_tenant_active", "tenant_id", "is_active"),
        Index("ix_event_rules_entity", "entity_type"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(100))
    trigger_type: Mapped[EventTriggerType] = mapped_column(
        SQLEnum(EventTriggerType), nullable=False
    )

    conditions: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    actions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    apply_to_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    fired_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    logs: Mapped[list["EventLog"]] = relationship("EventLog", back_populates="rule")


class EventLog(TenantScopedModel):
    """Audit record of an event rule firing."""

    __tablename__ = "event_logs"
    __table_args__ = (
        Index("ix_event_logs_rule", "rule_id"),
        Index("ix_event_logs_entity", "entity_type", "entity_id"),
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event_rules.id"), nullable=False
    )

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    trigger_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    actions_executed: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    rule: Mapped["EventRule"] = relationship("EventRule", back_populates="logs")


# ---------------------------------------------------------------------------
# DB-driven job scheduler (replaces cron)
# ---------------------------------------------------------------------------

class ScheduleType(str, Enum):
    INTERVAL = "interval"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ONE_TIME = "one_time"


class JobType(str, Enum):
    PROCESS_ACTIVITIES = "process_activities"
    GENERATE_DOCUMENTS = "generate_documents"
    RUN_REPORT = "run_report"
    DATA_IMPORT = "data_import"
    DATA_EXPORT = "data_export"
    CREDIT_BUREAU_REPORT = "credit_bureau_report"
    MASS_STATUS_UPDATE = "mass_status_update"
    RECONCILIATION = "reconciliation"
    DEMOGRAPHIC_SYNC = "demographic_sync"
    QUEUE_REPOPULATE = "queue_repopulate"
    RUN_SCRIPT = "run_script"
    CUSTOM = "custom"


class JobStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class ScheduledJob(TenantScopedModel):
    """A recurring or one-time job managed in the database.

    The application's background runner polls this table for due jobs
    instead of relying on external cron or task schedulers.
    """

    __tablename__ = "scheduled_jobs"
    __table_args__ = (
        Index("ix_scheduled_jobs_tenant", "tenant_id"),
        Index("ix_scheduled_jobs_next_run", "next_run_at", "status"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    job_type: Mapped[JobType] = mapped_column(SQLEnum(JobType), nullable=False)
    schedule_type: Mapped[ScheduleType] = mapped_column(SQLEnum(ScheduleType), nullable=False)

    interval_seconds: Mapped[int | None] = mapped_column(Integer)
    run_at_time: Mapped[str | None] = mapped_column(String(5))
    run_on_days: Mapped[list | None] = mapped_column(JSONB)
    run_on_day_of_month: Mapped[int | None] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)

    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus), default=JobStatus.ACTIVE, nullable=False
    )
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_duration_ms: Mapped[int | None] = mapped_column(Integer)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    executions: Mapped[list["JobExecution"]] = relationship(
        "JobExecution", back_populates="job"
    )


class ExecutionStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class JobExecution(TenantScopedModel):
    """Record of a single job run."""

    __tablename__ = "job_executions"
    __table_args__ = (
        Index("ix_job_executions_job", "job_id"),
        Index("ix_job_executions_started", "started_at"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scheduled_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[ExecutionStatus] = mapped_column(
        SQLEnum(ExecutionStatus), default=ExecutionStatus.RUNNING, nullable=False
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    records_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_succeeded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    output: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    error_trace: Mapped[str | None] = mapped_column(Text)

    triggered_by: Mapped[str] = mapped_column(
        String(50), default="scheduler", nullable=False
    )

    job: Mapped["ScheduledJob"] = relationship("ScheduledJob", back_populates="executions")
