#!/usr/bin/env python3
"""
CollectMax → DCS Migration Script
==================================
Migrates FLG's CollectMax data (Advantage DB CSV exports) into the DCS
PostgreSQL database as a new tenant.

Usage:
    cd /opt/sites/DCS
    source services/api/venv/bin/activate
    python migration/migrate_collectmax.py [--phase N] [--dry-run] [--data-dir PATH]

Phases:
    0  Tenant & admin user creation
    1  Reference data (users, status codes, action codes, courts, bank accounts)
    2  Clients (build lookup from Client + Demog)
    3  Consumers (debtors from Demog)
    4  Accounts (ARoot + Claim + AComp linkage)
    5  Contact data (MultAddr, MultPh)
    6  Financial data (Journal → payments + trust transactions)
    7  Legal data (Filing, Judgment, BankGarn, WageGarn, Bankruptcy)
    8  History & notes (_History → activity_entries)
    9  Ancillary data (PayPlan, Settle, CredScore, Dispute, Employ, etc.)

The script is idempotent: re-running a phase will skip records whose
CollectMax PK already exists in the pk_map table.
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

import asyncpg

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_DATA_DIR = Path("/opt/sites/DCS/migration/flg-data")
BATCH_SIZE = 1000
HISTORY_BATCH_SIZE = 500  # smaller for the 7.6 GB table

CM_NULL_DATES = frozenset({
    "12/30/1899 12:00:00 AM",
    "12/30/1899",
    "",
})

TENANT_NAME = "Faloni Law Group"
TENANT_SLUG = "flg"
ADMIN_EMAIL = "admin@falonilaw.com"
ADMIN_PASSWORD_HASH = (
    "$2b$12$LJ3m4ys5qOzXHGf8V7YBzuJ6v5jH0X5dBvGKr3EaQJbKz8F5Lx0Oi"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("migrate")

# ---------------------------------------------------------------------------
# In-memory PK mapping: CollectMax 8-char PK → DCS UUID
# ---------------------------------------------------------------------------

pk_map: dict[str, uuid.UUID] = {}
pk_map_dirty: list[tuple[str, uuid.UUID]] = []  # pending DB flush


def map_pk(cm_pk: str) -> Optional[uuid.UUID]:
    """Return the DCS UUID for a CollectMax PK, creating one if needed."""
    if cm_pk is None:
        return None
    cm_pk = cm_pk.strip()
    if not cm_pk:
        return None
    if cm_pk in pk_map:
        return pk_map[cm_pk]
    new_id = uuid.uuid4()
    pk_map[cm_pk] = new_id
    pk_map_dirty.append((cm_pk, new_id))
    return new_id


def lookup_pk(cm_pk: str) -> Optional[uuid.UUID]:
    """Look up a DCS UUID without creating one."""
    if cm_pk is None:
        return None
    cm_pk = cm_pk.strip()
    return pk_map.get(cm_pk)


# ---------------------------------------------------------------------------
# Parsing helpers for CollectMax data formats
# ---------------------------------------------------------------------------

def parse_date(val: str) -> Optional[datetime]:
    """Parse a CollectMax date/datetime string, returning UTC-aware datetime."""
    if not val or val.strip() in CM_NULL_DATES:
        return None
    val = val.strip()
    try:
        if "/" in val:
            dt = datetime.strptime(val, "%m/%d/%Y %I:%M:%S %p")
        elif len(val) >= 14 and val[:8].isdigit():
            dt = datetime.strptime(val[:14], "%Y%m%d%H%M%S")
        elif len(val) == 8 and val.isdigit():
            dt = datetime.strptime(val, "%Y%m%d")
        else:
            return None
        if dt.year <= 1900:
            return None
        return dt.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError):
        return None


def parse_cents(val: str) -> int:
    """Parse a dollar string to cents (integer)."""
    if not val or not val.strip():
        return 0
    try:
        d = Decimal(val.strip())
        return int(d * 100)
    except (InvalidOperation, ValueError):
        return 0


def parse_decimal(val: str) -> Optional[Decimal]:
    if not val or not val.strip():
        return None
    try:
        return Decimal(val.strip())
    except (InvalidOperation, ValueError):
        return None


def parse_bool(val: str) -> bool:
    if not val:
        return False
    return val.strip().lower() == "true"


def clean(val: str, max_len: int = None) -> Optional[str]:
    """Strip whitespace; return None if empty. Optionally truncate."""
    if val is None:
        return None
    val = val.strip()
    if not val:
        return None
    if max_len:
        val = val[:max_len]
    return val


def safe_ssn_last4(ssn: str) -> Optional[str]:
    """Extract last 4 digits of SSN, masking the rest."""
    if not ssn:
        return None
    digits = "".join(c for c in ssn.strip() if c.isdigit())
    if len(digits) >= 4:
        return digits[-4:]
    return None


# ---------------------------------------------------------------------------
# CSV streaming
# ---------------------------------------------------------------------------

def stream_csv(data_dir: Path, filename: str):
    """Yield dicts from a CSV file, handling BOM and encoding issues."""
    path = data_dir / filename
    if not path.exists():
        log.warning("File not found, skipping: %s", path)
        return
    size_mb = path.stat().st_size / (1024 * 1024)
    log.info("Reading %s (%.1f MB)", filename, size_mb)
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def count_rows(data_dir: Path, filename: str) -> int:
    """Quick line count (minus header)."""
    path = data_dir / filename
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return sum(1 for _ in f) - 1


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def get_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=2, max_size=8)


async def flush_pk_map(pool: asyncpg.Pool):
    """Persist any dirty PK map entries to the migration tracking table."""
    global pk_map_dirty
    if not pk_map_dirty:
        return
    async with pool.acquire() as conn:
        await conn.executemany(
            """INSERT INTO _migration_pk_map (cm_pk, dcs_id)
               VALUES ($1, $2)
               ON CONFLICT (cm_pk) DO NOTHING""",
            pk_map_dirty,
        )
    log.info("Flushed %d PK mappings to _migration_pk_map", len(pk_map_dirty))
    pk_map_dirty = []


async def load_pk_map(pool: asyncpg.Pool):
    """Load previously persisted PK mappings into memory."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT cm_pk, dcs_id FROM _migration_pk_map")
    for row in rows:
        pk_map[row["cm_pk"]] = row["dcs_id"]
    log.info("Loaded %d existing PK mappings", len(rows))


async def ensure_migration_tables(pool: asyncpg.Pool):
    """Create migration-specific tracking tables if they don't exist."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migration_pk_map (
                cm_pk VARCHAR(20) PRIMARY KEY,
                dcs_id UUID NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migration_log (
                id SERIAL PRIMARY KEY,
                phase INT NOT NULL,
                table_name VARCHAR(100),
                rows_processed INT DEFAULT 0,
                rows_skipped INT DEFAULT 0,
                rows_errored INT DEFAULT 0,
                started_at TIMESTAMPTZ DEFAULT NOW(),
                finished_at TIMESTAMPTZ,
                status VARCHAR(20) DEFAULT 'running'
            )
        """)


async def log_phase_start(pool: asyncpg.Pool, phase: int, table: str) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO _migration_log (phase, table_name)
               VALUES ($1, $2) RETURNING id""",
            phase, table,
        )
    return row["id"]


async def log_phase_end(
    pool: asyncpg.Pool, log_id: int, processed: int, skipped: int, errored: int
):
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE _migration_log
               SET rows_processed=$2, rows_skipped=$3, rows_errored=$4,
                   finished_at=NOW(), status='done'
               WHERE id=$1""",
            log_id, processed, skipped, errored,
        )


async def batch_insert(pool: asyncpg.Pool, sql: str, batch: list[tuple]):
    """Execute a batch insert, falling back to row-by-row on constraint errors."""
    if not batch:
        return 0
    try:
        async with pool.acquire() as conn:
            await conn.executemany(sql, batch)
        return len(batch)
    except (asyncpg.exceptions.UniqueViolationError,
            asyncpg.exceptions.NotNullViolationError):
        inserted = 0
        async with pool.acquire() as conn:
            for row in batch:
                try:
                    await conn.execute(sql, *row)
                    inserted += 1
                except (asyncpg.exceptions.UniqueViolationError,
                        asyncpg.exceptions.NotNullViolationError):
                    pass
        return inserted


# ---------------------------------------------------------------------------
# Phase 0: Tenant & Admin
# ---------------------------------------------------------------------------

