"""Bank reconciliation engine.

Handles importing bank statement files and auto-matching
statement lines to trust account transactions.
"""

import csv
import io
from datetime import date

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.models.trust import (
    BankReconciliation,
    ReconciliationItem,
    ReconciliationMatchStatus,
    TrustTransaction,
)


async def import_bank_statement(
    session: AsyncSession,
    reconciliation: BankReconciliation,
    file_content: str,
    config: dict,
) -> list[ReconciliationItem]:
    """Parse a bank statement file and create reconciliation items."""
    items = []
    delimiter = config.get("delimiter", ",")
    date_column = config.get("date_column", 0)
    amount_column = config.get("amount_column", 1)
    reference_column = config.get("reference_column", 2)
    description_column = config.get("description_column", 3)
    skip_header = config.get("skip_header", True)
    amount_multiplier = config.get("amount_multiplier", 100)

    reader = csv.reader(io.StringIO(file_content), delimiter=delimiter)
    for i, row in enumerate(reader):
        if skip_header and i == 0:
            continue
        if not row or len(row) <= max(date_column, amount_column):
            continue

        try:
            stmt_date = _parse_date(row[date_column].strip())
            raw_amount = row[amount_column].strip().replace(",", "").replace("$", "")
            stmt_amount = int(float(raw_amount) * amount_multiplier)
            stmt_ref = row[reference_column].strip() if len(row) > reference_column else None
            stmt_desc = row[description_column].strip() if len(row) > description_column else None
        except (ValueError, IndexError):
            continue

        item = ReconciliationItem(
            tenant_id=reconciliation.tenant_id,
            reconciliation_id=reconciliation.id,
            match_status=ReconciliationMatchStatus.UNMATCHED,
            statement_amount=stmt_amount,
            statement_date=stmt_date,
            statement_reference=stmt_ref,
            statement_description=stmt_desc,
        )
        items.append(item)
        session.add(item)

    return items


async def auto_match_items(
    session: AsyncSession,
    reconciliation: BankReconciliation,
) -> dict:
    """Auto-match unmatched statement items to trust transactions."""
    items_query = select(ReconciliationItem).where(
        and_(
            ReconciliationItem.reconciliation_id == reconciliation.id,
            ReconciliationItem.match_status == ReconciliationMatchStatus.UNMATCHED,
        )
    )
    result = await session.execute(items_query)
    items = list(result.scalars().all())

    matched = 0
    unmatched = 0

    for item in items:
        if not item.statement_amount:
            unmatched += 1
            continue

        tx_query = select(TrustTransaction).where(
            and_(
                TrustTransaction.trust_account_id == reconciliation.trust_account_id,
                TrustTransaction.amount == item.statement_amount,
                TrustTransaction.is_reconciled.is_(False),
            )
        )

        if item.statement_reference:
            tx_query = tx_query.where(
                TrustTransaction.reference_number == item.statement_reference
            )

        tx_result = await session.execute(tx_query.limit(1))
        transaction = tx_result.scalar_one_or_none()

        if transaction:
            item.match_status = ReconciliationMatchStatus.MATCHED
            item.book_transaction_id = transaction.id
            item.book_amount = transaction.amount
            item.difference = (item.statement_amount or 0) - transaction.amount
            transaction.is_reconciled = True
            matched += 1
        else:
            unmatched += 1

    return {"matched": matched, "unmatched": unmatched, "total": len(items)}


def _parse_date(date_str: str) -> date | None:
    """Parse common date formats."""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y"):
        try:
            return date.fromisoformat(date_str) if "-" in date_str else None
        except ValueError:
            pass
        try:
            from datetime import datetime
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None
