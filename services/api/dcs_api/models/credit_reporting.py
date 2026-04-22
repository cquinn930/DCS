"""Credit bureau reporting models.

Supports Metro II format export to Equifax, TransUnion, and Experian,
with batch tracking, filtering, and dispute suppression.
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
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import TenantScopedModel


class CreditBureau(str, Enum):
    EQUIFAX = "equifax"
    TRANSUNION = "transunion"
    EXPERIAN = "experian"


class BureauConfig(TenantScopedModel):
    """Configuration for credit bureau reporting per tenant."""

    __tablename__ = "bureau_configs"
    __table_args__ = (
        Index("ix_bureau_config_tenant_bureau", "tenant_id", "bureau", unique=True),
    )

    bureau: Mapped[CreditBureau] = mapped_column(SQLEnum(CreditBureau), nullable=False)

    subscriber_code: Mapped[str] = mapped_column(String(20), nullable=False)
    subscriber_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sic_code: Mapped[str | None] = mapped_column(String(4))

    portfolio_type: Mapped[str] = mapped_column(String(1), default="I", nullable=False)
    account_type: Mapped[str] = mapped_column(String(2), default="48", nullable=False)

    suppress_during_dispute: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_balance_to_report: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    min_days_delinquent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    reporting_schedule: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    field_mapping: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    batches: Mapped[list["BureauBatch"]] = relationship(
        "BureauBatch", back_populates="bureau_config"
    )


class BureauBatchStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    GENERATED = "generated"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PARTIALLY_ACCEPTED = "partially_accepted"


class BureauBatch(TenantScopedModel):
    """A batch export to a credit bureau."""

    __tablename__ = "bureau_batches"
    __table_args__ = (
        Index("ix_bureau_batch_config", "bureau_config_id"),
    )

    bureau_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bureau_configs.id"), nullable=False
    )

    reporting_period: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[BureauBatchStatus] = mapped_column(
        SQLEnum(BureauBatchStatus), default=BureauBatchStatus.PENDING, nullable=False
    )

    total_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accepted_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    suppressed_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    file_name: Mapped[str | None] = mapped_column(String(255))
    file_hash: Mapped[str | None] = mapped_column(String(64))

    filter_criteria: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    errors: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    generated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    bureau_config: Mapped["BureauConfig"] = relationship(
        "BureauConfig", back_populates="batches"
    )
    records: Mapped[list["BureauRecord"]] = relationship(
        "BureauRecord", back_populates="batch"
    )


class BureauRecordStatus(str, Enum):
    INCLUDED = "included"
    SUPPRESSED_DISPUTE = "suppressed_dispute"
    SUPPRESSED_BALANCE = "suppressed_balance"
    SUPPRESSED_MANUAL = "suppressed_manual"
    ERROR = "error"


class BureauRecord(TenantScopedModel):
    """An individual account record within a bureau batch."""

    __tablename__ = "bureau_records"
    __table_args__ = (
        Index("ix_bureau_records_batch", "batch_id"),
        Index("ix_bureau_records_account", "account_id"),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bureau_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )

    record_status: Mapped[BureauRecordStatus] = mapped_column(
        SQLEnum(BureauRecordStatus), default=BureauRecordStatus.INCLUDED, nullable=False
    )

    reported_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    account_status_code: Mapped[str] = mapped_column(String(2), nullable=False)
    payment_rating: Mapped[str | None] = mapped_column(String(1))
    date_of_first_delinquency: Mapped[date | None] = mapped_column(Date)
    special_comment: Mapped[str | None] = mapped_column(String(2))

    raw_segment: Mapped[str | None] = mapped_column(Text)
    suppression_reason: Mapped[str | None] = mapped_column(String(255))
    error_details: Mapped[str | None] = mapped_column(Text)

    batch: Mapped["BureauBatch"] = relationship("BureauBatch", back_populates="records")
