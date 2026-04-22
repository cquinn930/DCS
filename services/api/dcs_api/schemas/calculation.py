"""Calculation schemas.

These schemas define the inputs and outputs for the calculation engine.
All calculations include audit metadata for defensibility.

Non-legal guidance: Calculation results should be validated against
jurisdiction-specific rules and verified by qualified personnel.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.calculation import CalculationType
from dcs_api.schemas.common import AuditMetadata


class InterestCalculationRequest(BaseModel):
    """Simple or compound interest calculation request.

    Implements formulas from 06_calculation_engine.md:
    - Simple: interest = principal * (rate/100/365) * days
    - Compound: amount = principal * (1 + r/n)^(n*years)
    """

    principal: int = Field(..., gt=0, description="Principal amount in cents")
    annual_rate: Decimal = Field(..., ge=0, le=100, description="Annual interest rate %")
    start_date: date
    end_date: date
    interest_type: str = Field(
        default="simple",
        pattern="^(simple|compound_daily|compound_monthly|compound_annually)$",
    )
    rounding_rule: str = Field(
        default="final_step",
        pattern="^(final_step|stepwise)$",
    )


class InterestCalculationResponse(BaseModel):
    """Interest calculation result."""

    principal: int  # cents
    annual_rate: Decimal
    interest_type: str
    start_date: date
    end_date: date
    days: int
    interest_amount: int  # cents
    total_amount: int  # cents

    # Breakdown for audit
    daily_rate: Decimal
    formula: str
    steps: list[dict[str, Any]]

    # Audit metadata
    audit: AuditMetadata


class PostJudgmentInterestRequest(BaseModel):
    """Post-judgment interest calculation request.

    Uses post-judgment rates from the active policy pack:
      - NJ: N.J. Court Rules, R. 4:42-11(a) (annual AOC Notice to the Bar);
            +2.0% above the $20,000 SCP threshold (R. 6:1-2(a)(1)).
      - NY: CPLR § 5004(a) default 9%; § 5004(b) consumer-debt rate 2%
            (eff. Apr. 30, 2022).
    Rate determined by judgment year, jurisdiction, and consumer/threshold flag.
    """

    judgment_amount: int = Field(..., gt=0, description="Judgment amount in cents")
    judgment_date: date
    calculation_date: date
    jurisdiction: str = Field(default="NJ", min_length=2, max_length=2)
    is_above_threshold: bool | None = None  # Auto-detect if not specified


class PostJudgmentInterestResponse(BaseModel):
    """Post-judgment interest calculation result."""

    judgment_amount: int  # cents
    judgment_date: date
    calculation_date: date
    days_accrued: int
    total_interest: int  # cents
    current_balance: int  # cents

    # Rate details
    rates_applied: list[dict[str, Any]]
    # [{"year": 2024, "rate": 3.5, "days": 365, "interest": 350}, ...]

    # Threshold
    is_above_threshold: bool
    threshold_amount: int | None = None  # cents

    # Audit
    audit: AuditMetadata


class PaymentAllocationRequest(BaseModel):
    """Payment allocation calculation request.

    Default allocation: interest -> principal -> fees
    Configurable per tenant unless jurisdiction forbids changes.
    """

    payment_amount: int = Field(..., gt=0, description="Payment amount in cents")
    current_interest: int = Field(..., ge=0)
    current_principal: int = Field(..., ge=0)
    current_fees: int = Field(..., ge=0)
    allocation_order: list[str] = Field(
        default=["interest", "principal", "fees"],
        description="Allocation priority order",
    )


class PaymentAllocationResponse(BaseModel):
    """Payment allocation result."""

    payment_amount: int  # cents
    allocations: dict[str, int]  # {"interest": X, "principal": Y, "fees": Z}
    remaining_balances: dict[str, int]
    overpayment: int  # cents, if any

    # Audit
    audit: AuditMetadata


class CalculationRequest(BaseModel):
    """Generic calculation request wrapper."""

    calculation_type: CalculationType
    inputs: dict[str, Any]
    account_id: uuid.UUID | None = None
    judgment_id: uuid.UUID | None = None


class CalculationResponse(BaseModel):
    """Generic calculation response wrapper."""

    request_id: uuid.UUID
    calculation_type: CalculationType
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    breakdown: list[dict[str, Any]]
    is_valid: bool
    validation_errors: list[str]
    completed_at: datetime
    duration_ms: int

    # Audit
    audit: AuditMetadata
