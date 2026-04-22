"""Litigation and judgment models.

Handles court cases, judgments, and post-judgment interest accrual.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
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

if TYPE_CHECKING:
    from dcs_api.models.account import Account
    from dcs_api.models.compliance import PolicyPack


class LitigationStatus(str, Enum):
    """Litigation case status."""

    PENDING_FILING = "pending_filing"
    FILED = "filed"
    SERVED = "served"
    ANSWER_RECEIVED = "answer_received"
    DISCOVERY = "discovery"
    TRIAL_SCHEDULED = "trial_scheduled"
    JUDGMENT_ENTERED = "judgment_entered"
    POST_JUDGMENT = "post_judgment"
    SATISFIED = "satisfied"
    DISMISSED = "dismissed"
    APPEALED = "appealed"


class LitigationCase(TenantScopedModel):
    """Litigation case.

    Represents a court case for debt collection, including
    court metadata, deadlines, and filing status.
    """

    __tablename__ = "litigation_cases"
    __table_args__ = (
        Index("ix_litigation_account", "account_id"),
        Index("ix_litigation_docket", "court_id", "docket_number"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id"),
        nullable=False,
    )

    # Court information
    court_id: Mapped[str] = mapped_column(String(100), nullable=False)  # Court identifier
    court_name: Mapped[str] = mapped_column(String(255), nullable=False)
    court_type: Mapped[str] = mapped_column(String(50), nullable=False)  # special_civil, superior
    docket_number: Mapped[str | None] = mapped_column(String(100))
    case_number: Mapped[str | None] = mapped_column(String(100))

    # Status and dates
    status: Mapped[LitigationStatus] = mapped_column(
        SQLEnum(LitigationStatus),
        default=LitigationStatus.PENDING_FILING,
        nullable=False,
    )
    filed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    served_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answer_due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Amounts claimed
    principal_claimed: Mapped[int] = mapped_column(Integer, nullable=False)  # cents
    interest_claimed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fees_claimed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    costs_claimed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Attorney information
    attorney_name: Mapped[str | None] = mapped_column(String(255))
    attorney_bar_id: Mapped[str | None] = mapped_column(String(50))

    # Notes and documents
    notes: Mapped[str | None] = mapped_column(Text)
    documents: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # E-filing
    efiling_submission_id: Mapped[str | None] = mapped_column(String(255))
    efiling_status: Mapped[str | None] = mapped_column(String(50))

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="litigation_cases")
    judgment: Mapped["Judgment | None"] = relationship(
        "Judgment", back_populates="litigation_case", uselist=False
    )


class Judgment(TenantScopedModel):
    """Court judgment.

    Records a judgment with the amount, date, and applicable
    post-judgment interest rate from the policy pack.
    """

    __tablename__ = "judgments"

    litigation_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("litigation_cases.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    policy_pack_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policy_packs.id"),
    )

    # Judgment details
    judgment_date: Mapped[date] = mapped_column(Date, nullable=False)
    judgment_amount: Mapped[int] = mapped_column(Integer, nullable=False)  # cents
    principal_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    interest_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    costs_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attorney_fees_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Interest rate (from policy pack / NJ courts)
    post_judgment_rate: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)
    rate_source: Mapped[str] = mapped_column(String(255), nullable=False)
    rate_effective_year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Threshold determination (Special Civil Part vs Superior)
    is_above_threshold: Mapped[bool] = mapped_column(default=False, nullable=False)
    threshold_amount: Mapped[int | None] = mapped_column(Integer)

    # Accrual tracking
    total_accrued_interest: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_accrual_date: Mapped[date | None] = mapped_column(Date)

    # Satisfaction
    satisfied_date: Mapped[date | None] = mapped_column(Date)
    satisfaction_recorded: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Audit
    calculation_version: Mapped[str] = mapped_column(String(50), nullable=False)
    source_snapshot_hash: Mapped[str | None] = mapped_column(String(64))

    # Relationships
    litigation_case: Mapped["LitigationCase"] = relationship(
        "LitigationCase", back_populates="judgment"
    )
    policy_pack: Mapped["PolicyPack"] = relationship("PolicyPack")
    accruals: Mapped[list["JudgmentInterestAccrual"]] = relationship(
        "JudgmentInterestAccrual", back_populates="judgment"
    )


class JudgmentInterestAccrual(TenantScopedModel):
    """Daily post-judgment interest accrual.

    Records daily interest accruals for defensibility and audit.
    Can be computed on-demand or stored as snapshots.
    """

    __tablename__ = "judgment_interest_accruals"
    __table_args__ = (
        Index("ix_accrual_judgment_date", "judgment_id", "accrual_date"),
    )

    judgment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("judgments.id", ondelete="CASCADE"),
        nullable=False,
    )

    accrual_date: Mapped[date] = mapped_column(Date, nullable=False)
    principal_balance: Mapped[int] = mapped_column(Integer, nullable=False)  # cents
    daily_rate: Mapped[Decimal] = mapped_column(Numeric(12, 10), nullable=False)
    accrued_amount: Mapped[int] = mapped_column(Integer, nullable=False)  # cents
    cumulative_amount: Mapped[int] = mapped_column(Integer, nullable=False)  # cents

    # Rate metadata
    annual_rate: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)
    rate_year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Audit
    calculation_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relationships
    judgment: Mapped["Judgment"] = relationship("Judgment", back_populates="accruals")
