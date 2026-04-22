#!/usr/bin/env python3
"""Update account balances from CollectMax AcctBals.csv.

CollectMax stores per-claim balances in AcctBals with two sources:
  1. Columns: PRINBAL, INTBAL, FEEBAL, COSTBAL, OTHERBAL, OVERPAYBAL
  2. BALANCES field with ID* codes (Individual Debtor level):
     IDPPRJ_O = Original principal, IDPPRJ = Current principal (pre-judgment),
     IDPPOJ = Principal (post-judgment), IDIPRJ/IDIPOJ = Interest,
     IDCPRJ/IDCPOJ = Costs, IDNPRJ/IDNPOJ = other fees
"""

import asyncio
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

import asyncpg

DATA_DIR = Path(__file__).parent / "flg-data"
DB_URL = "postgresql://dcs:dcs@localhost:5432/dcs"
BATCH = 500
ZERO = Decimal(0)


def parse_decimal(val: str) -> Decimal:
    if not val or not val.strip():
        return ZERO
    try:
        return Decimal(val.strip())
    except (InvalidOperation, ValueError):
        return ZERO


def parse_balances(raw: str) -> dict[str, Decimal]:
    """Parse CollectMax BALANCES key=value field."""
    result = {}
    if not raw:
        return result
    for line in raw.strip().splitlines():
        line = line.strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        try:
            result[key] = Decimal(val)
        except (InvalidOperation, ValueError):
            pass
    return result


def cents(d: Decimal) -> int:
    return int(round(d * 100))


async def main():
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=5)

    tid = await pool.fetchval("SELECT id FROM tenants WHERE slug='flg'")
    if not tid:
        print("FLG tenant not found")
        return

    print("Loading PK mappings...")
    pk_rows = await pool.fetch("SELECT cm_pk, dcs_id FROM _migration_pk_map")
    pk_map = {r["cm_pk"]: r["dcs_id"] for r in pk_rows}
    print(f"  {len(pk_map):,} mappings loaded")

    print("Building claim → aroot index from Claim.csv...")
    claim_to_aroot = {}
    claim_csv = DATA_DIR / "Claim.csv"
    with open(claim_csv, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cpk = row.get("PKCLAIM", "").strip()
            arpk = row.get("PKAROOT", "").strip()
            if cpk and arpk:
                claim_to_aroot[cpk] = arpk
    print(f"  {len(claim_to_aroot):,} claims indexed")

    print("Processing AcctBals.csv...")
    updates = []
    skipped = 0
    processed = 0
    no_match = no_acct = no_bal = 0

    acctbals_csv = DATA_DIR / "AcctBals.csv"
    with open(acctbals_csv, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            file_pk = row.get("PKFILE", "").strip()
            if not file_pk:
                skipped += 1
                continue

            aroot_pk = claim_to_aroot.get(file_pk)
            if not aroot_pk:
                no_match += 1
                continue

            account_id = pk_map.get(aroot_pk)
            if not account_id:
                no_acct += 1
                continue

            # Source 1: direct columns (most reliable summary)
            col_prin = parse_decimal(row.get("PRINBAL", ""))
            col_int = parse_decimal(row.get("INTBAL", ""))
            col_fee = parse_decimal(row.get("FEEBAL", ""))
            col_cost = parse_decimal(row.get("COSTBAL", ""))
            col_other = parse_decimal(row.get("OTHERBAL", ""))

            # Source 2: parsed BALANCES field (ID* codes for individual debtor)
            bals = parse_balances(row.get("BALANCES", ""))
            id_orig = bals.get("IDPPRJ_O", ZERO)
            id_prin = bals.get("IDPPRJ", ZERO) + bals.get("IDPPOJ", ZERO)
            id_int = bals.get("IDIPRJ", ZERO) + bals.get("IDIPOJ", ZERO)
            id_cost = bals.get("IDCPRJ", ZERO) + bals.get("IDCPOJ", ZERO)
            id_fees = bals.get("IDNPRJ", ZERO) + bals.get("IDNPOJ", ZERO)

            # Use column data if available, fall back to parsed BALANCES
            if col_prin or col_int or col_fee or col_cost:
                prin = col_prin
                interest = col_int
                fees = col_fee + col_other
                costs = col_cost
                orig = id_orig if id_orig else prin
            elif id_prin or id_int or id_cost or id_fees:
                prin = id_prin
                interest = id_int
                fees = id_fees
                costs = id_cost
                orig = id_orig if id_orig else prin
            else:
                no_bal += 1
                continue

            total = prin + interest + fees + costs

            if total == 0 and orig == 0:
                no_bal += 1
                continue

            updates.append((
                cents(orig) if orig else cents(prin),
                cents(prin),
                cents(interest),
                cents(fees + costs),
                cents(total),
                account_id,
            ))
            processed += 1

            if len(updates) >= BATCH:
                async with pool.acquire() as conn:
                    await conn.executemany("""
                        UPDATE accounts
                        SET original_principal=$1, current_principal=$2,
                            current_interest=$3, current_fees=$4, total_balance=$5
                        WHERE id=$6
                    """, updates)
                print(f"  Updated {processed:,} accounts...")
                updates = []

    if updates:
        async with pool.acquire() as conn:
            await conn.executemany("""
                UPDATE accounts
                SET original_principal=$1, current_principal=$2,
                    current_interest=$3, current_fees=$4, total_balance=$5
                WHERE id=$6
            """, updates)

    with_bal = await pool.fetchval(
        "SELECT count(*) FROM accounts WHERE tenant_id=$1 AND total_balance > 0", tid
    )
    total_bal = await pool.fetchval(
        "SELECT sum(total_balance) FROM accounts WHERE tenant_id=$1", tid
    )

    print(f"\nDone!")
    print(f"  Updated:          {processed:,}")
    print(f"  No claim match:   {no_match:,}")
    print(f"  No DCS account:   {no_acct:,}")
    print(f"  No balance data:  {no_bal:,}")
    print(f"  Other skips:      {skipped:,}")
    print(f"  Accounts with balance > 0: {with_bal:,}")
    print(f"  Total balance: ${(total_bal or 0)/100:,.2f}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
