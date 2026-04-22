"""Enhanced payment plan models."""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import TenantScopedModel


class PlanType(str, enum.Enum):
    STANDARD = "standard"
    SETTLEMENT = "settlement"
    HARDSHIP = "hardship"
    STIPULATED = "stipulated"


class PlanStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    DEFAULTED = "defaulted"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


class PaymentFrequency(str, enum.Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    SEMI_MONTHLY = "semi_monthly"
    QUARTERLY = "quarterly"
    LUMP_SUM = "lump_sum"


class PaymentPlan(TenantScopedModel):
    __tablename__ = "payment_plans"

    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    consumer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    plan_type: Mapped[PlanType] = mapped_column(Enum(PlanType), default=PlanType.STANDARD, nullable=False)
    status: Mapped[PlanStatus] = mapped_column(Enum(PlanStatus), default=PlanStatus.DRAFT, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    frequency: Mapped[PaymentFrequency] = mapped_column(Enum(PaymentFrequency), default=PaymentFrequency.MONTHLY, nullable=False)
    total_payments: Mapped[int] = mapped_column(Integer, nullable=False)
    payments_made: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payments_remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    balance_remaining: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    next_payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_settlement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    settlement_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    settlement_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    original_balance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    pif_tolerance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    max_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auto_post: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    defaulted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    default_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    amortization_schedule: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    projection_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    scheduled_payments: Mapped[list["ScheduledPayment"]] = relationship(back_populates="plan", cascade="all, delete-orphan", order_by="ScheduledPayment.due_date")


class ScheduledPayment(TenantScopedModel):
    __tablename__ = "scheduled_payments"

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_due: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    principal_portion: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    interest_portion: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    fee_portion: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    plan: Mapped["PaymentPlan"] = relationship(back_populates="scheduled_payments")
