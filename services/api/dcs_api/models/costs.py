"""Cost tracking and billing models.

Tracks costs incurred on accounts (court fees, service fees,
skip trace charges) with disbursement and client billing workflows.
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


class CostType(str, Enum):
    COURT_FILING = "court_filing"
    SERVICE_OF_PROCESS = "service_of_process"
    SKIP_TRACE = "skip_trace"
    RECORDING = "recording"
    CREDIT_REPORT = "credit_report"
    GARNISHMENT = "garnishment"
    POSTAGE = "postage"
    DOCUMENT_PREP = "document_prep"
    TRAVEL = "travel"
    OTHER = "other"


class CostStatus(str, Enum):
    INCURRED = "incurred"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DISBURSED = "disbursed"
    RECOVERED = "recovered"
    PARTIALLY_RECOVERED = "partially_recovered"
    WRITTEN_OFF = "written_off"


class CostEntry(TenantScopedModel):
    """A cost incurred on an account."""

    __tablename__ = "cost_entries"
    __table_args__ = (
        Index("ix_cost_entries_account", "account_id"),
        Index("ix_cost_entries_status", "status"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )

    cost_type: Mapped[CostType] = mapped_column(SQLEnum(CostType), nullable=False)
    status: Mapped[CostStatus] = mapped_column(
        SQLEnum(CostStatus), default=CostStatus.INCURRED, nullable=False
    )

    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    recovered_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_recoverable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_firm_cost: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    vendor_name: Mapped[str | None] = mapped_column(String(255))
    vendor_reference: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)

    incurred_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    trust_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trust_accounts.id")
    )

    disbursement: Mapped["CostDisbursement | None"] = relationship(
        "CostDisbursement", back_populates="cost_entry", uselist=False
    )


class DisbursementMethod(str, Enum):
    CHECK = "check"
    ACH = "ach"
    WIRE = "wire"
    INTERNAL_TRANSFER = "internal_transfer"


class CostDisbursement(TenantScopedModel):
    """A payment made to a vendor for a cost."""

    __tablename__ = "cost_disbursements"

    cost_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_entries.id", ondelete="CASCADE"),
        unique=True, nullable=False,
    )

    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[DisbursementMethod] = mapped_column(
        SQLEnum(DisbursementMethod), nullable=False
    )

    check_number: Mapped[str | None] = mapped_column(String(50))
    reference_number: Mapped[str | None] = mapped_column(String(100))
    payee: Mapped[str] = mapped_column(String(255), nullable=False)

    disbursed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disbursed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    trust_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trust_transactions.id")
    )

    cost_entry: Mapped["CostEntry"] = relationship(
        "CostEntry", back_populates="disbursement"
    )


class ClientBillingStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class CostBilling(TenantScopedModel):
    """A bill sent to a client for costs incurred on their accounts."""

    __tablename__ = "cost_billings"
    __table_args__ = (
        Index("ix_cost_billing_tenant", "tenant_id"),
    )

    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_reference: Mapped[str | None] = mapped_column(String(100))

    status: Mapped[ClientBillingStatus] = mapped_column(
        SQLEnum(ClientBillingStatus), default=ClientBillingStatus.DRAFT, nullable=False
    )

    total_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    line_items: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    billing_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    billing_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    notes: Mapped[str | None] = mapped_column(Text)