async def phase_0(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Create the FLG tenant and admin user."""
    log.info("=== PHASE 0: Tenant & Admin ===")

    tenant_id = map_pk("__TENANT_FLG__")

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM tenants WHERE slug = $1", TENANT_SLUG,
        )
        if existing:
            tenant_id = existing["id"]
            pk_map["__TENANT_FLG__"] = tenant_id
            log.info("Tenant '%s' already exists: %s", TENANT_SLUG, tenant_id)
        elif not dry_run:
            await conn.execute(
                """INSERT INTO tenants (id, name, slug, status, business_model,
                       default_jurisdiction, retention_years, settings)
                   VALUES ($1, $2, $3, 'ACTIVE'::tenantstatus, 'CONTINGENCY'::businessmodel, 'NY', 7, '{}')""",
                tenant_id, TENANT_NAME, TENANT_SLUG,
            )
            log.info("Created tenant '%s': %s", TENANT_NAME, tenant_id)

        admin_id = map_pk("__ADMIN_FLG__")
        existing_user = await conn.fetchrow(
            "SELECT id FROM users WHERE email = $1 AND tenant_id = $2",
            ADMIN_EMAIL, tenant_id,
        )
        if existing_user:
            pk_map["__ADMIN_FLG__"] = existing_user["id"]
            log.info("Admin user already exists")
        elif not dry_run:
            await conn.execute(
                """INSERT INTO users (id, tenant_id, email, password_hash,
                       first_name, last_name, is_active, is_owner, is_master, failed_login_attempts)
                   VALUES ($1, $2, $3, $4, 'Admin', 'FLG', true, true, false, 0)""",
                admin_id, tenant_id, ADMIN_EMAIL, ADMIN_PASSWORD_HASH,
            )
            log.info("Created admin user: %s", ADMIN_EMAIL)

    await flush_pk_map(pool)


# ---------------------------------------------------------------------------
# Phase 1: Reference / Lookup data
# ---------------------------------------------------------------------------

async def phase_1_users(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Migrate UserCode → users."""
    log.info("--- Phase 1a: UserCode → users ---")
    tenant_id = pk_map["__TENANT_FLG__"]
    lid = await log_phase_start(pool, 1, "UserCode")
    processed = skipped = errored = 0
    batch = []
    seen_emails: set[str] = set()

    for row in stream_csv(data_dir, "UserCode.csv"):
        cm_pk = row.get("PKUSERCODE", "").strip()
        if not cm_pk:
            skipped += 1
            continue
        if lookup_pk(cm_pk):
            skipped += 1
            continue
        utype = clean(row.get("TYPE", ""))
        if utype == "T":
            skipped += 1
            continue

        dcs_id = map_pk(cm_pk)
        code = clean(row.get("CODE", ""), 10) or "???"
        long_name = clean(row.get("LONGNAME", ""), 100) or code
        email_val = clean(row.get("EMAIL", ""), 255)
        if not email_val:
            email_val = f"{code.lower().replace(' ', '')}@falonilaw.com"

        email_key = email_val.lower()
        if email_key in seen_emails:
            email_val = f"{code.lower().replace(' ', '')}+{cm_pk}@falonilaw.com"
        seen_emails.add(email_val.lower())

        name_parts = long_name.split(None, 1)
        first_name = name_parts[0][:100] if name_parts else code
        last_name = name_parts[1][:100] if len(name_parts) > 1 else "User"

        batch.append((
            dcs_id, tenant_id, email_val, ADMIN_PASSWORD_HASH,
            first_name, last_name, not parse_bool(row.get("HIDDEN", "False")),
            False, False, 0,
        ))
        processed += 1

        if len(batch) >= BATCH_SIZE:
            if not dry_run:
                await batch_insert(pool, """
                    INSERT INTO users (id, tenant_id, email, password_hash,
                        first_name, last_name, is_active, is_owner, is_master, failed_login_attempts)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    ON CONFLICT DO NOTHING
                """, batch)
            batch = []
            await flush_pk_map(pool)

    if batch and not dry_run:
        await batch_insert(pool, """
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, is_active, is_owner, is_master, failed_login_attempts)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            ON CONFLICT DO NOTHING
        """, batch)
    await flush_pk_map(pool)
    await log_phase_end(pool, lid, processed, skipped, errored)
    log.info("Users: %d migrated, %d skipped", processed, skipped)


async def phase_1_activity_codes(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Migrate ActCode → activity_codes."""
    log.info("--- Phase 1b: ActCode → activity_codes ---")
    tenant_id = pk_map["__TENANT_FLG__"]
    lid = await log_phase_start(pool, 1, "ActCode")
    processed = skipped = errored = 0
    batch = []

    for row in stream_csv(data_dir, "ActCode.csv"):
        cm_pk = row.get("PKACTCODE", "").strip()
        if not cm_pk or lookup_pk(cm_pk):
            skipped += 1
            continue
        dcs_id = map_pk(cm_pk)
        code = clean(row.get("CODE", ""), 20) or cm_pk
        name = clean(row.get("DESCRIPT", ""), 200) or code
        hidden = parse_bool(row.get("HIDDEN", "False"))
        span = int(row.get("DELAY", "0") or 0)
        batch.append((
            dcs_id, tenant_id, code, name, name, "CUSTOM", "NORMAL", span,
            False, False, not hidden,
            json.dumps({"cm_pk": cm_pk}),
        ))
        processed += 1

        if len(batch) >= BATCH_SIZE:
            if not dry_run:
                await batch_insert(pool, """
                    INSERT INTO activity_codes (id, tenant_id, code, name,
                        description, category, priority, span_days,
                        auto_execute, is_system, is_active, config)
                    VALUES ($1,$2,$3,$4,$5,$6::activitycategory,$7::activitypriority,$8,$9,$10,$11,$12)
                    ON CONFLICT (id) DO NOTHING
                """, batch)
            batch = []
            await flush_pk_map(pool)

    if batch and not dry_run:
        await batch_insert(pool, """
            INSERT INTO activity_codes (id, tenant_id, code, name,
                description, category, priority, span_days,
                auto_execute, is_system, is_active, config)
            VALUES ($1,$2,$3,$4,$5,$6::activitycategory,$7::activitypriority,$8,$9,$10,$11,$12)
            ON CONFLICT (id) DO NOTHING
        """, batch)
    await flush_pk_map(pool)
    await log_phase_end(pool, lid, processed, skipped, errored)
    log.info("Activity codes: %d migrated, %d skipped", processed, skipped)


async def phase_1_courts(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Migrate CrtCode → courts."""
    log.info("--- Phase 1c: CrtCode → courts ---")
    tenant_id = pk_map["__TENANT_FLG__"]
    lid = await log_phase_start(pool, 1, "CrtCode")
    processed = skipped = errored = 0
    batch = []

    for row in stream_csv(data_dir, "CrtCode.csv"):
        cm_pk = row.get("PKCRTCODE", "").strip()
        if not cm_pk or lookup_pk(cm_pk):
            skipped += 1
            continue
        dcs_id = map_pk(cm_pk)
        code = clean(row.get("CODE", ""), 20) or cm_pk
        name = clean(row.get("DESIGATION", ""), 200) or code
        hidden = parse_bool(row.get("HIDDEN", "False"))
        county = clean(row.get("COUNTYCDS", ""), 100)
        website = clean(row.get("WEBURL", ""), 255)

        batch.append((
            dcs_id, tenant_id, code, name, "civil", "NY",
            None, None, None, None, county, None, None, None, website,
            Decimal("0"), Decimal("0"), not hidden, None,
            json.dumps({"cm_pk": cm_pk, "payee_type": clean(row.get("PAYEETYPE", ""))}),
        ))
        processed += 1

        if len(batch) >= BATCH_SIZE:
            if not dry_run:
                await batch_insert(pool, """
                    INSERT INTO courts (id, tenant_id, code, name,
                        court_type, jurisdiction,
                        address_line1, address_line2, city, state, zip_code,
                        county, phone, fax, website,
                        filing_fee_default, service_fee_default, is_active, notes, settings)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
                    ON CONFLICT (id) DO NOTHING
                """, batch)
            batch = []
            await flush_pk_map(pool)

    if batch and not dry_run:
        await batch_insert(pool, """
            INSERT INTO courts (id, tenant_id, code, name,
                court_type, jurisdiction,
                address_line1, address_line2, city, state, zip_code,
                county, phone, fax, website,
                filing_fee_default, service_fee_default, is_active, notes, settings)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
            ON CONFLICT (id) DO NOTHING
        """, batch)
    await flush_pk_map(pool)
    await log_phase_end(pool, lid, processed, skipped, errored)
    log.info("Courts: %d migrated, %d skipped", processed, skipped)


async def phase_1_trust_accounts(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Migrate BankAcct → trust_accounts."""
    log.info("--- Phase 1d: BankAcct → trust_accounts ---")
    tenant_id = pk_map["__TENANT_FLG__"]
    lid = await log_phase_start(pool, 1, "BankAcct")
    processed = skipped = errored = 0
    batch = []

    acct_type_map = {"F": "OPERATING", "T": "POOLED_TRUST", "C": "COLLECTIONS_ONLY"}

    for row in stream_csv(data_dir, "BankAcct.csv"):
        cm_pk = row.get("PKBANKACCT", "").strip()
        if not cm_pk or lookup_pk(cm_pk):
            skipped += 1
            continue
        dcs_id = map_pk(cm_pk)
        code = clean(row.get("CODE", ""), 20) or cm_pk
        acct_num = clean(row.get("ACCTNUM", ""), 25)
        acct_type_raw = clean(row.get("ACCTTYPE", ""), 1) or "T"
        acct_type = acct_type_map.get(acct_type_raw, "POOLED_TRUST")
        route_no = clean(row.get("ROUTENO", ""), 9)
        hidden = parse_bool(row.get("HIDDEN", "False"))

        batch.append((
            dcs_id, tenant_id, f"BankAcct {code}",
            acct_type, "ACTIVE" if not hidden else "FROZEN",
            "Unknown",
            acct_num[-4:] if acct_num and len(acct_num) >= 4 else "0000",
            route_no[-4:] if route_no and len(route_no) >= 4 else None,
            0, False,
            json.dumps({"cm_pk": cm_pk, "code": code, "full_acct": acct_num}),
        ))
        processed += 1

    if batch and not dry_run:
        await batch_insert(pool, """
            INSERT INTO trust_accounts (id, tenant_id, name,
                account_type, status, bank_name,
                account_number_last4, routing_number_last4,
                current_balance, allow_overdraft, config)
            VALUES ($1,$2,$3,$4::trustaccounttype,$5::trustaccountstatus,$6,$7,$8,$9,$10,$11)
            ON CONFLICT (id) DO NOTHING
        """, batch)
    await flush_pk_map(pool)
    await log_phase_end(pool, lid, processed, skipped, errored)
    log.info("Trust accounts: %d migrated, %d skipped", processed, skipped)


async def phase_1(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Phase 1: All reference/lookup data."""
    log.info("=== PHASE 1: Reference Data ===")
    await phase_1_users(pool, data_dir, dry_run)
    await phase_1_activity_codes(pool, data_dir, dry_run)
    await phase_1_courts(pool, data_dir, dry_run)
    await phase_1_trust_accounts(pool, data_dir, dry_run)


# ---------------------------------------------------------------------------
# Phase 2: Client lookup (in-memory only — no Client table in DCS)
# ---------------------------------------------------------------------------

client_demog_map: dict[str, str] = {}  # PKCLIENT → Demog PK
client_name_map: dict[str, str] = {}   # PKCLIENT → client name string


async def phase_2(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Build client lookup: PKCLIENT → client name (from Client→Demog)."""
    log.info("=== PHASE 2: Client Lookup ===")

    # First read Client.csv to get PKCLIENT → PKDEMOG mapping
    for row in stream_csv(data_dir, "Client.csv"):
        cm_pk = row.get("PKCLIENT", "").strip()
        demog_pk = row.get("PKDEMOG", "").strip()
        cl_id = clean(row.get("ID", ""), 100)
        if cm_pk and demog_pk:
            client_demog_map[cm_pk] = demog_pk
            if cl_id:
                client_name_map[cm_pk] = cl_id

    log.info("Client→Demog mappings: %d", len(client_demog_map))

    # Only load Demog records that belong to clients (not all 209MB)
    needed_demog_pks = set(client_demog_map.values())
    log.info("Need to resolve %d Demog PKs for clients", len(needed_demog_pks))

    for row in stream_csv(data_dir, "Demog.csv"):
        dm_pk = row.get("PKDEMOG", "").strip()
        if not dm_pk or dm_pk not in needed_demog_pks:
            continue
        biz = parse_bool(row.get("BUSINESS", "False"))
        if biz:
            name = clean(row.get("LASTNAME", ""), 200)
        else:
            first = clean(row.get("FIRSTNAME", ""), 100) or ""
            last = clean(row.get("LASTNAME", ""), 100) or ""
            name = f"{first} {last}".strip()
        if name:
            for cl_pk, cl_dm_pk in client_demog_map.items():
                if cl_dm_pk == dm_pk:
                    client_name_map[cl_pk] = name
        needed_demog_pks.discard(dm_pk)
        if not needed_demog_pks:
            break  # found all clients, stop reading

    # Fill in any unresolved clients
    for cl_pk in client_demog_map:
        if cl_pk not in client_name_map:
            client_name_map[cl_pk] = cl_pk

    log.info("Client names resolved: %d", len(client_name_map))


# ---------------------------------------------------------------------------
# Phase 3: Consumers (Debtors)
# ---------------------------------------------------------------------------

# Track which Demog PKs are debtors vs clients
debtor_demog_pks: set[str] = set()


async def phase_3(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Migrate debtor Demog entries → consumers + inline contact_methods."""
    log.info("=== PHASE 3: Consumers ===")
    tenant_id = pk_map["__TENANT_FLG__"]

    # First pass: identify debtor demog PKs from AComp
    log.info("Scanning AComp for debtor Demog PKs...")
    for row in stream_csv(data_dir, "AComp.csv"):
        etype = clean(row.get("ENTRYTYPE", ""))
        if etype == "DEB":
            entity = row.get("PKENTITY", "").strip()
            if entity:
                debtor_demog_pks.add(entity)
    log.info("Found %d unique debtor Demog PKs", len(debtor_demog_pks))

    # Second pass: create consumers from Demog for debtor entries
    lid = await log_phase_start(pool, 3, "Demog→consumers")
    processed = skipped = errored = 0
    consumer_batch = []
    contact_batch = []

    for row in stream_csv(data_dir, "Demog.csv"):
        dm_pk = row.get("PKDEMOG", "").strip()
        if not dm_pk or dm_pk not in debtor_demog_pks:
            skipped += 1
            continue
        if lookup_pk(dm_pk):
            skipped += 1
            continue

        dcs_id = map_pk(dm_pk)
        first = clean(row.get("FIRSTNAME", ""), 100) or "Unknown"
        last = clean(row.get("LASTNAME", ""), 100) or "Unknown"
        middle = clean(row.get("MIDDLENAME", ""), 100)
        suffix = clean(row.get("SUFFIX", ""), 20)
        ssn = safe_ssn_last4(row.get("SSN", ""))
        dob = parse_date(row.get("DOB", ""))
        dod = parse_date(row.get("DOD", ""))
        is_biz = parse_bool(row.get("BUSINESS", "False"))

        lang_pk = clean(row.get("PKLANGCODE", ""))
        lang = "en"
        if lang_pk and lang_pk != "   ":
            lang = "es" if "span" in (clean(row.get("LANGUAGE", "")) or "").lower() else "en"

        extra = {"cm_pk": dm_pk, "is_business": is_biz}
        driver_lic = clean(row.get("DRIVERLIC", ""))
        if driver_lic:
            extra["drivers_license"] = driver_lic
        member_id = clean(row.get("MEMBERID", ""))
        if member_id:
            extra["member_id"] = member_id

        consumer_batch.append((
            dcs_id, tenant_id,
            first if not is_biz else "Business",
            last,
            middle, suffix, ssn, dob,
            lang, "America/New_York",
            dod is not None,  # is_deceased
            False, None, None,
            False, None, None,
            dm_pk,  # external_id
            json.dumps(extra),
        ))

        # Inline address from Demog
        addr1 = clean(row.get("ADDRESS1", ""), 255)
        city = clean(row.get("CITY", ""), 100)
        state = clean(row.get("STATE", ""), 2)
        zip_code = clean(row.get("ZIP", ""), 20)
        if addr1 and city:
            addr2 = clean(row.get("ADDRESS2", ""), 255)
            contact_id = uuid.uuid4()
            full_addr = ", ".join(filter(None, [addr1, addr2, city, state, zip_code]))
            addr_ok = parse_bool(row.get("ADDRESSOK", "True"))
            contact_batch.append((
                contact_id, tenant_id, dcs_id,
                "ADDRESS_HOME", full_addr, True, addr_ok, False,
                addr1, addr2, city, state, zip_code, "US", None, None,
            ))

        # Inline phones
        for ph_field, ph_type in [("PHONE1", "PHONE_HOME"), ("PHONE2", "PHONE_WORK"), ("PHONE3", "PHONE_MOBILE")]:
            phone = clean(row.get(ph_field, ""), 20)
            if phone and phone.replace("-", "").replace("(", "").replace(")", "").replace(" ", "").isdigit():
                c_id = uuid.uuid4()
                contact_batch.append((
                    c_id, tenant_id, dcs_id,
                    ph_type, phone, ph_field == "PHONE1", True, False,
                    None, None, None, None, None, "US", None, None,
                ))

        # Email
        email = clean(row.get("EMAIL", ""), 255)
        if email and "@" in email:
            c_id = uuid.uuid4()
            contact_batch.append((
                c_id, tenant_id, dcs_id,
                "EMAIL", email, False, True, False,
                None, None, None, None, None, "US", None, None,
            ))

        processed += 1

        if len(consumer_batch) >= BATCH_SIZE:
            if not dry_run:
                await batch_insert(pool, """
                    INSERT INTO consumers (id, tenant_id,
                        first_name, last_name, middle_name, suffix,
                        ssn_last_four, date_of_birth,
                        language_preference, timezone,
                        is_deceased, is_represented, attorney_name, attorney_contact,
                        legal_hold, legal_hold_reason, legal_hold_date,
                        external_id, extra_data)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
                    ON CONFLICT (id) DO NOTHING
                """, consumer_batch)
                if contact_batch:
                    await batch_insert(pool, """
                        INSERT INTO contact_methods (id, tenant_id, consumer_id,
                            contact_type, value, is_primary, is_valid, is_suppressed,
                            address_line_1, address_line_2, city, state, postal_code,
                            country, last_validated, validation_source)
                    VALUES ($1,$2,$3,$4::contacttype,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                    ON CONFLICT (id) DO NOTHING
                """, contact_batch)
            consumer_batch = []
            contact_batch = []
            await flush_pk_map(pool)

    if consumer_batch and not dry_run:
        await batch_insert(pool, """
            INSERT INTO consumers (id, tenant_id,
                first_name, last_name, middle_name, suffix,
                ssn_last_four, date_of_birth,
                language_preference, timezone,
                is_deceased, is_represented, attorney_name, attorney_contact,
                legal_hold, legal_hold_reason, legal_hold_date,
                external_id, extra_data)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
            ON CONFLICT (id) DO NOTHING
        """, consumer_batch)
        if contact_batch:
            await batch_insert(pool, """
                INSERT INTO contact_methods (id, tenant_id, consumer_id,
                    contact_type, value, is_primary, is_valid, is_suppressed,
                    address_line_1, address_line_2, city, state, postal_code,
                    country, last_validated, validation_source)
                    VALUES ($1,$2,$3,$4::contacttype,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                    ON CONFLICT (id) DO NOTHING
                """, contact_batch)
    await flush_pk_map(pool)
    await log_phase_end(pool, lid, processed, skipped, errored)
    log.info("Consumers: %d migrated, %d skipped", processed, skipped)


# ---------------------------------------------------------------------------
# Phase 4: Accounts
# ---------------------------------------------------------------------------

# AComp linkage: PKAROOT → {debtors: [PKDEMOG], client: PKCLIENT, claims: [PKCLAIM]}
acomp_map: dict[str, dict] = {}


async def phase_4(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Migrate ARoot + AComp + Claim → accounts."""
    log.info("=== PHASE 4: Accounts ===")
    tenant_id = pk_map["__TENANT_FLG__"]

    # Build AComp relationship map
    log.info("Building AComp linkage map...")
    for row in stream_csv(data_dir, "AComp.csv"):
        ar_pk = row.get("PKAROOT", "").strip()
        entity = row.get("PKENTITY", "").strip()
        etype = clean(row.get("ENTRYTYPE", ""))
        if not ar_pk or not entity:
            continue
        if ar_pk not in acomp_map:
            acomp_map[ar_pk] = {"debtors": [], "client": None, "claims": []}
        if etype == "DEB":
            acomp_map[ar_pk]["debtors"].append(entity)
        elif etype == "CLI":
            acomp_map[ar_pk]["client"] = entity
        elif etype in ("CLA", "PLA"):
            acomp_map[ar_pk]["claims"].append(entity)
    log.info("AComp map built: %d accounts", len(acomp_map))

    # Build lightweight Claim index: only store essential fields per claim
    # (ref_num, client_pk, open_date_str, close_date_str, purchase_dt_str)
    log.info("Loading Claim index (lightweight)...")
    claim_data: dict[str, tuple] = {}
    for row in stream_csv(data_dir, "Claim.csv"):
        cm_pk = row.get("PKCLAIM", "").strip()
        if not cm_pk:
            continue
        claim_data[cm_pk] = (
            clean(row.get("REFNUM", ""), 100),         # 0: ref_num
            clean(row.get("PKCLIENT", "")),             # 1: client_pk
            row.get("OPENDATE", "").strip(),             # 2: open_date (raw str)
            row.get("CLOSEDATE", "").strip(),            # 3: close_date (raw str)
            row.get("PURCHASEDT", "").strip(),           # 4: purchase_dt (raw str)
        )
    log.info("Claim index loaded: %d claims", len(claim_data))

    # Build status code lookup
    stat_code_map: dict[str, str] = {}
    for row in stream_csv(data_dir, "StatCode.csv"):
        sc_pk = row.get("PKSTATCODE", "").strip()
        code = clean(row.get("CODE", ""), 10)
        desc = clean(row.get("DESCRIPT", ""), 200)
        if sc_pk and code:
            stat_code_map[sc_pk] = f"{code}: {desc}" if desc else code
    log.info("Status codes loaded: %d", len(stat_code_map))

    # Now migrate ARoot → accounts
    lid = await log_phase_start(pool, 4, "ARoot→accounts")
    processed = skipped = errored = 0
    batch = []

    for row in stream_csv(data_dir, "ARoot.csv"):
        ar_pk = row.get("PKAROOT", "").strip()
        if not ar_pk:
            skipped += 1
            continue
        if lookup_pk(ar_pk):
            skipped += 1
            continue

        links = acomp_map.get(ar_pk, {})
        debtor_pks = links.get("debtors", [])
        client_entity_pk = links.get("client")
        claim_pks = links.get("claims", [])

        # Find consumer
        consumer_id = None
        for dpk in debtor_pks:
            consumer_id = lookup_pk(dpk)
            if consumer_id:
                break
        if not consumer_id:
            skipped += 1
            continue

        # Get client name
        client_pk = None
        if client_entity_pk:
            # client_entity_pk is a Demog PK; find which Client it belongs to
            for cl_pk, dm_pk in client_demog_map.items():
                if dm_pk == client_entity_pk:
                    client_pk = cl_pk
                    break
        # Also check from Claim
        for cpk in claim_pks:
            if cpk in claim_data and claim_data[cpk][1]:
                client_pk = claim_data[cpk][1]
                break
        client_name = client_name_map.get(client_pk, "Unknown Client") if client_pk else "Unknown Client"

        acct_num = clean(row.get("ACCTNUM", ""), 100) or ar_pk
        dcs_id = map_pk(ar_pk)
        create_time = parse_date(row.get("CREATETIME", ""))
        hold = parse_bool(row.get("HOLD", "False"))
        temp_hold = parse_bool(row.get("TEMPHOLD", "False"))
        invalid = parse_bool(row.get("INVALID", "False"))
        dncall = parse_bool(row.get("DNCALL", "False"))
        dncease = parse_bool(row.get("DNCEASE", "False"))

        # Determine status from claim
        status = "ACTIVE"
        claim_tuple = None
        for cpk in claim_pks:
            if cpk in claim_data:
                claim_tuple = claim_data[cpk]
                break
        if invalid:
            status = "CLOSED"
        elif hold or temp_hold:
            status = "HOLD"
        elif claim_tuple and claim_tuple[3] and claim_tuple[3] not in CM_NULL_DATES:
            status = "CLOSED"

        # Balances from AcctBals.ACCTTBAL on ARoot
        total_bal_str = row.get("ACCTTBAL", "0")
        total_bal_cents = parse_cents(total_bal_str)

        # Jurisdiction from court or default
        jurisdiction = "NY"

        extra = {
            "cm_pk": ar_pk,
            "acctnum": acct_num,
            "flash_msg": clean(row.get("FLASHMSG", "")),
            "remarks": clean(row.get("REMARKS", "")),
            "source": clean(row.get("SOURCE", "")),
            "aux_num": clean(row.get("AUXNUM", "")),
            "dncall": dncall,
            "dncease": dncease,
        }

        ref_num = None
        open_date = create_time
        if claim_tuple:
            ref_num = claim_tuple[0]
            open_date = parse_date(claim_tuple[2]) or create_time

        batch.append((
            dcs_id, tenant_id, consumer_id,
            acct_num,
            client_name,  # original_creditor
            client_name,  # current_creditor
            ref_num,      # client_account_number
            status,
            "CONSUMER",   # debt_type
            jurisdiction,
            total_bal_cents,  # original_principal
            total_bal_cents,  # current_principal
            0,  # current_interest
            0,  # current_fees
            total_bal_cents,  # total_balance
            parse_date(claim_tuple[4]) if claim_tuple else None,
            None,  # date_of_first_delinquency
            open_date or datetime.now(timezone.utc),
            None,  # statute_expiry_date
            hold or temp_hold,  # legal_hold
            "CollectMax hold" if hold else None,
            None,
            False, None,
            json.dumps(extra),
        ))
        processed += 1

        if len(batch) >= BATCH_SIZE:
            if not dry_run:
                await batch_insert(pool, """
                    INSERT INTO accounts (id, tenant_id, consumer_id,
                        account_reference, original_creditor, current_creditor,
                        client_account_number,
                        status, debt_type, jurisdiction,
                        original_principal, current_principal,
                        current_interest, current_fees, total_balance,
                        date_of_service, date_of_first_delinquency, date_placed,
                        statute_expiry_date,
                        legal_hold, legal_hold_reason, legal_hold_date,
                        validation_notice_sent, validation_notice_date,
                        extra_data)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8::accountstatus,$9::debttype,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25)
                    ON CONFLICT (id) DO NOTHING
                """, batch)
            batch = []
            await flush_pk_map(pool)

    if batch and not dry_run:
        await batch_insert(pool, """
            INSERT INTO accounts (id, tenant_id, consumer_id,
                account_reference, original_creditor, current_creditor,
                client_account_number,
                status, debt_type, jurisdiction,
                original_principal, current_principal,
                current_interest, current_fees, total_balance,
                date_of_service, date_of_first_delinquency, date_placed,
                statute_expiry_date,
                legal_hold, legal_hold_reason, legal_hold_date,
                validation_notice_sent, validation_notice_date,
                extra_data)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8::accountstatus,$9::debttype,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25)
            ON CONFLICT (id) DO NOTHING
        """, batch)
    await flush_pk_map(pool)
    await log_phase_end(pool, lid, processed, skipped, errored)
    log.info("Accounts: %d migrated, %d skipped", processed, skipped)

    # Free large data structures no longer needed
    claim_data.clear()
    debtor_demog_pks.clear()
    log.info("Freed claim_data and debtor_demog_pks from memory")


# ---------------------------------------------------------------------------
# Phase 5: Additional contact data (MultAddr, MultPh)
# ---------------------------------------------------------------------------

async def phase_5(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Migrate MultAddr and MultPh → contact_methods."""
    log.info("=== PHASE 5: Contact Data ===")
    tenant_id = pk_map["__TENANT_FLG__"]

    # MultAddr
    lid = await log_phase_start(pool, 5, "MultAddr")
    processed = skipped = errored = 0
    batch = []

    for row in stream_csv(data_dir, "MultAddr.csv"):
        ma_pk = row.get("PKMULTADDR", "").strip()
        if not ma_pk:
            skipped += 1
            continue

        # Find consumer via AComp debtor link
        acomp_pk = row.get("PKACOMP", "").strip()
        demog_pk = row.get("PKDEMOG", "").strip()
        ar_pk = row.get("PKAROOT", "").strip()

        consumer_id = None
        if demog_pk:
            consumer_id = lookup_pk(demog_pk)
        if not consumer_id and ar_pk:
            links = acomp_map.get(ar_pk, {})
            for dpk in links.get("debtors", []):
                consumer_id = lookup_pk(dpk)
                if consumer_id:
                    break
        if not consumer_id:
            skipped += 1
            continue

        dcs_id = uuid.uuid4()  # don't bloat pk_map for high-volume tables
        addr1 = clean(row.get("ADDRESS1", ""), 255)
        addr2 = clean(row.get("ADDRESS2", ""), 255)
        city = clean(row.get("CITY", ""), 100)
        state = clean(row.get("STATE", ""), 2)
        zip_code = clean(row.get("ZIP", ""), 20)
        addr_ok = parse_bool(row.get("ADDRESSOK", "True"))

        if not addr1:
            skipped += 1
            continue

        full_addr = ", ".join(filter(None, [addr1, addr2, city, state, zip_code]))

        batch.append((
            dcs_id, tenant_id, consumer_id,
            "ADDRESS_HOME", full_addr, False, addr_ok, False,
            addr1, addr2, city, state, zip_code, "US", None, None,
        ))
        processed += 1

        if len(batch) >= BATCH_SIZE:
            if not dry_run:
                await batch_insert(pool, """
                    INSERT INTO contact_methods (id, tenant_id, consumer_id,
                        contact_type, value, is_primary, is_valid, is_suppressed,
                        address_line_1, address_line_2, city, state, postal_code,
                        country, last_validated, validation_source)
                    VALUES ($1,$2,$3,$4::contacttype,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                    ON CONFLICT (id) DO NOTHING
                """, batch)
            batch = []
            await flush_pk_map(pool)

    if batch and not dry_run:
        await batch_insert(pool, """
            INSERT INTO contact_methods (id, tenant_id, consumer_id,
                contact_type, value, is_primary, is_valid, is_suppressed,
                address_line_1, address_line_2, city, state, postal_code,
                country, last_validated, validation_source)
            VALUES ($1,$2,$3,$4::contacttype,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
            ON CONFLICT (id) DO NOTHING
        """, batch)
    await flush_pk_map(pool)
    await log_phase_end(pool, lid, processed, skipped, errored)
    log.info("MultAddr: %d migrated, %d skipped", processed, skipped)

    # MultPh
    lid = await log_phase_start(pool, 5, "MultPh")
    processed = skipped = errored = 0
    batch = []

    for row in stream_csv(data_dir, "MultPh.csv"):
        mp_pk = row.get("PKMULTPH", "").strip()
        if not mp_pk:
            skipped += 1
            continue

        ar_pk = row.get("PKAROOT", "").strip()
        demog_pk = row.get("PKDEMOG", "").strip()

        consumer_id = None
        if demog_pk:
            consumer_id = lookup_pk(demog_pk)
        if not consumer_id and ar_pk:
            links = acomp_map.get(ar_pk, {})
            for dpk in links.get("debtors", []):
                consumer_id = lookup_pk(dpk)
                if consumer_id:
                    break
        if not consumer_id:
            skipped += 1
            continue

        dcs_id = uuid.uuid4()  # don't bloat pk_map for high-volume tables
        phone = clean(row.get("PHONE", ""), 20)
        if not phone:
            skipped += 1
            continue

        ph_type_raw = clean(row.get("PHTYPE", ""), 5) or "P"
        is_cell = parse_bool(row.get("ISCELL", "False"))
        ph_type = "PHONE_MOBILE" if is_cell else (
            "PHONE_WORK" if ph_type_raw == "W" else "PHONE_HOME"
        )
        phone_ok = parse_bool(row.get("PHONEOK", "True"))
        dnc = parse_bool(row.get("DONOTCALL", "False"))

        batch.append((
            dcs_id, tenant_id, consumer_id,
            ph_type, phone, False, phone_ok, dnc,
            None, None, None, None, None, "US", None, None,
        ))
        processed += 1

        if len(batch) >= BATCH_SIZE:
            if not dry_run:
                await batch_insert(pool, """
                    INSERT INTO contact_methods (id, tenant_id, consumer_id,
                        contact_type, value, is_primary, is_valid, is_suppressed,
                        address_line_1, address_line_2, city, state, postal_code,
                        country, last_validated, validation_source)
                    VALUES ($1,$2,$3,$4::contacttype,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                    ON CONFLICT (id) DO NOTHING
                """, batch)
            batch = []
            await flush_pk_map(pool)

    if batch and not dry_run:
        await batch_insert(pool, """
            INSERT INTO contact_methods (id, tenant_id, consumer_id,
                contact_type, value, is_primary, is_valid, is_suppressed,
                address_line_1, address_line_2, city, state, postal_code,
                country, last_validated, validation_source)
            VALUES ($1,$2,$3,$4::contacttype,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
            ON CONFLICT (id) DO NOTHING
        """, batch)
    await flush_pk_map(pool)
    await log_phase_end(pool, lid, processed, skipped, errored)
    log.info("MultPh: %d migrated, %d skipped", processed, skipped)


# ---------------------------------------------------------------------------
# Phase 6: Financial (Journal → payments + trust_transactions)
# ---------------------------------------------------------------------------

async def phase_6(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Migrate Journal → payments and trust_transactions."""
    log.info("=== PHASE 6: Financial Data ===")
    tenant_id = pk_map["__TENANT_FLG__"]
    lid = await log_phase_start(pool, 6, "Journal")
    processed = skipped = errored = 0
    pay_batch = []
    trx_batch = []

    PAYMENT_TYPES = {"PAY", "PPAY", "DPAY", "CPAY", "RPAY", "CASH", "ECHECK", "CC"}

    for row in stream_csv(data_dir, "Journal.csv"):
        jn_pk = row.get("PKJOURNAL", "").strip()
        if not jn_pk or lookup_pk(jn_pk):
            skipped += 1
            continue

        trans_type = clean(row.get("TRANSTYPE", ""), 10) or ""
        trans_class = clean(row.get("TRANSCLASS", ""), 5) or ""
        ar_pk = clean(row.get("PKAROOT", ""))
        account_id = lookup_pk(ar_pk) if ar_pk else None
        trans_date = parse_date(row.get("TRANSDATE", ""))
        dcs_id = uuid.uuid4()  # don't bloat pk_map for high-volume tables

        # Financial transactions → trust_transactions
        bank_type = clean(row.get("BANKTYPE", ""), 1)
        entity_pk = clean(row.get("PKENTITY", ""))
        reverse = parse_bool(row.get("REVERSE", "False"))
        r_bal_fwd = parse_cents(row.get("RBALFWD", "0"))

        if trans_type.strip().upper() in PAYMENT_TYPES and account_id:
            # This is a payment
            # Parse temp view for amount
            temp_view = row.get("JNTEMPVIEW", "")
            amount = 0
            if "$" in temp_view:
                try:
                    amt_str = temp_view.split("$")[1].split()[0].replace(",", "")
                    amount = parse_cents(amt_str)
                except (IndexError, ValueError):
                    pass

            method = "CHECK"
            if "CC" in trans_type.upper():
                method = "CARD"
            elif "ECHECK" in trans_type.upper() or "ACH" in trans_type.upper():
                method = "ACH"
            elif "CASH" in trans_type.upper():
                method = "CASH"

            pay_batch.append((
                dcs_id, tenant_id, account_id,
                abs(amount), method, "COMPLETED",
                None, json.dumps({"cm_type": trans_type}),
                trans_date or datetime.now(timezone.utc),
                trans_date,
                "collectmax_migration", None,
            ))
        else:
            # Trust transaction
            trust_acct_pk = clean(row.get("TRXBAPK", ""))
            trust_id = lookup_pk(trust_acct_pk) if trust_acct_pk else None
            if not trust_id:
                skipped += 1
                continue

            trx_type = "DISBURSEMENT" if trans_class in ("D", "X") else "DEPOSIT"
            trx_num = clean(row.get("TRXNUM", ""), 20)

            trx_batch.append((
                dcs_id, tenant_id, trust_id,
                trx_type, abs(r_bal_fwd), r_bal_fwd,
                trx_num, None, None,
                clean(row.get("JNTEMPVIEW", ""), 500),
                account_id, None, None,
                trans_date or datetime.now(timezone.utc),
                None, False,
            ))

        processed += 1

        if len(pay_batch) >= BATCH_SIZE:
            if not dry_run:
                await batch_insert(pool, """
                    INSERT INTO payments (id, tenant_id, account_id,
                        amount, method, status,
                        processor_reference, processor_response,
                        received_at, processed_at,
                        source, source_ip)
                    VALUES ($1,$2,$3,$4,$5::paymentmethod,$6::paymentstatus,$7,$8,$9,$10,$11,$12)
                    ON CONFLICT (id) DO NOTHING
                """, pay_batch)
            pay_batch = []
            await flush_pk_map(pool)

        if len(trx_batch) >= BATCH_SIZE:
            if not dry_run:
                await batch_insert(pool, """
                    INSERT INTO trust_transactions (id, tenant_id, trust_account_id,
                        transaction_type, amount, running_balance,
                        reference_number, check_number, payee,
                        memo, account_id, payment_id, linked_transaction_id,
                        transaction_date, posted_by_id, is_reconciled)
                    VALUES ($1,$2,$3,$4::trusttransactiontype,$5,$6,$7,$8,$9,$10,$11::uuid,$12::uuid,$13::uuid,$14,$15::uuid,$16)
                    ON CONFLICT (id) DO NOTHING
                """, trx_batch)
            trx_batch = []

    # Flush remaining
    if pay_batch and not dry_run:
        await batch_insert(pool, """
            INSERT INTO payments (id, tenant_id, account_id,
                amount, method, status,
                processor_reference, processor_response,
                received_at, processed_at,
                source, source_ip)
            VALUES ($1,$2,$3,$4,$5::paymentmethod,$6::paymentstatus,$7,$8,$9,$10,$11,$12)
            ON CONFLICT (id) DO NOTHING
        """, pay_batch)
    if trx_batch and not dry_run:
        await batch_insert(pool, """
            INSERT INTO trust_transactions (id, tenant_id, trust_account_id,
                transaction_type, amount, running_balance,
                reference_number, check_number, payee,
                memo, account_id, payment_id, linked_transaction_id,
                transaction_date, posted_by_id, is_reconciled)
            VALUES ($1,$2,$3,$4::trusttransactiontype,$5,$6,$7,$8,$9,$10,$11::uuid,$12::uuid,$13::uuid,$14,$15::uuid,$16)
            ON CONFLICT (id) DO NOTHING
        """, trx_batch)
    await flush_pk_map(pool)
    await log_phase_end(pool, lid, processed, skipped, errored)
    log.info("Financial: %d migrated, %d skipped", processed, skipped)


# ---------------------------------------------------------------------------
# Phase 7: Legal data
# ---------------------------------------------------------------------------

async def phase_7(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Migrate Filing → litigation_cases, Judgment → judgments."""
    log.info("=== PHASE 7: Legal Data ===")
    tenant_id = pk_map["__TENANT_FLG__"]

    # Filing → litigation_cases
    lid = await log_phase_start(pool, 7, "Filing")
    processed = skipped = errored = 0
    batch = []

    for row in stream_csv(data_dir, "Filing.csv"):
        ff_pk = row.get("PKFILING", "").strip()
        if not ff_pk or lookup_pk(ff_pk):
            skipped += 1
            continue

        ar_pk = clean(row.get("PKAROOT", ""))
        account_id = lookup_pk(ar_pk) if ar_pk else None
        if not account_id:
            skipped += 1
            continue

        dcs_id = map_pk(ff_pk)
        court_pk = clean(row.get("PKCRTCODE", ""))
        court_id = lookup_pk(court_pk) if court_pk else None
        ct_file_no = clean(row.get("CTFILENO", ""), 100)
        filing_date = parse_date(row.get("FILINGDATE", ""))
        serve_date = parse_date(row.get("SERVEDATE", ""))
        ans_due = parse_date(row.get("ANSDUEDATE", ""))
        trial_date = parse_date(row.get("TRIALDATE", ""))
        outcome = clean(row.get("OUTCOME", ""), 100)
        principal = parse_cents(row.get("PRINCIPAL", "0"))
        interest = parse_cents(row.get("INTEREST", "0"))
        fees = parse_cents(row.get("FEES", "0"))
        costs = parse_cents(row.get("COSTS", "0"))
        legal_cap = clean(row.get("LEGALCAP", ""), 500)
        comments = clean(row.get("COMMENTS", ""), 2000)

        status = "FILED"
        if outcome:
            status = "DISMISSED"
        elif serve_date:
            status = "SERVED"

        batch.append((
            dcs_id, tenant_id, account_id, court_id, None, "civil",
            ct_file_no, ct_file_no, status,
            filing_date, serve_date, ans_due, trial_date,
            principal, interest, fees, costs,
            None, None,
            comments or legal_cap,
            json.dumps({"cm_pk": ff_pk, "outcome": outcome}),
            None, None,
        ))
        processed += 1

        if len(batch) >= BATCH_SIZE:
            if not dry_run:
                await batch_insert(pool, """
                    INSERT INTO litigation_cases (id, tenant_id, account_id,
                        court_id, court_name, court_type,
                        docket_number, case_number, status,
                        filed_date, served_date, answer_due_date, trial_date,
                        principal_claimed, interest_claimed, fees_claimed, costs_claimed,
                        attorney_name, attorney_bar_id,
                        notes, documents,
                        efiling_submission_id, efiling_status)
                    VALUES ($1,$2,$3,$4::uuid,$5,$6,$7,$8,$9::litigationstatus,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23)
                    ON CONFLICT (id) DO NOTHING
                """, batch)
            batch = []
            await flush_pk_map(pool)

    if batch and not dry_run:
        await batch_insert(pool, """
            INSERT INTO litigation_cases (id, tenant_id, account_id,
                court_id, court_name, court_type,
                docket_number, case_number, status,
                filed_date, served_date, answer_due_date, trial_date,
                principal_claimed, interest_claimed, fees_claimed, costs_claimed,
                attorney_name, attorney_bar_id,
                notes, documents,
                efiling_submission_id, efiling_status)
            VALUES ($1,$2,$3,$4::uuid,$5,$6,$7,$8,$9::litigationstatus,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23)
            ON CONFLICT (id) DO NOTHING
        """, batch)
    await flush_pk_map(pool)
    await log_phase_end(pool, lid, processed, skipped, errored)
    log.info("Filings → litigation_cases: %d migrated, %d skipped", processed, skipped)

    # Judgment → judgments
    lid = await log_phase_start(pool, 7, "Judgment")
    processed = skipped = errored = 0
    batch = []

    for row in stream_csv(data_dir, "Judgment.csv"):
        jd_pk = row.get("PKJUDGMENT", "").strip()
        if not jd_pk or lookup_pk(jd_pk):
            skipped += 1
            continue

        ar_pk = clean(row.get("PKAROOT", ""))
        ff_pk = clean(row.get("PKFILING", ""))
        lit_case_id = lookup_pk(ff_pk) if ff_pk else None
        if not lit_case_id:
            skipped += 1
            continue

        dcs_id = map_pk(jd_pk)
        jmt_date = parse_date(row.get("JMTDATE", ""))
        if not jmt_date:
            skipped += 1
            continue
        principal = parse_cents(row.get("PRINCIPAL", "0"))
        interest = parse_cents(row.get("INTEREST", "0"))
        fees = parse_cents(row.get("FEES", "0"))
        costs = parse_cents(row.get("COSTS", "0"))
        total = principal + interest + fees + costs
        sat_date = parse_date(row.get("SATDATE", ""))
        award_rate = parse_decimal(row.get("AWARDRATE", "0")) or Decimal("0")

        batch.append((
            dcs_id, tenant_id, lit_case_id, None,
            jmt_date, total, principal, interest, costs, fees,
            award_rate, "collectmax_migration", jmt_date.year,
            False, None, 0,
            None, sat_date, sat_date is not None,
            "1.0", None,
        ))
        processed += 1

        if len(batch) >= BATCH_SIZE:
            if not dry_run:
                await batch_insert(pool, """
                    INSERT INTO judgments (id, tenant_id, litigation_case_id, policy_pack_id,
                        judgment_date, judgment_amount, principal_amount, interest_amount,
                        costs_amount, attorney_fees_amount,
                        post_judgment_rate, rate_source, rate_effective_year,
                        is_above_threshold, threshold_amount, total_accrued_interest,
                        last_accrual_date, satisfied_date, satisfaction_recorded,
                        calculation_version, source_snapshot_hash)
                    VALUES ($1,$2,$3,$4::uuid,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22)
                    ON CONFLICT (id) DO NOTHING
                """, batch)
            batch = []
            await flush_pk_map(pool)

    if batch and not dry_run:
        await batch_insert(pool, """
            INSERT INTO judgments (id, tenant_id, litigation_case_id, policy_pack_id,
                judgment_date, judgment_amount, principal_amount, interest_amount,
                costs_amount, attorney_fees_amount,
                post_judgment_rate, rate_source, rate_effective_year,
                is_above_threshold, threshold_amount, total_accrued_interest,
                last_accrual_date, satisfied_date, satisfaction_recorded,
                calculation_version, source_snapshot_hash)
            VALUES ($1,$2,$3,$4::uuid,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22)
            ON CONFLICT (id) DO NOTHING
        """, batch)
    await flush_pk_map(pool)
    await log_phase_end(pool, lid, processed, skipped, errored)
    log.info("Judgments: %d migrated, %d skipped", processed, skipped)


# ---------------------------------------------------------------------------
# Phase 8: History & Notes
# ---------------------------------------------------------------------------

async def phase_8(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Migrate _History → activity_entries (the 7.6 GB table).

    Uses uuid4() directly instead of pk_map to avoid OOM on millions of rows.
    """
    log.info("=== PHASE 8: History & Notes (this will take a while) ===")
    tenant_id = pk_map["__TENANT_FLG__"]

    # Build claim→aroot lookup for account linking (lightweight: PK strings only)
    claim_to_aroot: dict[str, str] = {}
    for row in stream_csv(data_dir, "Claim.csv"):
        cm_pk = row.get("PKCLAIM", "").strip()
        ar_pk = row.get("PKAROOT", "").strip()
        if cm_pk and ar_pk:
            claim_to_aroot[cm_pk] = ar_pk
    log.info("Claim→ARoot index: %d entries", len(claim_to_aroot))

    lid = await log_phase_start(pool, 8, "_History")
    processed = skipped = errored = 0
    batch = []

    for row in stream_csv(data_dir, "_History.csv"):
        hi_pk = row.get("PKHISTORY", "").strip()
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
        user_id = lookup_pk(user_pk) if user_pk else None
        tag = clean(row.get("TAG", ""), 50)
        hist_type = clean(row.get("TYPE", ""), 10)

        # Generate UUID directly — do NOT add to pk_map (millions of rows)
        dcs_id = uuid.uuid4()

        # Try to find account from PKFILE
        file_pk = clean(row.get("PKFILE", ""))
        account_id = None
        if file_pk:
            if file_pk in claim_to_aroot:
                account_id = lookup_pk(claim_to_aroot[file_pk])
            else:
                account_id = lookup_pk(file_pk)

        batch.append((
            dcs_id, tenant_id, account_id, None,
            user_id, "COMPLETED", "NORMAL",
            effect_date, enter_time, enter_time,
            note.strip()[:10000],
            json.dumps({"tag": tag, "type": hist_type}),
            None,
        ))
        processed += 1

        if len(batch) >= HISTORY_BATCH_SIZE:
            if not dry_run:
                try:
                    await batch_insert(pool, """
                        INSERT INTO activity_entries (id, tenant_id, account_id,
                            activity_code_id, assigned_to_id,
                            status, priority,
                            scheduled_date, started_at, completed_at,
                            notes, result, parent_entry_id)
                        VALUES ($1,$2,$3,$4::uuid,$5::uuid,$6::activitystatus,$7::activitypriority,$8,$9,$10,$11,$12,$13)
                        ON CONFLICT (id) DO NOTHING
                    """, batch)
                except Exception as e:
                    errored += len(batch)
                    log.warning("Batch error in history: %s", e)
            batch = []
            if processed % 100000 == 0:
                log.info("  History progress: %d rows processed...", processed)

    if batch and not dry_run:
        try:
            await batch_insert(pool, """
                INSERT INTO activity_entries (id, tenant_id, account_id,
                    activity_code_id, assigned_to_id,
                    status, priority,
                    scheduled_date, started_at, completed_at,
                    notes, result, parent_entry_id)
                VALUES ($1,$2,$3,$4::uuid,$5::uuid,$6::activitystatus,$7::activitypriority,$8,$9,$10,$11,$12,$13)
                ON CONFLICT (id) DO NOTHING
            """, batch)
        except Exception as e:
            errored += len(batch)
            log.warning("Final batch error in history: %s", e)

    # Clean up the claim→aroot index
    del claim_to_aroot

    await log_phase_end(pool, lid, processed, skipped, errored)
    log.info("History: %d migrated, %d skipped, %d errors", processed, skipped, errored)


# ---------------------------------------------------------------------------
# Phase 9: Ancillary data
# ---------------------------------------------------------------------------

async def phase_9_payment_plans(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Migrate PayPlan → payment_plans."""
    log.info("--- Phase 9a: PayPlan → payment_plans ---")
    tenant_id = pk_map["__TENANT_FLG__"]
    lid = await log_phase_start(pool, 9, "PayPlan")
    processed = skipped = errored = 0
    batch = []

    freq_map = {"WK": "WEEKLY", "BW": "BIWEEKLY", "MO": "MONTHLY", "SM": "SEMI_MONTHLY"}

    for row in stream_csv(data_dir, "PayPlan.csv"):
        pp_pk = row.get("PKPAYPLAN", "").strip()
        if not pp_pk or lookup_pk(pp_pk):
            skipped += 1
            continue

        ar_pk = clean(row.get("PKACCOUNT", "")) or clean(row.get("PKAROOT", ""))
        account_id = lookup_pk(ar_pk) if ar_pk else None
        if not account_id:
            skipped += 1
            continue

        dcs_id = map_pk(pp_pk)
        amount = parse_cents(row.get("AMOUNT", "0"))
        begin_date = parse_date(row.get("BEGINING", ""))
        freq_raw = clean(row.get("FREQUENCY", ""), 5) or "MO"
        freq = freq_map.get(freq_raw.upper(), "MONTHLY")
        plan_date = parse_date(row.get("PLANDATE", ""))

        batch.append((
            dcs_id, tenant_id, account_id, None,
            "STANDARD", "ACTIVE",
            0,  # total_amount (would need calculation)
            amount, freq,
            0, 0, 0, 0, 0,
            begin_date, begin_date, None,
            False, None, None, None,
            None, None, False, None, None,
            None, None, None, None,
            None, None,
        ))
        processed += 1

        if len(batch) >= BATCH_SIZE:
            if not dry_run:
                await batch_insert(pool, """
                    INSERT INTO payment_plans (id, tenant_id, account_id, consumer_id,
                        plan_type, status,
                        total_amount, payment_amount, frequency,
                        total_payments, payments_made, payments_remaining,
                        amount_paid, balance_remaining,
                        start_date, next_payment_date, end_date,
                        is_settlement, settlement_amount, settlement_percentage,
                        original_balance,
                        pif_tolerance, max_months, auto_post, payment_method, notes,
                        approved_by, approved_at, defaulted_at, default_reason,
                        amortization_schedule, projection_data)
                    VALUES ($1,$2,$3,$4,$5::plantype,$6::planstatus,$7,$8,$9::paymentfrequency,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31,$32)
                    ON CONFLICT (id) DO NOTHING
                """, batch)
            batch = []
            await flush_pk_map(pool)

    if batch and not dry_run:
        await batch_insert(pool, """
            INSERT INTO payment_plans (id, tenant_id, account_id, consumer_id,
                plan_type, status,
                total_amount, payment_amount, frequency,
                total_payments, payments_made, payments_remaining,
                amount_paid, balance_remaining,
                start_date, next_payment_date, end_date,
                is_settlement, settlement_amount, settlement_percentage,
                original_balance,
                pif_tolerance, max_months, auto_post, payment_method, notes,
                approved_by, approved_at, defaulted_at, default_reason,
                amortization_schedule, projection_data)
            VALUES ($1,$2,$3,$4,$5::plantype,$6::planstatus,$7,$8,$9::paymentfrequency,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31,$32)
            ON CONFLICT (id) DO NOTHING
        """, batch)
    await flush_pk_map(pool)
    await log_phase_end(pool, lid, processed, skipped, errored)
    log.info("Payment plans: %d migrated, %d skipped", processed, skipped)


async def phase_9_disputes(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Migrate Dispute → disputes."""
    log.info("--- Phase 9b: Dispute → disputes ---")
    tenant_id = pk_map["__TENANT_FLG__"]
    lid = await log_phase_start(pool, 9, "Dispute")
    processed = skipped = errored = 0
    batch = []

    for row in stream_csv(data_dir, "Dispute.csv"):
        td_pk = row.get("PKDISPUTE", "").strip()
        if not td_pk or lookup_pk(td_pk):
            skipped += 1
            continue

        ar_pk = clean(row.get("PKAROOT", ""))
        account_id = lookup_pk(ar_pk) if ar_pk else None
        if not account_id:
            skipped += 1
            continue

        dcs_id = map_pk(td_pk)
        open_date = parse_date(row.get("OPENDATE", ""))
        close_date = parse_date(row.get("CLOSEDATE", ""))
        notes = clean(row.get("NOTES", ""), 2000)
        disp_id = clean(row.get("DISPUTEID", ""), 100)

        status = "PENDING"
        if close_date:
            status = "RESOLVED_VALID"

        batch.append((
            dcs_id, tenant_id, account_id,
            status, "OTHER", notes,
            open_date or datetime.now(timezone.utc),
            (open_date or datetime.now(timezone.utc)),
            close_date, close_date,
            notes, None,
            json.dumps({"cm_pk": td_pk, "dispute_id": disp_id}),
        ))
        processed += 1

        if len(batch) >= BATCH_SIZE:
            if not dry_run:
                await batch_insert(pool, """
                    INSERT INTO disputes (id, tenant_id, account_id,
                        status, reason, description,
                        filed_at, response_due_date,
                        responded_at, resolved_at,
                        resolution_notes, resolved_by_id,
                        documents)
                    VALUES ($1,$2,$3,$4::disputestatus,$5::disputereason,$6,$7,$8,$9,$10,$11,$12::uuid,$13)
                    ON CONFLICT (id) DO NOTHING
                """, batch)
            batch = []
            await flush_pk_map(pool)

    if batch and not dry_run:
        await batch_insert(pool, """
            INSERT INTO disputes (id, tenant_id, account_id,
                status, reason, description,
                filed_at, response_due_date,
                responded_at, resolved_at,
                resolution_notes, resolved_by_id,
                documents)
            VALUES ($1,$2,$3,$4::disputestatus,$5::disputereason,$6,$7,$8,$9,$10,$11,$12::uuid,$13)
            ON CONFLICT (id) DO NOTHING
        """, batch)
    await flush_pk_map(pool)
    await log_phase_end(pool, lid, processed, skipped, errored)
    log.info("Disputes: %d migrated, %d skipped", processed, skipped)


async def phase_9(pool: asyncpg.Pool, data_dir: Path, dry_run: bool):
    """Phase 9: All ancillary data."""
    log.info("=== PHASE 9: Ancillary Data ===")
    await phase_9_payment_plans(pool, data_dir, dry_run)
    await phase_9_disputes(pool, data_dir, dry_run)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

PHASES = {
    0: phase_0,
    1: phase_1,
    2: phase_2,
    3: phase_3,
    4: phase_4,
    5: phase_5,
    6: phase_6,
    7: phase_7,
    8: phase_8,
    9: phase_9,
}


async def run_migration(args):
    dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql://dcs:dcs@localhost:5432/dcs",
    )
    # asyncpg needs plain postgresql:// not postgresql+asyncpg://
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")

    log.info("Connecting to database: %s", dsn.split("@")[-1])
    pool = await get_pool(dsn)

    try:
        await ensure_migration_tables(pool)
        await load_pk_map(pool)

        phases_to_run = (
            [args.phase] if args.phase is not None
            else sorted(PHASES.keys())
        )

        for p in phases_to_run:
            if p not in PHASES:
                log.error("Unknown phase: %d", p)
                continue
            fn = PHASES[p]
            start = datetime.now()
            await fn(pool, args.data_dir, args.dry_run)
            elapsed = (datetime.now() - start).total_seconds()
            log.info("Phase %d completed in %.1f seconds", p, elapsed)

        # Final PK map flush
        await flush_pk_map(pool)

        # Print summary
        async with pool.acquire() as conn:
            summary = await conn.fetch(
                "SELECT phase, table_name, rows_processed, rows_skipped, rows_errored "
                "FROM _migration_log ORDER BY id"
            )
        log.info("=" * 60)
        log.info("MIGRATION SUMMARY")
        log.info("=" * 60)
        for row in summary:
            log.info(
                "  Phase %d | %-20s | %7d processed | %7d skipped | %4d errors",
                row["phase"], row["table_name"] or "",
                row["rows_processed"], row["rows_skipped"], row["rows_errored"],
            )
        log.info("Total PK mappings: %d", len(pk_map))

    finally:
        await pool.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate CollectMax data to DCS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--phase", type=int, default=None,
        help="Run only a specific phase (0-9). Default: run all.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and validate data without writing to the database.",
    )
    parser.add_argument(
        "--data-dir", type=Path, default=DEFAULT_DATA_DIR,
        help=f"Path to CollectMax CSV exports. Default: {DEFAULT_DATA_DIR}",
    )
    args = parser.parse_args()

    if not args.data_dir.exists():
        log.error("Data directory not found: %s", args.data_dir)
        sys.exit(1)

    mode = "DRY RUN" if args.dry_run else "LIVE"
    log.info("CollectMax → DCS Migration [%s]", mode)
    log.info("Data directory: %s", args.data_dir)

    asyncio.run(run_migration(args))


if __name__ == "__main__":
    main()
