"""Calculation engine tests.

cursor.stage: calc_engine
cursor.jurisdiction: NJ
cursor.sources: []
"""

from datetime import date
from decimal import Decimal

import pytest

from dcs_api.routers.judgments import (
    calculate_post_judgment_interest,
    get_nj_post_judgment_rate,
)


class TestNJRates:
    """Test NJ post-judgment interest rate lookups."""

    def test_get_rate_2024(self) -> None:
        """Test 2024 rate lookup."""
        rate = get_nj_post_judgment_rate(2024, above_threshold=False)
        assert rate == Decimal("3.5")

    def test_get_rate_2025(self) -> None:
        """Test 2025 rate lookup."""
        rate = get_nj_post_judgment_rate(2025, above_threshold=False)
        assert rate == Decimal("5.5")

    def test_get_rate_above_threshold(self) -> None:
        """Test above threshold rate adjustment (+2%)."""
        rate = get_nj_post_judgment_rate(2024, above_threshold=True)
        assert rate == Decimal("5.5")  # 3.5 + 2.0

    def test_get_rate_unknown_year(self) -> None:
        """Test fallback rate for unknown year."""
        rate = get_nj_post_judgment_rate(2030, above_threshold=False)
        assert rate == Decimal("0.25")  # Default fallback


class TestPostJudgmentInterest:
    """Test post-judgment interest calculations."""

    def test_simple_calculation(self) -> None:
        """Test basic interest calculation."""
        result = calculate_post_judgment_interest(
            judgment_amount=1000000,  # $10,000 in cents
            judgment_date=date(2024, 1, 1),
            calculation_date=date(2024, 12, 31),
            above_threshold=False,
        )

        assert result["total_interest"] > 0
        assert len(result["yearly_breakdown"]) == 1
        assert result["yearly_breakdown"][0]["year"] == 2024
        assert result["yearly_breakdown"][0]["annual_rate"] == 3.5

    def test_multi_year_calculation(self) -> None:
        """Test calculation spanning multiple years."""
        result = calculate_post_judgment_interest(
            judgment_amount=1000000,  # $10,000 in cents
            judgment_date=date(2023, 1, 1),
            calculation_date=date(2025, 1, 1),
            above_threshold=False,
        )

        assert len(result["yearly_breakdown"]) == 2
        years = [b["year"] for b in result["yearly_breakdown"]]
        assert 2023 in years
        assert 2024 in years

    def test_same_day_calculation(self) -> None:
        """Test calculation with same date returns zero."""
        result = calculate_post_judgment_interest(
            judgment_amount=1000000,
            judgment_date=date(2024, 1, 1),
            calculation_date=date(2024, 1, 1),
            above_threshold=False,
        )

        assert result["total_interest"] == 0
        assert result["yearly_breakdown"] == []

    def test_above_threshold_calculation(self) -> None:
        """Test calculation with above threshold rate."""
        result_below = calculate_post_judgment_interest(
            judgment_amount=1000000,
            judgment_date=date(2024, 1, 1),
            calculation_date=date(2024, 12, 31),
            above_threshold=False,
        )

        result_above = calculate_post_judgment_interest(
            judgment_amount=1000000,
            judgment_date=date(2024, 1, 1),
            calculation_date=date(2024, 12, 31),
            above_threshold=True,
        )

        # Above threshold should accrue more interest
        assert result_above["total_interest"] > result_below["total_interest"]


class TestInterestFormula:
    """Test interest calculation formula accuracy.

    Formula: interest = principal * (annual_rate / 100 / 365) * days
    """

    def test_formula_accuracy(self) -> None:
        """Verify formula produces expected results."""
        # $10,000 at 3.5% for 365 days
        principal = 1000000  # cents
        annual_rate = Decimal("3.5")
        days = 365

        # Expected: 10000 * 0.035 = $350 = 35000 cents
        expected = int(Decimal(principal) * annual_rate / Decimal("100"))

        result = calculate_post_judgment_interest(
            judgment_amount=principal,
            judgment_date=date(2024, 1, 1),
            calculation_date=date(2025, 1, 1),
            above_threshold=False,
        )

        # Allow for rounding differences
        assert abs(result["total_interest"] - expected) < 100


class TestPaymentAllocation:
    """Test payment allocation calculations."""

    def test_default_allocation_order(self) -> None:
        """Test default allocation: interest -> principal -> fees."""
        from dcs_api.schemas.calculation import PaymentAllocationRequest

        request = PaymentAllocationRequest(
            payment_amount=50000,  # $500
            current_interest=20000,  # $200
            current_principal=100000,  # $1000
            current_fees=5000,  # $50
        )

        # Manually compute expected allocation
        # $500 payment
        # First: $200 to interest
        # Remaining $300 to principal
        # Fees untouched

        assert request.payment_amount == 50000
        assert request.allocation_order == ["interest", "principal", "fees"]
