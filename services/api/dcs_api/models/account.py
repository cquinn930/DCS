"""Account, case, dispute, payment, and notice models.

Core debt lifecycle entities including account management, case workflows,
dispute handling, and payment processing.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
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

if TYPE_CHECKING:
    from dcs_api.models.tenant import Tenant, User
    from dcs_api.models.consumer import Consumer
    from dcs_api.models.litigation import LitigationCase


class AccountStatus(str, Enum):
    """Account lifecycle status."""

    ACTIVE = "active"
    HOLD = "hold"  # Payment plan, dispute, etc.
    LEGAL_HOLD = "legal_hold"
    PAID_IN_FULL = "paid_in_full"
    SETTLED = "settled"
    CLOSED = "closed"
    RECALLED = "recalled"
    STATUTE_BARRED = "statute_barred"


class DebtType(str, Enum):
    """Types of debt."""

    CONSUMER = "consumer"
    COMMERCIAL = "commercial"
    MEDICAL = "medical"
    JUDGMENT = "judgment"
    STUDENT = "student"
    UTILITY = "utility"
    TELECOM = "telecom"
    OTHER = "other"


class Account(TenantScopedModel):
    """Debt account.

    Represents a single debt obligation linked to a consumer.
    All monetary values stored in cents to avoid floating point issues.
    """

    __tablename__ = "accounts"
    __table_args__ = (
        Index("ix_accounts_tenant_status", "tenant_id", "status"),
        Index("ix_accounts_consumer", "consumer_id"),
        Index("ix_accounts_reference", "tenant_id", "account_reference"),
    )

    consumer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consumers.id"),
        nullable=False,
    )

    # References
    account_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    original_creditor: Mapped[str] = mapped_column(String(255), nullable=False)
    current_creditor: Mapped[str | None] = mapped_column(String(255))
    client_account_number: Mapped[str | None] = mapped_column(String(100))

    # Status
    status: Mapped[AccountStatus] = mapped_column(
        SQLEnum(AccountStatus),
        default=AccountStatus.ACTIVE,
        nullable=False,
    )
    debt_type: Mapped[DebtType] = mapped_column(
        SQLEnum(DebtType),
        default=DebtType.CONSUMER,
        nullable=False,
    )
    jurisdiction: Mapped[str] = mapped_column(String(2), default="NJ", nullable=False)

    # Balances (all in cents)
    original_principal: Mapped[int] = mapped_column(Integer, nullable=False)
    current_principal: Mapped[int] = mapped_column(Integer, nullable=False)
    current_interest: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_fees: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_balance: Mapped[int] = mapped_column(Integer, nullable=False)

    # Dates
    date_of_service: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_of_first_delinquency: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_placed: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    statute_expiry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Legal hold
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    legal_hold_reason: Mapped[str | None] = mapped_column(Text)
    legal_hold_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Compliance
    validation_notice_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    validation_notice_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Metadata
    extra_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="accounts")
    consumer: Mapped["Consumer"] = relationship("Consumer", back_populates="accounts")
    debt_instrument: Mapped["DebtInstrument | None"] = relationship(
        "DebtInstrument", back_populates="account", uselist=False
    )
    cases: Mapped[list["Case"]] = relationship("Case", back_populates="account")
    disputes: Mapped[list["Dispute"]] = relationship("Dispute", back_populates="account")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="account")
    notices: Mapped[list["Notice"]] = relationship("Notice", back_populates="account")
    fees: Mapped[list["Fee"]] = relationship("Fee", back_populates="account")
    litigation_cases: Mapped[list["LitigationCase"]] = relationship(
        "LitigationCase", back_populates="account"
    )


class InterestType(str, Enum):
    """Interest calculation method."""

    SIMPLE = "simple"
    COMPOUND_DAILY = "compound_daily"
    COMPOUND_MONTHLY = "compound_monthly"
    COMPOUND_ANNUALLY = "compound_annually"
    POST_JUDGMENT = "post_judgment"


class DebtInstrument(TenantScopedModel):
    """Debt instrument details (contract terms).

    Stores the original contract terms including interest rate and type.
    """

    __tablename__ = "debt_instruments"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    instrument_type: Mapped[str] = mapped_column(String(100), nullable=False)  # credit_card, loan
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)  # Annual %
    interest_type: Mapped[InterestType] = mapped_column(
        SQLEnum(InterestType),
        default=InterestType.SIMPLE,
        nullable=False,
    )
    contract_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terms: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="debt_instrument")


class CaseStatus(str, Enum):
    """Case workflow status."""

    NEW = "new"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Case(TenantScopedModel):
    """Collection case (workflow instance).

    Represents work being done on an account, including collector assignment.
    """

    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_cases_tenant_status", "tenant_id", "status"),
        Index("ix_cases_assigned", "assigned_to_id"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id"),
        nullable=False,
    )
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
    )

    status: Mapped[CaseStatus] = mapped_column(
        SQLEnum(CaseStatus),
        default=CaseStatus.NEW,
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False)  # 1-10

    workflow_state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    next_action_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="cases")
    assigned_to: Mapped["User"] = relationship("User", back_populates="assigned_cases")


class DisputeStatus(str, Enum):
    """Dispute status."""

    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    RESOLVED_VALID = "resolved_valid"
    RESOLVED_INVALID = "resolved_invalid"
    CLOSED = "closed"


class DisputeReason(str, Enum):
    """Standard dispute reasons."""

    NOT_MY_DEBT = "not_my_debt"
    WRONG_AMOUNT = "wrong_amount"
    ALREADY_PAID = "already_paid"
    STATUTE_EXPIRED = "statute_expired"
    IDENTITY_THEFT = "identity_theft"
    OTHER = "other"


class Dispute(TenantScopedModel):
    """Consumer dispute record.

    Filing a dispute triggers legal hold and pauses outbound contact.
    Response timelines are enforced per Regulation F.
    """

    __tablename__ = "disputes"
    __table_args__ = (
        Index("ix_disputes_account", "account_id"),
        Index("ix_disputes_status", "status"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id"),
        nullable=False,
    )

    status: Mapped[DisputeStatus] = mapped_column(
        SQLEnum(DisputeStatus),
        default=DisputeStatus.PENDING,
        nullable=False,
    )
    reason: Mapped[DisputeReason] = mapped_column(SQLEnum(DisputeReason), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Timeline tracking (Reg F compliance)
    filed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    response_due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Resolution
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Documents
    documents: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="disputes")


class NoticeType(str, Enum):
    """Types of notices."""

    INITIAL_COMMUNICATION = "initial_communication"
    VALIDATION_NOTICE = "validation_notice"
    DISPUTE_ACKNOWLEDGEMENT = "dispute_acknowledgement"
    PAYMENT_CONFIRMATION = "payment_confirmation"
    SETTLEMENT_OFFER = "settlement_offer"
    POST_JUDGMENT_DISCLOSURE = "post_judgment_disclosure"
    CEASE_COMMUNICATION = "cease_communication"


class NoticeStatus(str, Enum):
    """Notice delivery status."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class Notice(TenantScopedModel):
    """Notice/communication record.

    Tracks all required notices with delivery status and template versions.
    """

    __tablename__ = "notices"
    __table_args__ = (
        Index("ix_notices_account", "account_id"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id"),
        nullable=False,
    )

    notice_type: Mapped[NoticeType] = mapped_column(SQLEnum(NoticeType), nullable=False)
    status: Mapped[NoticeStatus] = mapped_column(
        SQLEnum(NoticeStatus),
        default=NoticeStatus.PENDING,
        nullable=False,
    )

    # Template tracking
    template_id: Mapped[str] = mapped_column(String(100), nullable=False)
    template_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # Content and delivery
    channel: Mapped[str] = mapped_column(String(50), nullable=False)  # email, mail, sms
    recipient: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64))  # SHA-256 of content

    # Timing
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="notices")


