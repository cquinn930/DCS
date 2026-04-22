"""Compliance models: policy packs, rate tables, and rules.

These models implement the jurisdiction-specific compliance framework
including interest rates, statute of limitations, and usury rules.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

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

from dcs_api.models.base import BaseModel

if TYPE_CHECKING:
    pass


class PolicyPackStatus(str, Enum):
    """Policy pack lifecycle status."""

    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class PolicyPack(BaseModel):
    """Jurisdiction-specific policy pack.

    Contains all compliance rules, rates, and templates for a jurisdiction.
    Policy packs are versioned and immutable once active.
    """

    __tablename__ = "policy_packs"
    __table_args__ = (
        Index("ix_policy_pack_jurisdiction", "jurisdiction", "status"),
    )

    # Identity
    jurisdiction: Mapped[str] = mapped_column(String(2), nullable=False)  # State code
    version: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., nj-2025.1
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Lifecycle
    status: Mapped[PolicyPackStatus] = mapped_column(
        SQLEnum(PolicyPackStatus),
        default=PolicyPackStatus.DRAFT,
        nullable=False,
    )
    effective_start: Mapped[date] = mapped_column(Date, nullable=False)
    effective_end: Mapped[date | None] = mapped_column(Date)

    # Source verification
    sources: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # Structure: {"fdcpa": {"url": "...", "hash": "...", "verified_date": "..."}, ...}

    # Contact rules
    contact_window_start: Mapped[str] = mapped_column(
        String(5), default="08:00", nullable=False
    )  # HH:MM
    contact_window_end: Mapped[str] = mapped_column(String(5), default="21:00", nullable=False)
    max_daily_contacts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_weekly_contacts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Validation notice
    validation_notice_days: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    dispute_response_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    # Licensing
    license_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    bond_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_bond_amount: Mapped[int | None] = mapped_column(Integer)  # cents

    # Notice templates (references)
    notice_templates: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    rate_tables: Mapped[list["RateTable"]] = relationship("RateTable", back_populates="policy_pack")
    sol_rules: Mapped[list["StatuteOfLimitationsRule"]] = relationship(
        "StatuteOfLimitationsRule", back_populates="policy_pack"
    )
    usury_rules: Mapped[list["UsuryRule"]] = relationship(
        "UsuryRule", back_populates="policy_pack"
    )


class RateTableType(str, Enum):
    """Types of rate tables."""

    POST_JUDGMENT_STANDARD = "post_judgment_standard"
    POST_JUDGMENT_ABOVE_THRESHOLD = "post_judgment_above_threshold"
    CONTRACTUAL = "contractual"
    STATUTORY = "statutory"


class RateTable(BaseModel):
    """Rate table for interest calculations.

    Stores interest rates by year/period for a jurisdiction.
    """

    __tablename__ = "rate_tables"
    __table_args__ = (
        Index("ix_rate_table_pack_type", "policy_pack_id", "rate_type"),
    )

    policy_pack_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policy_packs.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rate_type: Mapped[RateTableType] = mapped_column(SQLEnum(RateTableType), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Source
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_hash: Mapped[str | None] = mapped_column(String(64))

    # Threshold (for above/below Special Civil Part)
    threshold_amount: Mapped[int | None] = mapped_column(Integer)  # cents
    above_threshold_adjustment: Mapped[Decimal | None] = mapped_column(Numeric(8, 5))

    # Relationships
    policy_pack: Mapped["PolicyPack"] = relationship("PolicyPack", back_populates="rate_tables")
    entries: Mapped[list["RateTableEntry"]] = relationship(
        "RateTableEntry", back_populates="rate_table"
    )


class RateTableEntry(BaseModel):
    """Individual rate table entry.

    One entry per year/period with the applicable rate.
    """

    __tablename__ = "rate_table_entries"
    __table_args__ = (
        Index("ix_rate_entry_table_year", "rate_table_id", "effective_year", unique=True),
    )

    rate_table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rate_tables.id", ondelete="CASCADE"),
        nullable=False,
    )

    effective_year: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date)
    rate: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)  # Annual %

    # Relationships
    rate_table: Mapped["RateTable"] = relationship("RateTable", back_populates="entries")


class DebtCategory(str, Enum):
    """Categories of debt for SOL purposes."""

    WRITTEN_CONTRACT = "written_contract"
    ORAL_CONTRACT = "oral_contract"
    PROMISSORY_NOTE = "promissory_note"
    OPEN_ACCOUNT = "open_account"
    JUDGMENT = "judgment"


class StatuteOfLimitationsRule(BaseModel):
    """Statute of limitations rule.

    Defines how long debt is legally enforceable by type.
    """

    __tablename__ = "statute_of_limitations_rules"
    __table_args__ = (
        Index("ix_sol_pack_category", "policy_pack_id", "debt_category", unique=True),
    )

    policy_pack_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policy_packs.id", ondelete="CASCADE"),
        nullable=False,
    )

    debt_category: Mapped[DebtCategory] = mapped_column(SQLEnum(DebtCategory), nullable=False)
    limitation_years: Mapped[int] = mapped_column(Integer, nullable=False)
    statute_citation: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    policy_pack: Mapped["PolicyPack"] = relationship("PolicyPack", back_populates="sol_rules")


class UsuryRule(BaseModel):
    """Usury limit rule.

    Defines maximum allowable interest rates by debt type.
    """

    __tablename__ = "usury_rules"
    __table_args__ = (
        Index("ix_usury_pack_category", "policy_pack_id", "debt_category"),
    )

    policy_pack_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policy_packs.id", ondelete="CASCADE"),
        nullable=False,
    )

    debt_category: Mapped[DebtCategory] = mapped_column(SQLEnum(DebtCategory), nullable=False)
    max_rate: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)  # Annual %
    is_criminal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    statute_citation: Mapped[str | None] = mapped_column(String(255))
    exemptions: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    policy_pack: Mapped["PolicyPack"] = relationship("PolicyPack", back_populates="usury_rules")
