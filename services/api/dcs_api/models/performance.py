"""Collector performance, goals, and analytics models.

Tracks individual and group goals, daily performance snapshots,
and provides data for management dashboards.
"""

import uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import TenantScopedModel


class GoalType(str, Enum):
    COLLECTIONS = "collections"
    CONTACTS = "contacts"
    ACCOUNTS_WORKED = "accounts_worked"
    PROMISES = "promises"
    SETTLEMENTS = "settlements"
    PAYMENTS_SECURED = "payments_secured"
    CUSTOM = "custom"


class GoalPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class GoalGroup(TenantScopedModel):
    """A grouping of accounts for targeted goal-setting.

    Lets supervisors set different goals for high-balance vs low-balance
    portfolios, or by client, debt type, etc.
    """

    __tablename__ = "goal_groups"
    __table_args__ = (
        Index("ix_goal_groups_tenant", "tenant_id"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    filter_criteria: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    goals: Mapped[list["CollectorGoal"]] = relationship(
        "CollectorGoal", back_populates="goal_group"
    )


class CollectorGoal(TenantScopedModel):
    """A performance goal for a specific collector."""

    __tablename__ = "collector_goals"
    __table_args__ = (
        Index("ix_collector_goals_user", "collector_id"),
        Index("ix_collector_goals_period", "period_start", "period_end"),
    )

    collector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    goal_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goal_groups.id")
    )

    goal_type: Mapped[GoalType] = mapped_column(SQLEnum(GoalType), nullable=False)
    period: Mapped[GoalPeriod] = mapped_column(SQLEnum(GoalPeriod), nullable=False)

    target_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    goal_factor: Mapped[float] = mapped_column(Numeric(5, 2), default=1.0, nullable=False)

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    notes: Mapped[str | None] = mapped_column(Text)

    goal_group: Mapped["GoalGroup | None"] = relationship(
        "GoalGroup", back_populates="goals"
    )


class PerformanceSnapshot(TenantScopedModel):
    """Daily performance metrics for a collector.

    Captures a point-in-time snapshot of collector productivity
    for trend analysis and management reporting.
    """

    __tablename__ = "performance_snapshots"
    __table_args__ = (
        Index("ix_perf_snap_collector_date", "collector_id", "snapshot_date", unique=True),
    )

    collector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    accounts_worked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    calls_made: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    calls_connected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    promises_obtained: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payments_secured: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_collected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    activities_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    documents_generated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    queue_depth_start: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    queue_depth_end: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    extra_metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