class PaymentMethod(str, Enum):
    """Payment method types."""

    CARD = "card"
    ACH = "ach"
    ECHECK = "echeck"
    WIRE = "wire"
    CHECK = "check"
    CASH = "cash"
    OTHER = "other"


class PaymentStatus(str, Enum):
    """Payment processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"
    REFUNDED = "refunded"


class Payment(TenantScopedModel):
    """Payment record.

    All payments are tokenized via Tratta. No PAN storage.
    Amount in cents.
    """

    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_account", "account_id"),
        Index("ix_payments_processor_ref", "processor_reference"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id"),
        nullable=False,
    )

    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # cents
    method: Mapped[PaymentMethod] = mapped_column(SQLEnum(PaymentMethod), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus),
        default=PaymentStatus.PENDING,
        nullable=False,
    )

    # Processor tracking (Tratta)
    processor_reference: Mapped[str | None] = mapped_column(String(255))
    processor_response: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Timestamps
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Consumer source
    source: Mapped[str] = mapped_column(String(100), nullable=False)  # portal, phone, mail
    source_ip: Mapped[str | None] = mapped_column(String(45))

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="payments")
    allocations: Mapped[list["PaymentAllocation"]] = relationship(
        "PaymentAllocation", back_populates="payment"
    )


class AllocationTarget(str, Enum):
    """Payment allocation targets."""

    INTEREST = "interest"
    PRINCIPAL = "principal"
    FEES = "fees"
    COSTS = "costs"


class PaymentAllocation(TenantScopedModel):
    """Payment allocation breakdown.

    Shows how a payment was split across interest, principal, and fees.
    Allocation order is configurable per tenant/jurisdiction.
    """

    __tablename__ = "payment_allocations"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
    )

    target: Mapped[AllocationTarget] = mapped_column(SQLEnum(AllocationTarget), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # cents
    order: Mapped[int] = mapped_column(Integer, nullable=False)  # Allocation sequence

    # Relationships
    payment: Mapped["Payment"] = relationship("Payment", back_populates="allocations")


class FeeType(str, Enum):
    """Types of fees."""

    LATE_FEE = "late_fee"
    COLLECTION_FEE = "collection_fee"
    COURT_COST = "court_cost"
    ATTORNEY_FEE = "attorney_fee"
    NSF_FEE = "nsf_fee"
    SERVICE_FEE = "service_fee"
    OTHER = "other"


class Fee(TenantScopedModel):
    """Fee record.

    All fees must be validated against jurisdiction rules before being applied.
    """

    __tablename__ = "fees"
    __table_args__ = (
        Index("ix_fees_account", "account_id"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id"),
        nullable=False,
    )

    fee_type: Mapped[FeeType] = mapped_column(SQLEnum(FeeType), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # cents
    description: Mapped[str | None] = mapped_column(Text)

    # Validation
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    jurisdiction_validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    validation_rule: Mapped[str | None] = mapped_column(String(255))

    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    applied_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="fees")
