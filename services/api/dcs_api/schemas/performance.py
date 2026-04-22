"""Collector goals and performance snapshot schemas."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.performance import GoalPeriod, GoalType
from dcs_api.schemas.common import TimestampSchema


class GoalGroupCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    filter_criteria: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class GoalGroupUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    filter_criteria: dict[str, Any] | None = None
    is_active: bool | None = None


class GoalGroupResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    filter_criteria: dict[str, Any]
    is_active: bool


class CollectorGoalCreate(BaseModel):
    collector_id: uuid.UUID
    goal_group_id: uuid.UUID | None = None
    goal_type: GoalType
    period: GoalPeriod
    target_amount: int
    actual_amount: int = 0
    goal_factor: float = Field(default=1.0, ge=0)
    period_start: date
    period_end: date
    notes: str | None = None


class CollectorGoalUpdate(BaseModel):
    collector_id: uuid.UUID | None = None
    goal_group_id: uuid.UUID | None = None
    goal_type: GoalType | None = None
    period: GoalPeriod | None = None
    target_amount: int | None = None
    actual_amount: int | None = None
    goal_factor: float | None = Field(None, ge=0)
    period_start: date | None = None
    period_end: date | None = None
    notes: str | None = None


class CollectorGoalResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    collector_id: uuid.UUID
    goal_group_id: uuid.UUID | None
    goal_type: GoalType
    period: GoalPeriod
    target_amount: int
    actual_amount: int
    goal_factor: float
    period_start: date
    period_end: date
    notes: str | None


class PerformanceSnapshotCreate(BaseModel):
    collector_id: uuid.UUID
    snapshot_date: date
    accounts_worked: int = Field(default=0, ge=0)
    calls_made: int = Field(default=0, ge=0)
    calls_connected: int = Field(default=0, ge=0)
    promises_obtained: int = Field(default=0, ge=0)
    payments_secured: int = Field(default=0, ge=0)
    total_collected: int = Field(default=0, ge=0)
    activities_completed: int = Field(default=0, ge=0)
    documents_generated: int = Field(default=0, ge=0)
    queue_depth_start: int = Field(default=0, ge=0)
    queue_depth_end: int = Field(default=0, ge=0)
    extra_metrics: dict[str, Any] = Field(default_factory=dict)


class PerformanceSnapshotUpdate(BaseModel):
    snapshot_date: date | None = None
    accounts_worked: int | None = Field(None, ge=0)
    calls_made: int | None = Field(None, ge=0)
    calls_connected: int | None = Field(None, ge=0)
    promises_obtained: int | None = Field(None, ge=0)
    payments_secured: int | None = Field(None, ge=0)
    total_collected: int | None = Field(None, ge=0)
    activities_completed: int | None = Field(None, ge=0)
    documents_generated: int | None = Field(None, ge=0)
    queue_depth_start: int | None = Field(None, ge=0)
    queue_depth_end: int | None = Field(None, ge=0)
    extra_metrics: dict[str, Any] | None = None


class PerformanceSnapshotResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    collector_id: uuid.UUID
    snapshot_date: date
    accounts_worked: int
    calls_made: int
    calls_connected: int
    promises_obtained: int
    payments_secured: int
    total_collected: int
    activities_completed: int
    documents_generated: int
    queue_depth_start: int
    queue_depth_end: int
    extra_metrics: dict[str, Any]
