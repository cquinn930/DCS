#!/usr/bin/env python3
"""Import _History.csv into DCS activity_entries table.

Standalone script that loads the pk_map from _migration_pk_map
and imports CollectMax history/notes data. Designed to handle
the large (7+ GB) _History.csv file efficiently.
"""

import asyncio
import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

DATA_DIR = Path(__file__).parent / "flg-data"
DB_URL = "postgresql://dcs:dcs@localhost:5432/dcs"
BATCH_SIZE = 500

CM_NULL_DATES = {
    "", "12/30/1899 12:00:00 AM", "12/31/1899 12:00:00 AM",
    "1/1/1900 12:00:00 AM", "01/01/1900 12:00:00 AM",
}


def parse_date(val: str):
    if not val or val.strip() in CM_NULL_DATES:
        return None
    val = val.strip()
    try:
        if "/" in val:
            return datetime.strptime(val, "%m/%d/%Y %I:%M:%S %p").replace(tzinfo=timezone.utc)
        elif "-" in val:
            return datetime.strptime(val[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        elif len(val) >= 14 and val[:8].isdigit():
            return datetime.strptime(val[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    return None


def clean(val, max_len=None):
    if val is None:
        return None
    val = val.strip()
    if not val:
        return None
    if max_len:
        val = val[:max_len]
    return val


async def main():
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=8)

    tid = await pool.fetchval("SELECT id FROM tenants WHERE slug='flg'")
    if not tid:
        print("FLG tenant not found")
        return

    # Check if already imported
    existing = await pool.fetchval(
        "SELECT count(*) FROM activity_entries WHERE tenant_id = $1", tid
    )
    if existing and existing > 1000:
        print(f"Already have {existing:,} activity_entries for FLG. Skipping import.")
        print("Delete them first if you want to re-import:")
        print(f"  DELETE FROM activity_entries WHERE tenant_id = '{tid}';")
        return

    # Test insert to verify schema compatibility
    print("Testing insert...")
    test_id = uuid.uuid4()
    # Grab a real account_id for the test
    test_acct = await pool.fetchval("SELECT id FROM accounts WHERE tenant_id = $1 LIMIT 1", tid)
    if not test_acct:
        print("  No accounts found — cannot test insert")
        return
    try:
        await pool.execute("""
            INSERT INTO activity_entries (id, tenant_id, account_id,
                activity_code_id, assigned_to_id,
                status, priority,
                scheduled_date, started_at, completed_at,
                notes, result, parent_entry_id)
            VALUES ($1,$2,$3,$4::uuid,$5::uuid,
                    $6::activitystatus,$7::activitypriority,
                    $8,$9,$10,$11,$12::jsonb,$13)
            ON CONFLICT (id) DO NOTHING
        """, test_id, tid, test_acct, None, None,
             "COMPLETED", "NORMAL",
             None, None, None,
             "test entry", '{"tag":"","type":""}', None)
        await pool.execute("DELETE FROM activity_entries WHERE id = $1", test_id)
        print("  Test insert OK")
    except Exception as e:
        print(f"  TEST INSERT FAILED: {e}")
        print("  Fix the error above before continuing.")
        return

    # Load PK mappings, but only keep ones that point to REAL accounts
    print("Loading PK mappings...")
    pk_map_raw = {}
    rows = await pool.fetch("SELECT cm_pk, dcs_id FROM _migration_pk_map")
    for r in rows:
        pk_map_raw[r["cm_pk"]] = r["dcs_id"]
    print(f"  {len(pk_map_raw):,} raw mappings loaded")

    # Load actual account IDs from DB
    print("Loading valid account IDs...")
    valid_accounts = set()
    acct_rows = await pool.fetch("SELECT id FROM accounts WHERE tenant_id = $1", tid)
    for r in acct_rows:
        valid_accounts.add(r["id"])
    print(f"  {len(valid_accounts):,} valid accounts")

    # Build claim→aroot lookup
    print("Building claim→aroot index from Claim.csv...")
    claim_to_aroot: dict[str, str] = {}
    claim_path = DATA_DIR / "Claim.csv"
    if claim_path.exists():
        with open(claim_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                cm_pk = (row.get("PKCLAIM") or "").strip()
                ar_pk = (row.get("PKAROOT") or "").strip()
                if cm_pk and ar_pk:
                    claim_to_aroot[cm_pk] = ar_pk
    print(f"  {len(claim_to_aroot):,} claims indexed")

    # Process _History.csv
    hist_path = DATA_DIR / "_History.csv"
    if not hist_path.exists():
        print(f"ERROR: {hist_path} not found")
        return

    print(f"Importing _History.csv...")
    processed = 0
    skipped = 0
    errored = 0
    batch: list[tuple] = []

    with open(hist_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            hi_pk = (row.get("PKHISTORY") or "").strip()
            if not hi_pk:
                skipped += 1
                continue

            note = row.get("NOTE", "")
            if not note or not note.strip():
                skipped += 1
                continue

            enter_time = parse_date(row.get("ENTERTIME", ""))
            effect_date = parse_date(row.get("EFFECTDATE", ""))
            user_pk = clean(row.get("PKUSERCODE", ""))
            user_id = pk_map_raw.get(user_pk) if user_pk else None
            tag = clean(row.get("TAG", ""), 50)
            hist_type = clean(row.get("TYPE", ""), 10)

            dcs_id = uuid.uuid4()

            # Find account from PKFILE — skip if we can't link it
            file_pk = clean(row.get("PKFILE", ""))
            account_id = None
            if file_pk:
                if file_pk in claim_to_aroot:
                    ar_pk = claim_to_aroot[file_pk]
                    account_id = pk_map_raw.get(ar_pk)
                else:
                    account_id = pk_map_raw.get(file_pk)

            # Only insert if the account actually exists in the DB
            if account_id is None or account_id not in valid_accounts:
                skipped += 1
                continue

            batch.append((
                dcs_id, tid, account_id, None,
                user_id, "COMPLETED", "NORMAL",
                effect_date, enter_time, enter_time,
                note.strip()[:10000],
                json.dumps({"tag": tag or "", "type": hist_type or ""}),
                None,
            ))
            processed += 1

            if len(batch) >= BATCH_SIZE:
                errored += await flush_batch(pool, batch)
                batch = []
                if processed % 100000 == 0:
                    print(f"  {processed:,} rows processed...")

    if batch:
        errored += await flush_batch(pool, batch)

    del claim_to_aroot

    print(f"\nDone!")
    print(f"  Imported:  {processed:,}")
    print(f"  Skipped:   {skipped:,}")
    print(f"  Errors:    {errored:,}")

    # Verify
    count = await pool.fetchval(
        "SELECT count(*) FROM activity_entries WHERE tenant_id = $1", tid
    )
    print(f"  Total activity_entries in DB: {count:,}")

    # Sample
    samples = await pool.fetch("""
        SELECT ae.notes, ae.scheduled_date, ae.result,
               a.account_reference
        FROM activity_entries ae
        LEFT JOIN accounts a ON a.id = ae.account_id
        WHERE ae.tenant_id = $1
        ORDER BY ae.scheduled_date DESC
        LIMIT 5
    """, tid)
    if samples:
        print("\nSample entries (most recent):")
        for s in samples:
            dt = s["scheduled_date"]
            ref = s["account_reference"] or "no-account"
            note = (s["notes"] or "")[:80]
            print(f"  [{ref}] {dt} — {note}")

    await pool.close()


_first_error_logged = False

async def flush_batch(pool, batch):
    """Insert a batch, falling back to row-by-row on errors."""
    global _first_error_logged
    errored = 0
    try:
        async with pool.acquire() as conn:
            await conn.executemany("""
                INSERT INTO activity_entries (id, tenant_id, account_id,
                    activity_code_id, assigned_to_id,
                    status, priority,
                    scheduled_date, started_at, completed_at,
                    notes, result, parent_entry_id)
                VALUES ($1,$2,$3,$4::uuid,$5::uuid,
                        $6::activitystatus,$7::activitypriority,
                        $8,$9,$10,$11,$12::jsonb,$13)
                ON CONFLICT (id) DO NOTHING
            """, batch)
    except Exception as e:
        if not _first_error_logged:
            print(f"\n  Batch insert failed: {e}")
            print(f"  Falling back to row-by-row for this batch...")
            _first_error_logged = True
        for row in batch:
            try:
                async with pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO activity_entries (id, tenant_id, account_id,
                            activity_code_id, assigned_to_id,
                            status, priority,
                            scheduled_date, started_at, completed_at,
                            notes, result, parent_entry_id)
                        VALUES ($1,$2,$3,$4::uuid,$5::uuid,
                                $6::activitystatus,$7::activitypriority,
                                $8,$9,$10,$11,$12::jsonb,$13)
                        ON CONFLICT (id) DO NOTHING
                    """, *row)
            except Exception as row_err:
                errored += 1
                if errored <= 3:
                    print(f"  Row error: {row_err}")
    return errored


if __name__ == "__main__":
    asyncio.run(main())
