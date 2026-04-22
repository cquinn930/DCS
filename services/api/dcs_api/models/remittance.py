"""Remittance models for client fund disbursement."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import TenantScopedModel


class RemittanceStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    FINALIZED = "finalized"
    SENT = "sent"
    VOIDED = "voided"


class RemittanceStatement(TenantScopedModel):
    __tablename__ = "remittance_statements"

    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    statement_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[RemittanceStatus] = mapped_column(Enum(RemittanceStatus), default=RemittanceStatus.DRAFT, nullable=False)
    total_collected: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_fees: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_costs: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_invoices: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    net_remittance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    trust_balance_before: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    trust_balance_after: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    line_items: Mapped[list["RemittanceLineItem"]] = relationship(back_populates="statement", cascade="all, delete-orphan")


class RemittanceLineItem(TenantScopedModel):
    __tablename__ = "remittance_line_items"

    statement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("remittance_statements.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    line_type: Mapped[str] = mapped_column(String(50), nullable=False)  # payment, fee, cost, adjustment, invoice
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    cost_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    transaction_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    statement: Mapped["RemittanceStatement"] = relationship(back_populates="line_items")


class RemittanceConfig(TenantScopedModel):
    __tablename__ = "remittance_configs"

    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    include_payments: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_fees: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_costs: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_invoices: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_trust_summary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    group_by: Mapped[str] = mapped_column(String(50), default="account", nullable=False)
    sort_by: Mapped[str] = mapped_column(String(50), default="date", nullable=False)
    output_format: Mapped[str] = mapped_column(String(20), default="pdf", nullable=False)
    email_on_finalize: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_recipients: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    template_overrides: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
