"""Trust accounting and bank reconciliation models.

Supports four account types mirroring industry standards:
  Type 1 – Pooled trust (standard)
  Type 2 – Segregated trust (strict, no overdraft)
  Type 3 – Operating / cost account (paired with Type 2)
  Type 4 – Collections-only (fee isolation)
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


class TrustAccountType(str, Enum):
    POOLED_TRUST = "pooled_trust"
    SEGREGATED_TRUST = "segregated_trust"
    OPERATING = "operating"
    COLLECTIONS_ONLY = "collections_only"


class TrustAccountStatus(str, Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class TrustAccount(TenantScopedModel):
    """Trust or operating bank account."""

    __tablename__ = "trust_accounts"
    __table_args__ = (
        Index("ix_trust_accounts_tenant", "tenant_id"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[TrustAccountType] = mapped_column(
        SQLEnum(TrustAccountType), nullable=False
    )
    status: Mapped[TrustAccountStatus] = mapped_column(
        SQLEnum(TrustAccountStatus), default=TrustAccountStatus.ACTIVE, nullable=False
    )

    bank_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_number_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    routing_number_last4: Mapped[str | None] = mapped_column(String(4))

    current_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    linked_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trust_accounts.id")
    )

    allow_overdraft: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    linked_account: Mapped["TrustAccount | None"] = relationship(
        "TrustAccount", remote_side="TrustAccount.id"
    )
    transactions: Mapped[list["TrustTransaction"]] = relationship(
        "TrustTransaction", back_populates="trust_account"
    )
    reconciliations: Mapped[list["BankReconciliation"]] = relationship(
        "BankReconciliation", back_populates="trust_account"
    )


class TrustTransactionType(str, Enum):
    DEPOSIT = "deposit"
    DISBURSEMENT = "disbursement"
    COST_TRANSFER = "cost_transfer"
    FEE_TRANSFER = "fee_transfer"
    ADJUSTMENT = "adjustment"
    REVERSAL = "reversal"
    INTEREST_EARNED = "interest_earned"
    WIRE_IN = "wire_in"
    WIRE_OUT = "wire_out"
    CHECK = "check"


class TrustTransaction(TenantScopedModel):
    """Individual movement of funds in/out of a trust account."""

    __tablename__ = "trust_transactions"
    __table_args__ = (
        Index("ix_trust_tx_account", "trust_account_id"),
        Index("ix_trust_tx_date", "transaction_date"),
        Index("ix_trust_tx_reference", "reference_number"),
    )

    trust_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trust_accounts.id"), nullable=False
    )
    transaction_type: Mapped[TrustTransactionType] = mapped_column(
        SQLEnum(TrustTransactionType), nullable=False
    )

    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    running_balance: Mapped[int] = mapped_column(Integer, nullable=False)

    reference_number: Mapped[str | None] = mapped_column(String(100))
    check_number: Mapped[str | None] = mapped_column(String(50))
    payee: Mapped[str | None] = mapped_column(String(255))
    memo: Mapped[str | None] = mapped_column(Text)

    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id")
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    linked_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trust_transactions.id")
    )

    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    posted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    trust_account: Mapped["TrustAccount"] = relationship(
        "TrustAccount", back_populates="transactions"
    )


class ReconciliationStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    APPROVED = "approved"


class BankReconciliation(TenantScopedModel):
    """A reconciliation session for a trust account."""

    __tablename__ = "bank_reconciliations"
    __table_args__ = (
        Index("ix_bank_recon_account", "trust_account_id"),
    )

    trust_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trust_accounts.id"), nullable=False
    )

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    statement_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    book_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    adjusted_balance: Mapped[int | None] = mapped_column(Integer)
    difference: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[ReconciliationStatus] = mapped_column(
        SQLEnum(ReconciliationStatus), default=ReconciliationStatus.DRAFT, nullable=False
    )

    reconciled_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    notes: Mapped[str | None] = mapped_column(Text)
    import_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    trust_account: Mapped["TrustAccount"] = relationship(
        "TrustAccount", back_populates="reconciliations"
    )
    items: Mapped[list["ReconciliationItem"]] = relationship(
        "ReconciliationItem", back_populates="reconciliation"
    )


class ReconciliationMatchStatus(str, Enum):
    MATCHED = "matched"
    UNMATCHED = "unmatched"
    OUTSTANDING = "outstanding"
    ADJUSTMENT = "adjustment"


class ReconciliationItem(TenantScopedModel):
    """A line item in a bank reconciliation."""

    __tablename__ = "reconciliation_items"

    reconciliation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_reconciliations.id", ondelete="CASCADE"),
        nullable=False,
    )

    match_status: Mapped[ReconciliationMatchStatus] = mapped_column(
        SQLEnum(ReconciliationMatchStatus), nullable=False
    )

    statement_amount: Mapped[int | None] = mapped_column(Integer)
    statement_date: Mapped[date | None] = mapped_column(Date)
    statement_reference: Mapped[str | None] = mapped_column(String(255))
    statement_description: Mapped[str | None] = mapped_column(String(500))

    book_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trust_transactions.id")
    )
    book_amount: Mapped[int | None] = mapped_column(Integer)

    difference: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    reconciliation: Mapped["BankReconciliation"] = relationship(
        "BankReconciliation", back_populates="items"
    )
