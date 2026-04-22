"""Calculation engine.

Provides the canonical math used by the calculations / judgments / payments
routers. Two design goals:

1. **Defensibility.** Every public function returns step-by-step breakdowns,
   the policy-pack version that supplied the rate, and the source citation
   so the result can be reproduced years later.
2. **No floats for money.** All monetary inputs/outputs are integer cents;
   all rates and intermediates are `Decimal` with explicit quantization.

Authority for the formulas:
  - Simple interest: I = P * (r/365) * d  (actual/365 day count)
  - Compound interest: A = P * (1 + r/n)^(n*y)
  - NJ post-judgment: N.J. Court Rules R. 4:42-11(a) — annual SCP rate plus
    +2.0% above the $20,000 SCP threshold (R. 6:1-2(a)(1)).
  - NY post-judgment: CPLR § 5004(a) (9% default) and § 5004(b) (2% on
    consumer-debt judgments, eff. Apr. 30, 2022).

Non-legal guidance: This engine assists with calculations but does not
guarantee enforceability. Verify against current law and qualified counsel.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.models.compliance import (
    PolicyPack,
    PolicyPackStatus,
    RateTable,
    RateTableEntry,
    RateTableType,
)

logger = logging.getLogger(__name__)


CALCULATION_ENGINE_VERSION = "1.1.0"

CENTS = Decimal("1")        # quantize cents
RATE_Q = Decimal("0.00001")  # quantize daily rates to 5 dp


class InterestType(str, Enum):
    SIMPLE = "simple"
    COMPOUND_DAILY = "compound_daily"
    COMPOUND_MONTHLY = "compound_monthly"
    COMPOUND_ANNUALLY = "compound_annually"


class RoundingRule(str, Enum):
    FINAL_STEP = "final_step"   # Quantize only at the final cent conversion
    STEPWISE = "stepwise"       # Quantize each intermediate (less defensible)


@dataclass
class CalcStep:
    description: str
    formula: str
    values: str
    result: str

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "formula": self.formula,
            "values": self.values,
            "result": self.result,
        }


@dataclass
class InterestResult:
    principal_cents: int
    annual_rate: Decimal
    interest_type: InterestType
    start_date: date
    end_date: date
    days: int
    interest_cents: int
    total_cents: int
    daily_rate: Decimal
    formula: str
    steps: list[CalcStep] = field(default_factory=list)
    engine_version: str = CALCULATION_ENGINE_VERSION

    def to_dict(self) -> dict:
        return {
            "principal_cents": self.principal_cents,
            "annual_rate": str(self.annual_rate),
            "interest_type": self.interest_type.value,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "days": self.days,
            "interest_cents": self.interest_cents,
            "total_cents": self.total_cents,
            "daily_rate": str(self.daily_rate),
            "formula": self.formula,
            "steps": [s.to_dict() for s in self.steps],
            "engine_version": self.engine_version,
        }


@dataclass
class PostJudgmentResult:
    judgment_cents: int
    judgment_date: date
    calculation_date: date
    is_above_threshold: bool
    threshold_cents: int | None
    total_interest_cents: int
    current_balance_cents: int
    yearly_breakdown: list[dict]
    rate_source: str
    policy_pack_version: str | None
    policy_pack_id: uuid.UUID | None
    engine_version: str = CALCULATION_ENGINE_VERSION

    def to_dict(self) -> dict:
        return {
            "judgment_cents": self.judgment_cents,
            "judgment_date": self.judgment_date.isoformat(),
            "calculation_date": self.calculation_date.isoformat(),
            "is_above_threshold": self.is_above_threshold,
            "threshold_cents": self.threshold_cents,
            "total_interest_cents": self.total_interest_cents,
            "current_balance_cents": self.current_balance_cents,
            "yearly_breakdown": self.yearly_breakdown,
            "rate_source": self.rate_source,
            "policy_pack_version": self.policy_pack_version,
            "policy_pack_id": (
                str(self.policy_pack_id) if self.policy_pack_id else None
            ),
            "engine_version": self.engine_version,
        }


@dataclass
class AllocationResult:
    payment_cents: int
    allocations: dict[str, int]
    remaining_balances: dict[str, int]
    overpayment_cents: int
    order: list[str]
    engine_version: str = CALCULATION_ENGINE_VERSION

    def to_dict(self) -> dict:
        return {
            "payment_cents": self.payment_cents,
            "allocations": self.allocations,
            "remaining_balances": self.remaining_balances,
            "overpayment_cents": self.overpayment_cents,
            "order": self.order,
            "engine_version": self.engine_version,
        }


# ---------------------------------------------------------------------------
# Interest
# ---------------------------------------------------------------------------

def _to_cents(value: Decimal, rule: RoundingRule) -> int:
    if rule == RoundingRule.FINAL_STEP:
        return int(value.quantize(CENTS, rounding=ROUND_HALF_UP))
    return int(value)


def calculate_interest(
    *,
    principal_cents: int,
    annual_rate: Decimal,
    start_date: date,
    end_date: date,
    interest_type: InterestType = InterestType.SIMPLE,
    rounding: RoundingRule = RoundingRule.FINAL_STEP,
) -> InterestResult:
    """Compute simple or compound interest.

    Day count is actual/365 (the FDCPA / Reg F do not prescribe one; 365 is
    consistent with NJ Courts AOC notices and the historical CollectMax
    behavior we are migrating from).
    """
    if end_date <= start_date:
        raise ValueError("end_date must be after start_date")
    if principal_cents < 0:
        raise ValueError("principal must be non-negative")

    days = (end_date - start_date).days
    principal = Decimal(principal_cents)
    rate = Decimal(annual_rate)
    steps: list[CalcStep] = []

    if interest_type == InterestType.SIMPLE:
        daily_rate = (rate / Decimal("100") / Decimal("365"))
        interest = principal * daily_rate * Decimal(days)
        steps.extend([
            CalcStep(
                "Daily rate",
                "annual_rate / 100 / 365",
                f"{rate} / 100 / 365",
                str(daily_rate.quantize(RATE_Q)),
            ),
            CalcStep(
                "Interest",
                "principal * daily_rate * days",
                f"{principal} * {daily_rate.quantize(RATE_Q)} * {days}",
                str(interest),
            ),
        ])
        formula = "principal * (annual_rate/100/365) * days"
    else:
        n_map = {
            InterestType.COMPOUND_DAILY: 365,
            InterestType.COMPOUND_MONTHLY: 12,
            InterestType.COMPOUND_ANNUALLY: 1,
        }
        n = n_map[interest_type]
        r = rate / Decimal("100")
        years = Decimal(days) / Decimal("365")
        amount = principal * (Decimal(1) + r / Decimal(n)) ** (Decimal(n) * years)
        interest = amount - principal
        daily_rate = r / Decimal(n)
        steps.extend([
            CalcStep(
                "Rate per period",
                "r / n",
                f"{r} / {n}",
                str(daily_rate.quantize(RATE_Q)),
            ),
            CalcStep(
                "Compound amount",
                "principal * (1 + r/n)^(n*years)",
                f"{principal} * (1 + {r}/{n})^({n}*{years})",
                str(amount),
            ),
            CalcStep(
                "Interest",
                "amount - principal",
                f"{amount} - {principal}",
                str(interest),
            ),
        ])
        formula = "principal * (1 + annual_rate/100/n)^(n*years) - principal"

    interest_cents = _to_cents(interest, rounding)
    total_cents = principal_cents + interest_cents

    return InterestResult(
        principal_cents=principal_cents,
        annual_rate=rate,
        interest_type=interest_type,
        start_date=start_date,
        end_date=end_date,
        days=days,
        interest_cents=interest_cents,
        total_cents=total_cents,
        daily_rate=daily_rate.quantize(RATE_Q),
        formula=formula,
        steps=steps,
    )


# ---------------------------------------------------------------------------
# Post-judgment interest
# ---------------------------------------------------------------------------

async def calculate_post_judgment_interest(
    session: AsyncSession,
    *,
    jurisdiction: str,
    judgment_cents: int,
    judgment_date: date,
    calculation_date: date | None = None,
    is_consumer_debt: bool = False,
    is_above_threshold: bool | None = None,
) -> PostJudgmentResult:
    """Compute post-judgment interest using the active policy pack's rate table.

    NJ behavior (R. 4:42-11(a)):
      * Look up the SCP rate for each calendar year crossed.
      * If `is_above_threshold` is True (judgment principal > $20k), add
        the table's `above_threshold_adjustment` (+2.0%).

    NY behavior (CPLR § 5004):
      * If `is_consumer_debt` is True, use the
        POST_JUDGMENT_ABOVE_THRESHOLD table (which holds the 2% consumer
        rate from § 5004(b)). Otherwise use POST_JUDGMENT_STANDARD (9%
        per § 5004(a)).

    The function prorates daily across calendar-year boundaries so a
    judgment that crosses a year-end picks up the new rate on Jan 1.
    """
    calc_date = calculation_date or date.today()
    if calc_date <= judgment_date:
        raise ValueError("calculation_date must be after judgment_date")

    pack = await _load_active_pack(session, jurisdiction)
    if pack is None:
        raise ValueError(
            f"No active policy pack for jurisdiction {jurisdiction.upper()}"
        )

    # Pick rate table
    juris = jurisdiction.upper()[:2]
    if juris == "NY" and is_consumer_debt:
        table = await _get_rate_table(
            session, pack=pack, rate_type=RateTableType.POST_JUDGMENT_ABOVE_THRESHOLD
        )
        is_above_threshold_resolved = False
        threshold_cents = None
    else:
        table = await _get_rate_table(
            session, pack=pack, rate_type=RateTableType.POST_JUDGMENT_STANDARD
        )
        threshold_cents = table.threshold_amount if table else None
        if is_above_threshold is None:
            is_above_threshold_resolved = bool(
                threshold_cents is not None and judgment_cents > threshold_cents
            )
        else:
            is_above_threshold_resolved = is_above_threshold

    if table is None:
        raise ValueError(
            f"Policy pack {pack.version} has no post-judgment rate table"
        )

    rates_by_year = await _rates_by_year(session, table)
    above_adj = (
        Decimal(table.above_threshold_adjustment)
        if table.above_threshold_adjustment is not None
        and is_above_threshold_resolved
        else Decimal("0")
    )

    breakdown: list[dict] = []
    total_interest = Decimal("0")
    cur = judgment_date
    while cur < calc_date:
        period_end = min(date(cur.year + 1, 1, 1), calc_date)
        days = (period_end - cur).days
        if days <= 0:
            break

        base_rate = rates_by_year.get(cur.year)
        if base_rate is None:
            # fall back to most-recent entry <= cur.year, then last year overall
            candidates = [y for y in rates_by_year if y <= cur.year]
            if candidates:
                base_rate = rates_by_year[max(candidates)]
            else:
                base_rate = rates_by_year[max(rates_by_year)]

        annual_rate = base_rate + above_adj
        daily = annual_rate / Decimal("100") / Decimal("365")
        interest = Decimal(judgment_cents) * daily * Decimal(days)
        breakdown.append({
            "year": cur.year,
            "period_start": cur.isoformat(),
            "period_end": period_end.isoformat(),
            "days": days,
            "annual_rate": str(annual_rate),
            "above_threshold_adjustment": str(above_adj),
            "daily_rate": str(daily.quantize(RATE_Q)),
            "interest_cents": int(interest.quantize(CENTS, rounding=ROUND_HALF_UP)),
        })
        total_interest += interest
        cur = period_end

    total_int_cents = int(total_interest.quantize(CENTS, rounding=ROUND_HALF_UP))

    return PostJudgmentResult(
        judgment_cents=judgment_cents,
        judgment_date=judgment_date,
        calculation_date=calc_date,
        is_above_threshold=is_above_threshold_resolved,
        threshold_cents=threshold_cents,
        total_interest_cents=total_int_cents,
        current_balance_cents=judgment_cents + total_int_cents,
        yearly_breakdown=breakdown,
        rate_source=table.source_name,
        policy_pack_version=pack.version,
        policy_pack_id=pack.id,
    )


# ---------------------------------------------------------------------------
# Payment allocation
# ---------------------------------------------------------------------------

DEFAULT_ALLOCATION_ORDER: tuple[str, ...] = ("interest", "principal", "fees")


def allocate_payment(
    *,
    payment_cents: int,
    interest_cents: int,
    principal_cents: int,
    fees_cents: int,
    order: Sequence[str] = DEFAULT_ALLOCATION_ORDER,
    jurisdiction_locks: Sequence[str] = (),
) -> AllocationResult:
    """Allocate a payment across interest, principal, and fees.

    Default order (per docs/06_calculation_engine.md): interest -> principal
    -> fees. Tenants may override the order via `order` unless the bucket is
    listed in `jurisdiction_locks` (some states forbid moving fees ahead of
    principal). When a lock is violated, the function falls back to the
    default order.
    """
    if payment_cents < 0:
        raise ValueError("payment must be non-negative")
    for name, value in (
        ("interest", interest_cents),
        ("principal", principal_cents),
        ("fees", fees_cents),
    ):
        if value < 0:
            raise ValueError(f"{name} balance must be non-negative")

    use_order = list(order) if order else list(DEFAULT_ALLOCATION_ORDER)
    if any(b in jurisdiction_locks for b in use_order) and tuple(use_order) != DEFAULT_ALLOCATION_ORDER:
        logger.warning(
            "Allocation order %s violates jurisdiction lock; using default",
            use_order,
        )
        use_order = list(DEFAULT_ALLOCATION_ORDER)

    balances = {
        "interest": interest_cents,
        "principal": principal_cents,
        "fees": fees_cents,
    }
    allocations: dict[str, int] = {b: 0 for b in balances}
    remaining = payment_cents
    for bucket in use_order:
        if remaining <= 0:
            break
        if bucket not in balances:
            continue
        take = min(remaining, balances[bucket])
        allocations[bucket] = take
        balances[bucket] -= take
        remaining -= take

    return AllocationResult(
        payment_cents=payment_cents,
        allocations=allocations,
        remaining_balances=balances,
        overpayment_cents=remaining,
        order=use_order,
    )


# ---------------------------------------------------------------------------
# Internal: pack / rate-table loaders
# ---------------------------------------------------------------------------

async def _load_active_pack(
    session: AsyncSession, jurisdiction: str
) -> PolicyPack | None:
    juris = (jurisdiction or "").upper()[:2]
    if not juris:
        return None
    result = await session.execute(
        select(PolicyPack).where(
            PolicyPack.jurisdiction == juris,
            PolicyPack.status == PolicyPackStatus.ACTIVE,
        )
    )
    return result.scalar_one_or_none()


async def _get_rate_table(
    session: AsyncSession, *, pack: PolicyPack, rate_type: RateTableType
) -> RateTable | None:
    result = await session.execute(
        select(RateTable).where(
            RateTable.policy_pack_id == pack.id,
            RateTable.rate_type == rate_type,
        )
    )
    return result.scalar_one_or_none()


async def _rates_by_year(
    session: AsyncSession, table: RateTable
) -> dict[int, Decimal]:
    result = await session.execute(
        select(RateTableEntry).where(RateTableEntry.rate_table_id == table.id)
    )
    return {e.effective_year: Decimal(e.rate) for e in result.scalars()}
