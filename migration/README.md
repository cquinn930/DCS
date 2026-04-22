# CollectMax → DCS Migration

Migrates FLG's (Faloni Law Group) CollectMax data (Advantage DB CSV exports)
into the DCS PostgreSQL database as a new tenant.

## Prerequisites

- CSV exports from CollectMax placed in `/opt/sites/DCS/migration/flg-data/`
- DCS API services running with database migrations applied
- Python venv with `asyncpg` installed

## Quick Start

```bash
# SSH into the server
ssh cquinn@falreports

# Activate the DCS venv
cd /opt/sites/DCS
source services/api/venv/bin/activate

# Dry run first (parses data, validates, no DB writes)
python migration/migrate_collectmax.py --dry-run

# Run all phases
python migration/migrate_collectmax.py

# Or run a single phase
python migration/migrate_collectmax.py --phase 0   # tenant + admin
python migration/migrate_collectmax.py --phase 1   # reference data
python migration/migrate_collectmax.py --phase 2   # client lookup
python migration/migrate_collectmax.py --phase 3   # consumers
python migration/migrate_collectmax.py --phase 4   # accounts
python migration/migrate_collectmax.py --phase 5   # addresses + phones
python migration/migrate_collectmax.py --phase 6   # financial
python migration/migrate_collectmax.py --phase 7   # legal
python migration/migrate_collectmax.py --phase 8   # history (7.6 GB — slow)
python migration/migrate_collectmax.py --phase 9   # payment plans, disputes
```

## Phases

| # | What | Source Tables | Target Tables | Size |
|---|------|-------------|--------------|------|
| 0 | Tenant + admin | — | `tenants`, `users` | instant |
| 1 | Reference data | `UserCode`, `ActCode`, `CrtCode`, `BankAcct` | `users`, `activity_codes`, `courts`, `trust_accounts` | < 1 min |
| 2 | Client lookup | `Client`, `Demog` | in-memory only | < 2 min |
| 3 | Consumers | `Demog`, `AComp` | `consumers`, `contact_methods` | ~2 min |
| 4 | Accounts | `ARoot`, `AComp`, `Claim`, `StatCode` | `accounts` | ~3 min |
| 5 | Contact data | `MultAddr`, `MultPh` | `contact_methods` | ~3 min |
| 6 | Financial | `Journal` | `payments`, `trust_transactions` | ~5 min |
| 7 | Legal | `Filing`, `Judgment` | `litigation_cases`, `judgments` | ~2 min |
| 8 | History | `_History` | `activity_entries` | ~30+ min |
| 9 | Ancillary | `PayPlan`, `Dispute` | `payment_plans`, `disputes` | < 1 min |

## How It Works

1. **PK Mapping**: Every CollectMax primary key (e.g. `AR000001`) gets mapped
   to a DCS UUID. Mappings are persisted in `_migration_pk_map` so the script
   is idempotent — re-running skips already-migrated records.

2. **Streaming**: CSV files are streamed row-by-row (never loaded fully into
   memory), so the 7.6 GB `_History.csv` is fine.

3. **Batched Inserts**: Rows are inserted in batches of 1000 (500 for history)
   via `asyncpg.executemany` for performance.

4. **Phase Dependencies**: Phases must run in order (0→9) on first run.
   After that, individual phases can be re-run safely.

## CollectMax → DCS Table Mapping

| CollectMax | DCS | Notes |
|-----------|-----|-------|
| `ARoot` | `accounts` | Main account record |
| `Claim` | account balances | Sub-account with interest/balances |
| `AComp` | relationship links | Connects clients, debtors, claims |
| `Demog` (debtor) | `consumers` | PII: name, SSN, DOB, address |
| `Demog` (client) | `account.original_creditor` | Client name string |
| `Client` | client metadata | Commission rates, settings |
| `MultAddr` | `contact_methods` | Additional addresses |
| `MultPh` | `contact_methods` | Additional phone numbers |
| `Journal` | `payments` / `trust_transactions` | Financial transactions |
| `Filing` | `litigation_cases` | Court filings |
| `Judgment` | `judgments` | Judgment records |
| `_History` | `activity_entries` | Notes and history events |
| `PayPlan` | `payment_plans` | Payment arrangements |
| `Dispute` | `disputes` | Consumer disputes |
| `StatCode` | status mapping | Account status codes |
| `ActCode` | `activity_codes` | Action/activity codes |
| `CrtCode` | `courts` | Court definitions |
| `BankAcct` | `trust_accounts` | Bank accounts |
| `UserCode` | `users` | Operators/collectors |

## Post-Migration

After migration completes:

```bash
# Restart the API to pick up new data
sudo systemctl restart dcs-api

# Log in at https://dcs.flnet.local with:
#   Email: admin@falonilaw.com
#
# Set the admin password (the migration script does NOT seed a password —
# the user is created with a NULL password hash, which the auth layer
# refuses). Use one of the following before first login:
#
#   # Option 1: from a Python shell with the API venv active
#   from dcs_api.auth.security import hash_password
#   from dcs_api.database import sessionmaker
#   import asyncio, sqlalchemy as sa
#   async def main():
#       async with sessionmaker()() as s:
#           await s.execute(sa.text(
#               "UPDATE users SET password_hash = :h "
#               "WHERE email = 'admin@falonilaw.com'"
#           ), {"h": hash_password("CHANGE_ME_ON_FIRST_LOGIN")})
#           await s.commit()
#   asyncio.run(main())
#
#   # Option 2: hit the password-reset endpoint immediately after restart
#   curl -X POST https://dcs.flnet.local/api/v1/auth/password-reset \
#        -d '{"email":"admin@falonilaw.com"}'
#
# Then log in and change the password from the UI. Do NOT leave the
# default password active on a production deployment.

# Seed the NJ + NY policy packs once after restart so calculations and
# notices have something to bind to:
python /opt/sites/DCS/services/api/scripts/seed_policy_packs.py --activate

# Check migration stats
psql -U dcs -d dcs -c "SELECT * FROM _migration_log ORDER BY id;"

# Check record counts
psql -U dcs -d dcs -c "
  SELECT 'tenants' as tbl, count(*) FROM tenants
  UNION ALL SELECT 'consumers', count(*) FROM consumers
  UNION ALL SELECT 'accounts', count(*) FROM accounts
  UNION ALL SELECT 'payments', count(*) FROM payments
  UNION ALL SELECT 'activity_entries', count(*) FROM activity_entries
  UNION ALL SELECT 'litigation_cases', count(*) FROM litigation_cases
  ORDER BY 1;
"
```

## Troubleshooting

- **"asyncpg not found"**: Make sure you activated the venv:
  `source /opt/sites/DCS/services/api/venv/bin/activate`
- **Connection refused**: Ensure PostgreSQL is running:
  `sudo systemctl status postgresql`
- **Permission denied on CSV files**: Ensure the migration user can read them:
  `chmod -R g+r /opt/sites/DCS/migration/flg-data/`
- **Out of memory**: Shouldn't happen (streaming), but you can run individual
  phases with `--phase N`
