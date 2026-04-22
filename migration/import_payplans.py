#!/usr/bin/env python3
"""Import PayPlan.csv into DCS payment_plans table.

Standalone script that loads the pk_map from _migration_pk_map
and imports CollectMax payment plan data. Uses the account's
original_principal for total_amount and cross-references the
payments table for actual payment counts.
"""

import asyncio
import csv
import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import asyncpg

DATA_DIR = Path(__file__).parent / "flg-data"
DB_URL = "postgresql://dcs:dcs@localhost:5432/dcs"
BATCH = 500

CM_NULL_DATES = {
    "", "12/30/1899 12:00:00 AM", "12/31/1899 12:00:00 AM",
    "1/1/1900 12:00:00 AM", "01/01/1900 12:00:00 AM",
}

FREQ_MAP = {
    "WK": "WEEKLY", "BW": "BIWEEKLY", "MO": "MONTHLY",
    "SM": "SEMI_MONTHLY", "QR": "QUARTERLY", "LS": "LUMP_SUM",
}


def parse_date(val: str):
    if not val or val.strip() in CM_NULL_DATES:
        return None
    val = val.strip()
    try:
        if "/" in val:
            return datetime.strptime(val, "%m/%d/%Y %I:%M:%S %p").replace(tzinfo=timezone.utc)
        elif len(val) >= 14 and val[:8].isdigit():
            return datetime.strptime(val[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    return None


def parse_amount(val: str) -> Decimal:
    if not val or not val.strip():
        return Decimal(0)
    try:
        return Decimal(val.strip().replace(",", "").replace("$", ""))
    except (InvalidOperation, ValueError):
        return Decimal(0)


async def main():
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=5)

    tid = await pool.fetchval("SELECT id FROM tenants WHERE slug='flg'")
    if not tid:
        print("FLG tenant not found")
        return

    print("Loading PK mappings...")
    rows = await pool.fetch("SELECT cm_pk, dcs_id FROM _migration_pk_map")
    pk_map = {r["cm_pk"]: r["dcs_id"] for r in rows}
    print(f"  {len(pk_map):,} mappings loaded")

    existing = await pool.fetchval(
        "SELECT count(*) FROM payment_plans WHERE tenant_id=$1", tid
    )
    print(f"  Existing payment plans for FLG: {existing}")

    # Pre-load account balances and dates for computing correct totals
    print("Loading account balances...")
    acct_rows = await pool.fetch(
        "SELECT id, original_principal, total_balance, date_placed FROM accounts WHERE tenant_id=$1", tid
    )
    acct_balances = {}
    for a in acct_rows:
        acct_balances[a["id"]] = {
            "orig": Decimal(str(a["original_principal"] or 0)) / 100,
            "bal": Decimal(str(a["total_balance"] or 0)) / 100,
            "date_placed": a["date_placed"],
        }
    print(f"  {len(acct_balances):,} accounts loaded")

    # Pre-load payment counts per account
    print("Loading payment counts...")
    pay_rows = await pool.fetch("""
        SELECT account_id, count(*) as cnt, coalesce(sum(amount), 0) as total_cents
        FROM payments WHERE tenant_id=$1 GROUP BY account_id
    """, tid)
    acct_payments = {}
    for p in pay_rows:
        acct_payments[p["account_id"]] = {
            "count": p["cnt"],
            "total_cents": p["total_cents"],
        }
    print(f"  {len(acct_payments):,} accounts with payments")

    csv_path = DATA_DIR / "PayPlan.csv"
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found")
        return

    print("Importing PayPlan.csv...")
    batch = []
    processed = 0
    skipped_no_account = 0
    skipped_dup = 0
    seen_pks = set()

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pp_pk = row.get("PKPAYPLAN", "").strip()
            if not pp_pk:
                skipped_dup += 1
                continue

            if pp_pk in seen_pks:
                skipped_dup += 1
                continue
            seen_pks.add(pp_pk)

            ar_pk = row.get("PKACCOUNT", "").strip() or row.get("PKAROOT", "").strip()
            account_id = pk_map.get(ar_pk) if ar_pk else None
            if not account_id:
                skipped_no_account += 1
                continue

            dcs_id = pk_map.get(pp_pk) or uuid.uuid4()
            pmt_amount = parse_amount(row.get("AMOUNT", "0"))
            begin_date = parse_date(row.get("BEGINING", ""))
            plan_date = parse_date(row.get("PLANDATE", ""))
            freq_raw = (row.get("FREQUENCY", "") or "MO").strip().upper()
            freq = FREQ_MAP.get(freq_raw, "MONTHLY")
            step_no = int(row.get("STEPNO", "1") or "1")

            # Use real account data for totals
            ab = acct_balances.get(account_id, {"orig": Decimal(0), "bal": Decimal(0)})

            acct_date_placed = ab.get("date_placed")
            start = begin_date or plan_date or acct_date_placed or datetime(2020, 1, 1, tzinfo=timezone.utc)
            total_amount = ab["orig"] if ab["orig"] > 0 else ab["bal"]
            if total_amount <= 0:
                total_amount = pmt_amount * 12

            total_payments = int(math.ceil(total_amount / pmt_amount)) if pmt_amount > 0 else 12

            ap = acct_payments.get(account_id, {"count": 0, "total_cents": 0})
            payments_made = ap["count"]
            amount_paid = Decimal(str(ap["total_cents"])) / 100
            balance_remaining = max(Decimal(0), total_amount - amount_paid)
            payments_remaining = max(0, total_payments - payments_made)

            batch.append((
                dcs_id, tid, account_id, None,
                "STANDARD", "ACTIVE",
                float(total_amount),
                float(pmt_amount),
                freq,
                total_payments,
                payments_made,
                payments_remaining,
                float(amount_paid),
                float(balance_remaining),
                start,  # start_date
                start,  # next_payment_date
                None,   # end_date
                False, None, None, float(total_amount),  # settlement fields + original_balance
                0.0, None, False, None,
                f"CollectMax PayPlan {pp_pk}, Step {step_no}",
                None, None, None, None,
                None, None,
            ))
            processed += 1

            if len(batch) >= BATCH:
                await _insert_batch(pool, batch)
                print(f"  Inserted {processed:,} plans...")
                batch = []

    if batch:
        await _insert_batch(pool, batch)

    final_count = await pool.fetchval(
        "SELECT count(*) FROM payment_plans WHERE tenant_id=$1", tid
    )

    print(f"\nDone!")
    print(f"  Imported:          {processed:,}")
    print(f"  Skipped (no acct): {skipped_no_account:,}")
    print(f"  Skipped (dup):     {skipped_dup:,}")
    print(f"  Total in DB now:   {final_count:,}")

    await pool.close()


async def _insert_batch(pool, batch):
    async with pool.acquire() as conn:
        try:
            await conn.executemany("""
                INSERT INTO payment_plans (
                    id, tenant_id, account_id, consumer_id,
                    plan_type, status,
                    total_amount, payment_amount, frequency,
                    total_payments, payments_made, payments_remaining,
                    amount_paid, balance_remaining,
                    start_date, next_payment_date, end_date,
                    is_settlement, settlement_amount, settlement_percentage,
                    original_balance,
                    pif_tolerance, max_months, auto_post, payment_method,
                    notes,
                    approved_by, approved_at, defaulted_at, default_reason,
                    amortization_schedule, projection_data
                ) VALUES (
                    $1,$2,$3,$4,
                    $5::plantype, $6::planstatus,
                    $7,$8,$9::paymentfrequency,
                    $10,$11,$12,$13,$14,
                    $15,$16,$17,
                    $18,$19,$20,$21,
                    $22,$23,$24,$25,
                    $26,
                    $27,$28,$29,$30,
                    $31,$32
                ) ON CONFLICT (id) DO NOTHING
            """, batch)
        except Exception as e:
            print(f"  [WARN] Batch error, inserting one by one: {e}")
            for row in batch:
                try:
                    await conn.execute("""
                        INSERT INTO payment_plans (
                            id, tenant_id, account_id, consumer_id,
                            plan_type, status,
                            total_amount, payment_amount, frequency,
                            total_payments, payments_made, payments_remaining,
                            amount_paid, balance_remaining,
                            start_date, next_payment_date, end_date,
                            is_settlement, settlement_amount, settlement_percentage,
                            original_balance,
                            pif_tolerance, max_months, auto_post, payment_method,
                            notes,
                            approved_by, approved_at, defaulted_at, default_reason,
                            amortization_schedule, projection_data
                        ) VALUES (
                            $1,$2,$3,$4,
                            $5::plantype, $6::planstatus,
                            $7,$8,$9::paymentfrequency,
                            $10,$11,$12,$13,$14,
                            $15,$16,$17,
                            $18,$19,$20,$21,
                            $22,$23,$24,$25,
                            $26,
                            $27,$28,$29,$30,
                            $31,$32
                        ) ON CONFLICT (id) DO NOTHING
                    """, *row)
                except Exception as e2:
                    print(f"    [SKIP] {e2}")
    batch.clear()


if __name__ == "__main__":
    asyncio.run(main())
