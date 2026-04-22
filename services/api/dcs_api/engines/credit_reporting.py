"""Credit bureau reporting engine.

Generates Metro II format segments for credit bureau reporting.
Handles account eligibility, dispute suppression, and batch generation.
"""

from datetime import date, datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.models.account import Account, AccountStatus
from dcs_api.models.consumer import Consumer
from dcs_api.models.credit_reporting import (
    BureauBatch,
    BureauBatchStatus,
    BureauConfig,
    BureauRecord,
    BureauRecordStatus,
)
from dcs_api.models.account import Dispute, DisputeStatus


async def generate_bureau_batch(
    session: AsyncSession,
    config: BureauConfig,
    tenant_id,
    *,
    reporting_period: date | None = None,
    generated_by_id=None,
) -> BureauBatch:
    """Generate a new credit bureau batch from eligible accounts."""
    if reporting_period is None:
        reporting_period = date.today()

    batch = BureauBatch(
        tenant_id=tenant_id,
        bureau_config_id=config.id,
        reporting_period=reporting_period,
        status=BureauBatchStatus.GENERATING,
        generated_by_id=generated_by_id,
    )
    session.add(batch)
    await session.flush()

    accounts = await _find_eligible_accounts(session, config, tenant_id)

    total = 0
    suppressed = 0

    for account in accounts:
        is_suppressed, reason = await _check_suppression(session, config, account)

        if is_suppressed:
            record = BureauRecord(
                tenant_id=tenant_id,
                batch_id=batch.id,
                account_id=account.id,
                record_status=BureauRecordStatus.SUPPRESSED_DISPUTE
                if "dispute" in (reason or "").lower()
                else BureauRecordStatus.SUPPRESSED_BALANCE,
                reported_balance=account.total_balance,
                account_status_code="DA",
                suppression_reason=reason,
            )
            suppressed += 1
        else:
            status_code = _determine_status_code(account)
            record = BureauRecord(
                tenant_id=tenant_id,
                batch_id=batch.id,
                account_id=account.id,
                record_status=BureauRecordStatus.INCLUDED,
                reported_balance=account.total_balance,
                account_status_code=status_code,
                payment_rating=_determine_payment_rating(account),
                date_of_first_delinquency=account.date_of_first_delinquency.date()
                if account.date_of_first_delinquency else None,
                raw_segment=_build_base_segment(config, account, status_code),
            )

        session.add(record)
        total += 1

    batch.total_records = total
    batch.suppressed_records = suppressed
    batch.accepted_records = total - suppressed
    batch.status = BureauBatchStatus.GENERATED
    batch.generated_at = datetime.now(timezone.utc)

    return batch


async def _find_eligible_accounts(
    session: AsyncSession,
    config: BureauConfig,
    tenant_id,
) -> list[Account]:
    """Find accounts eligible for bureau reporting."""
    query = select(Account).where(
        and_(
            Account.tenant_id == tenant_id,
            Account.status.in_([
                AccountStatus.ACTIVE,
                AccountStatus.HOLD,
                AccountStatus.LEGAL_HOLD,
            ]),
            Account.total_balance >= config.min_balance_to_report,
        )
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def _check_suppression(
    session: AsyncSession,
    config: BureauConfig,
    account: Account,
) -> tuple[bool, str | None]:
    """Check if an account should be suppressed from reporting."""
    if config.suppress_during_dispute:
        dispute_query = select(Dispute).where(
            and_(
                Dispute.account_id == account.id,
                Dispute.status.in_([DisputeStatus.PENDING, DisputeStatus.UNDER_REVIEW]),
            )
        )
        result = await session.execute(dispute_query)
        if result.scalar_one_or_none():
            return True, "Active dispute on account"

    if account.total_balance < config.min_balance_to_report:
        return True, f"Balance below minimum ({config.min_balance_to_report})"

    return False, None


def _determine_status_code(account: Account) -> str:
    """Map account status to Metro II account status code."""
    mapping = {
        AccountStatus.ACTIVE: "11",
        AccountStatus.HOLD: "11",
        AccountStatus.LEGAL_HOLD: "11",
        AccountStatus.PAID_IN_FULL: "13",
        AccountStatus.SETTLED: "65",
        AccountStatus.CLOSED: "97",
        AccountStatus.RECALLED: "DA",
    }
    return mapping.get(account.status, "11")


def _determine_payment_rating(account: Account) -> str:
    """Determine payment rating based on account data."""
    if account.status == AccountStatus.PAID_IN_FULL:
        return "0"
    return "L"


def _build_base_segment(config: BureauConfig, account: Account, status_code: str) -> str:
    """Build the Metro II base segment for an account."""
    subscriber = (config.subscriber_code or "").ljust(10)
    portfolio = config.portfolio_type or "I"
    acct_type = config.account_type or "48"
    acct_ref = (account.account_reference or "").ljust(30)

    balance_str = str(account.total_balance).rjust(9, "0")

    return f"{subscriber}{portfolio}{acct_type}{status_code}{acct_ref}{balance_str}"
