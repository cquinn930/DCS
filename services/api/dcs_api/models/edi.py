"""Electronic Data Interchange (EDI) models.

Handles structured data exchange with creditors, courts, vendors,
and other agencies using configurable record layouts.
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


class ExchangeDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    BIDIRECTIONAL = "bidirectional"


class ExchangeFormatType(str, Enum):
    FIXED_WIDTH = "fixed_width"
    CSV = "csv"
    TAB_DELIMITED = "tab_delimited"
    JSON = "json"
    XML = "xml"
    CUSTOM = "custom"


class DataExchangeFormat(TenantScopedModel):
    """A registered data exchange format (EDI standard).

    Defines the record layout, field positions, and mapping rules
    for exchanging data with external partners.
    """

    __tablename__ = "data_exchange_formats"
    __table_args__ = (
        Index("ix_exchange_format_tenant_code", "tenant_id", "code", unique=True),
    )

    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)

    direction: Mapped[ExchangeDirection] = mapped_column(
        SQLEnum(ExchangeDirection), nullable=False
    )
    format_type: Mapped[ExchangeFormatType] = mapped_column(
        SQLEnum(ExchangeFormatType), nullable=False
    )

    record_layouts: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    field_mappings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    header_layout: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    trailer_layout: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    validation_rules: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    transform_rules: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    partners: Mapped[list["DataExchangePartner"]] = relationship(
        "DataExchangePartner", back_populates="exchange_format"
    )


class DataExchangePartner(TenantScopedModel):
    """A trading partner configuration for data exchange."""

    __tablename__ = "data_exchange_partners"
    __table_args__ = (
        Index("ix_exchange_partner_tenant", "tenant_id"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    partner_code: Mapped[str] = mapped_column(String(30), nullable=False)
    exchange_format_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_exchange_formats.id"), nullable=False
    )

    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(320))

    connection_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    partner_settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    exchange_format: Mapped["DataExchangeFormat"] = relationship(
        "DataExchangeFormat", back_populates="partners"
    )
    batches: Mapped[list["DataExchangeBatch"]] = relationship(
        "DataExchangeBatch", back_populates="partner"
    )


class ExchangeBatchStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DataExchangeBatch(TenantScopedModel):
    """A batch of records exchanged with a partner."""

    __tablename__ = "data_exchange_batches"
    __table_args__ = (
        Index("ix_exchange_batch_partner", "partner_id"),
        Index("ix_exchange_batch_status", "status"),
    )

    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_exchange_partners.id"), nullable=False
    )
    direction: Mapped[ExchangeDirection] = mapped_column(
        SQLEnum(ExchangeDirection), nullable=False
    )

    status: Mapped[ExchangeBatchStatus] = mapped_column(
        SQLEnum(ExchangeBatchStatus), default=ExchangeBatchStatus.PENDING, nullable=False
    )

    file_name: Mapped[str | None] = mapped_column(String(255))
    file_hash: Mapped[str | None] = mapped_column(String(64))

    total_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_accounts_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accounts_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    errors: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    partner: Mapped["DataExchangePartner"] = relationship(
        "DataExchangePartner", back_populates="batches"
    )
