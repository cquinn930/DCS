"""Calculation models.

Tracks calculation requests and results for audit and defensibility.
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
from sqlalchemy.orm import Mapped, mapped_column

from dcs_api.models.base import TenantScopedModel


class CalculationType(str, Enum):
    """Types of calculations."""

    SIMPLE_INTEREST = "simple_interest"
    COMPOUND_INTEREST = "compound_interest"
    POST_JUDGMENT_INTEREST = "post_judgment_interest"
    PAYMENT_ALLOCATION = "payment_allocation"
    BALANCE_COMPUTATION = "balance_computation"
    STATUTE_OF_LIMITATIONS = "statute_of_limitations"


class CalculationRequest(TenantScopedModel):
    """Calculation request record.

    Stores the inputs and metadata for any calculation performed.
    """

    __tablename__ = "calculation_requests"
    __table_args__ = (
        Index("ix_calc_request_tenant", "tenant_id"),
        Index("ix_calc_request_account", "account_id"),
    )

    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    judgment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    calculation_type: Mapped[CalculationType] = mapped_column(
        SQLEnum(CalculationType),
        nullable=False,
    )

    # Input parameters
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Structure varies by type:
    # {
    #   "principal": 10000,           # cents
    #   "rate": "5.50",               # annual %
    #   "start_date": "2024-01-01",
    #   "end_date": "2024-12-31",
    #   "rounding_rule": "final_step",
    #   "day_count": "actual_365",
    #   ...
    # }

    # Policy reference
    policy_pack_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    policy_pack_version: Mapped[str | None] = mapped_column(String(50))
    rate_table_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Version tracking
    engine_version: Mapped[str] = mapped_column(String(50), nullable=False)
    code_version: Mapped[str | None] = mapped_column(String(50))

    # Audit
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class CalculationResult(TenantScopedModel):
    """Calculation result record.

    Stores the outputs and audit trail for any calculation.
    """

    __tablename__ = "calculation_results"
    __table_args__ = (
        Index("ix_calc_result_request", "request_id"),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calculation_requests.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Outputs
    outputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Structure varies by type:
    # {
    #   "interest_amount": 550,       # cents
    #   "days_accrued": 365,
    #   "daily_rate": "0.0001507",
    #   "formula": "principal * daily_rate * days",
    #   ...
    # }

    # Detailed breakdown (for defensibility)
    breakdown: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # {
    #   "steps": [
    #     {"description": "Calculate daily rate", "value": "5.50 / 100 / 365", "result": "0.0001507"},
    #     {"description": "Calculate interest", "value": "10000 * 0.0001507 * 365", "result": "550"},
    #   ]
    # }

    # Rate source for audit
    rate_source: Mapped[str | None] = mapped_column(String(255))
    rate_effective_date: Mapped[date | None] = mapped_column(Date)
    source_snapshot_hash: Mapped[str | None] = mapped_column(String(64))

    # Status
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    validation_errors: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Timing
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
