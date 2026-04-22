"""Dashboard analytics response schemas (aggregated display data)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LiveMetricsResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    generated_at: datetime
    active_accounts: int = Field(ge=0)
    total_balance_cents: int
    open_disputes: int = Field(ge=0)
    payments_today_cents: int
    pending_activities: int = Field(ge=0)
    queue_accounts_pending: int = Field(ge=0)


class CollectorDashboardResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    collector_id: uuid.UUID
    generated_at: datetime
    assigned_accounts: int = Field(ge=0)
    queue_depth: int = Field(ge=0)
    activities_due_today: int = Field(ge=0)
    payments_secured_cents: int
    calls_today: int = Field(ge=0)
    goal_progress_pct: float | None = Field(default=None, ge=0, le=100)
    extra: dict[str, Any] = Field(default_factory=dict)


class ManagementDashboardResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    generated_at: datetime
    total_portfolio_cents: int
    active_collectors: int = Field(ge=0)
    litigation_cases_open: int = Field(ge=0)
    trust_balance_cents: int
    month_to_date_collected_cents: int
    dispute_rate_pct: float | None = Field(default=None, ge=0, le=100)
    extra: dict[str, Any] = Field(default_factory=dict)


class QueueStatsResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    queue_id: uuid.UUID
    generated_at: datetime
    pending_count: int = Field(ge=0)
    in_progress_count: int = Field(ge=0)
    completed_today: int = Field(ge=0)
    avg_age_hours: float | None = Field(default=None, ge=0)
    sla_breaches: int = Field(default=0, ge=0)
    oldest_entry_at: datetime | None = None
