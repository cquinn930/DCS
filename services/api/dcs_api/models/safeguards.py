"""Financial safeguard models."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from dcs_api.models.base import TenantScopedModel


class TransactionLimit(TenantScopedModel):
    __tablename__ = "transaction_limits"

    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    max_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    requires_approval_above: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    applies_to_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)


class FinancialNote(TenantScopedModel):
    __tablename__ = "financial_notes"

    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    must_acknowledge: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TemporaryHold(TenantScopedModel):
    __tablename__ = "temporary_holds"

    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    hold_type: Mapped[str] = mapped_column(String(50), default="general", nullable=False)
    placed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    block_batch_processing: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    block_letters: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    block_credit_reporting: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_manual_entry: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
