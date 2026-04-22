"""Event rules and scheduled job schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.automation import (
    EventTriggerType,
    ExecutionStatus,
    JobStatus,
    JobType,
    ScheduleType,
)
from dcs_api.schemas.common import TimestampSchema


class EventRuleCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    entity_type: str = Field(..., max_length=50)
    field_name: str | None = Field(None, max_length=100)
    trigger_type: EventTriggerType
    conditions: dict[str, Any] = Field(default_factory=dict)
    actions: list[Any] = Field(default_factory=list)
    priority: int = Field(default=100, ge=0)
    is_active: bool = True
    is_system: bool = False
    apply_to_closed: bool = False
    created_by_id: uuid.UUID | None = None


class EventRuleUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    entity_type: str | None = Field(None, max_length=50)
    field_name: str | None = Field(None, max_length=100)
    trigger_type: EventTriggerType | None = None
    conditions: dict[str, Any] | None = None
    actions: list[Any] | None = None
    priority: int | None = Field(None, ge=0)
    is_active: bool | None = None
    is_system: bool | None = None
    apply_to_closed: bool | None = None
    created_by_id: uuid.UUID | None = None


class EventRuleResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    entity_type: str
    field_name: str | None
    trigger_type: EventTriggerType
    conditions: dict[str, Any]
    actions: list[Any]
    priority: int
    is_active: bool
    is_system: bool
    apply_to_closed: bool
    fired_count: int
    last_fired_at: datetime | None
    created_by_id: uuid.UUID | None


class EventLogCreate(BaseModel):
    rule_id: uuid.UUID
    entity_type: str = Field(..., max_length=50)
    entity_id: uuid.UUID
    trigger_data: dict[str, Any] = Field(default_factory=dict)
    actions_executed: list[Any] = Field(default_factory=list)
    success: bool = True
    error_message: str | None = None


class EventLogUpdate(BaseModel):
    trigger_data: dict[str, Any] | None = None
    actions_executed: list[Any] | None = None
    success: bool | None = None
    error_message: str | None = None


class EventLogResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    rule_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    trigger_data: dict[str, Any]
    actions_executed: list[Any]
    success: bool
    error_message: str | None


class ScheduledJobCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    job_type: JobType
    schedule_type: ScheduleType
    interval_seconds: int | None = Field(None, ge=0)
    run_at_time: str | None = Field(None, max_length=5)
    run_on_days: list[Any] | None = None
    run_on_day_of_month: int | None = Field(None, ge=1, le=31)
    timezone: str = Field(default="UTC", max_length=50)
    status: JobStatus = JobStatus.ACTIVE
    parameters: dict[str, Any] = Field(default_factory=dict)
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_duration_ms: int | None = Field(None, ge=0)
    consecutive_failures: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    created_by_id: uuid.UUID | None = None
    is_system: bool = False


class ScheduledJobUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    job_type: JobType | None = None
    schedule_type: ScheduleType | None = None
    interval_seconds: int | None = Field(None, ge=0)
    run_at_time: str | None = Field(None, max_length=5)
    run_on_days: list[Any] | None = None
    run_on_day_of_month: int | None = Field(None, ge=1, le=31)
    timezone: str | None = Field(None, max_length=50)
    status: JobStatus | None = None
    parameters: dict[str, Any] | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_duration_ms: int | None = Field(None, ge=0)
    consecutive_failures: int | None = Field(None, ge=0)
    max_retries: int | None = Field(None, ge=0)
    created_by_id: uuid.UUID | None = None
    is_system: bool | None = None


class ScheduledJobResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    job_type: JobType
    schedule_type: ScheduleType
    interval_seconds: int | None
    run_at_time: str | None
    run_on_days: list[Any] | None
    run_on_day_of_month: int | None
    timezone: str
    status: JobStatus
    parameters: dict[str, Any]
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_duration_ms: int | None
    consecutive_failures: int
    max_retries: int
    created_by_id: uuid.UUID | None
    is_system: bool


class JobExecutionCreate(BaseModel):
    job_id: uuid.UUID
    status: ExecutionStatus = ExecutionStatus.RUNNING
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = Field(None, ge=0)
    records_processed: int = Field(default=0, ge=0)
    records_succeeded: int = Field(default=0, ge=0)
    records_failed: int = Field(default=0, ge=0)
    output: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    error_trace: str | None = None
    triggered_by: str = Field(default="scheduler", max_length=50)


class JobExecutionUpdate(BaseModel):
    status: ExecutionStatus | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = Field(None, ge=0)
    records_processed: int | None = Field(None, ge=0)
    records_succeeded: int | None = Field(None, ge=0)
    records_failed: int | None = Field(None, ge=0)
    output: dict[str, Any] | None = None
    error_message: str | None = None
    error_trace: str | None = None
    triggered_by: str | None = Field(None, max_length=50)


class JobExecutionResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    job_id: uuid.UUID
    status: ExecutionStatus
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    records_processed: int
    records_succeeded: int
    records_failed: int
    output: dict[str, Any]
    error_message: str | None
    error_trace: str | None
    triggered_by: str
