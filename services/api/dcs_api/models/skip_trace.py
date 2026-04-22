"""Skip tracing models.

Tracks requests to and results from skip tracing vendors
(LexisNexis, TransUnion TLO, etc.) for locating consumers.
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


class SkipVendor(str, Enum):
    LEXISNEXIS = "lexisnexis"
    TRANSUNION_TLO = "transunion_tlo"
    EXPERIAN = "experian"
    EQUIFAX = "equifax"
    IDI = "idi"
    TRACERS = "tracers"
    MANUAL = "manual"
    OTHER = "other"


class SkipRequestType(str, Enum):
    FULL_LOCATE = "full_locate"
    PHONE_APPEND = "phone_append"
    ADDRESS_UPDATE = "address_update"
    EMPLOYER_SEARCH = "employer_search"
    ASSET_SEARCH = "asset_search"
    DECEASED_CHECK = "deceased_check"
    IDENTITY_VERIFY = "identity_verify"
    BATCH = "batch"


class SkipRequestStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    NO_HIT = "no_hit"
    PARTIAL_HIT = "partial_hit"
    ERROR = "error"
    CANCELLED = "cancelled"


class SkipTraceRequest(TenantScopedModel):
    """A skip trace request for locating a consumer."""

    __tablename__ = "skip_trace_requests"
    __table_args__ = (
        Index("ix_skip_request_account", "account_id"),
        Index("ix_skip_request_status", "status"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    consumer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consumers.id"), nullable=False
    )

    vendor: Mapped[SkipVendor] = mapped_column(SQLEnum(SkipVendor), nullable=False)
    request_type: Mapped[SkipRequestType] = mapped_column(
        SQLEnum(SkipRequestType), nullable=False
    )
    status: Mapped[SkipRequestStatus] = mapped_column(
        SQLEnum(SkipRequestStatus), default=SkipRequestStatus.PENDING, nullable=False
    )

    search_parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    vendor_reference: Mapped[str | None] = mapped_column(String(255))

    cost_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    error_message: Mapped[str | None] = mapped_column(Text)

    results: Mapped[list["SkipTraceResult"]] = relationship(
        "SkipTraceResult", back_populates="request"
    )


class SkipResultType(str, Enum):
    ADDRESS = "address"
    PHONE = "phone"
    EMAIL = "email"
    EMPLOYER = "employer"
    ASSET = "asset"
    RELATIVE = "relative"
    ASSOCIATE = "associate"
    DECEASED = "deceased"
    BANKRUPTCY = "bankruptcy"


class SkipTraceResult(TenantScopedModel):
    """A result from a skip trace request."""

    __tablename__ = "skip_trace_results"
    __table_args__ = (
        Index("ix_skip_result_request", "request_id"),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skip_trace_requests.id", ondelete="CASCADE"),
        nullable=False,
    )

    result_type: Mapped[SkipResultType] = mapped_column(
        SQLEnum(SkipResultType), nullable=False
    )
    confidence_score: Mapped[int | None] = mapped_column(Integer)

    data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    is_applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    request: Mapped["SkipTraceRequest"] = relationship(
        "SkipTraceRequest", back_populates="results"
    )
