# DCS Deployment Guide

This is the operator-facing guide for deploying DCS from the
`dcs-deploy-<timestamp>.zip` artifact onto a target server.

## TL;DR — both first install and redeploy use the same two commands

```bash
# From your workstation
scp dcs-deploy-<stamp>.zip cquinn@<server>:/tmp/

# On the server
ssh cquinn@<server>
cd /tmp && unzip -q dcs-deploy-<stamp>.zip && cd DCS && sudo bash install.sh
```

`install.sh` auto-detects whether this is a first install or a redeploy,
syncs the source into `/opt/sites/DCS`, runs the right scripts, smoke-
tests the services, and removes the staging directory it was launched
from. After it exits, `/tmp` only contains the original
`dcs-deploy-<stamp>.zip` — nothing else to clean up.

> **Non-legal guidance.** On first install `install.sh` activates the
> seeded NJ + NY policy packs (`nj-2026.1` and `ny-2026.1`). Have
> qualified counsel re-verify the rates and citations in
> `docs/08_nj_policy_pack.md` and `docs/09_ny_policy_pack.md` first.
> Pass `--skip-seed` to defer activation:
> `sudo bash install.sh --skip-seed`.

---

## 0. What's in the zip

| Path                            | Purpose                                              |
|---------------------------------|------------------------------------------------------|
| `services/api/`                 | FastAPI backend (Python 3.11)                        |
| `services/ui/`                  | Next.js + Electron frontend                          |
| `services/api/scripts/`         | `seed.py`, `seed_policy_packs.py`                    |
| `migration/`                    | CollectMax → DCS migration tooling                   |
| `docker/docker-compose.yml`     | Local-dev Postgres + Redis stack                     |
| `scripts/`                      | Server install + redeploy automation (bash)          |
| `scripts/systemd/`              | `dcs-api.service`, `dcs-ui.service`                  |
| `scripts/nginx/dcs.conf`        | Reverse-proxy template                               |
| `docs/`                         | Design docs (00–10)                                  |
| `README.md`, `HOWTO.md`, `DEPLOY.md` | Project, dev, and deploy docs                  |

Excluded from the zip (rebuilt on the target): `services/api/venv`,
`services/ui/node_modules`, `services/ui/.next`, `__pycache__`,
`migration/flg-data` CSVs.

---

## 1. Prerequisites on the target server

Ubuntu 22.04 / 24.04 or RHEL 9.

```bash
# System packages
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip \
                    postgresql postgresql-contrib redis-server \
                    nginx libpq-dev build-essential unzip

# Node.js 22 LTS, system-wide (NOT via nvm — systemd needs system PATH)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# Verify
python3.11 --version    # 3.11.x
node --version          # v22.x
psql --version          # 14+
redis-cli --version
```

Provision the database role and DB the API will use (matches the values
in `services/api/.env.example`):

```bash
sudo -u postgres psql <<SQL
CREATE ROLE dcs LOGIN PASSWORD 'dcs';
CREATE DATABASE dcs OWNER dcs;
ALTER ROLE dcs CREATEDB;     -- needed for `pytest` to spin temp DBs
SQL
```

---

## 2. Upload, unpack, and install — one workflow

From your workstation:

```bash
scp dcs-deploy-<stamp>.zip cquinn@<server>:/tmp/
```

On the server:

```bash
ssh cquinn@<server>
cd /tmp
unzip -q dcs-deploy-<stamp>.zip      # extracts to /tmp/DCS
cd DCS

# First time only — create env files BEFORE install.sh runs:
sudo cp services/api/.env.example       /opt/sites/DCS/services/api/.env       2>/dev/null \
    || (sudo mkdir -p /opt/sites/DCS/services/api && sudo cp services/api/.env.example /opt/sites/DCS/services/api/.env)
sudo cp services/ui/.env.example        /opt/sites/DCS/services/ui/.env.local 2>/dev/null \
    || (sudo mkdir -p /opt/sites/DCS/services/ui  && sudo cp services/ui/.env.example  /opt/sites/DCS/services/ui/.env.local)

# Edit at minimum:
#   /opt/sites/DCS/services/api/.env
#     DATABASE_URL=postgresql+asyncpg://dcs:<real-pw>@localhost:5432/dcs
#     SECRET_KEY=<48+ random chars>
#     DEBUG=false
#     ALLOWED_ORIGINS=https://dcs.<your-domain>
#   /opt/sites/DCS/services/ui/.env.local
#     NEXT_PUBLIC_API_URL=https://dcs.<your-domain>/api
sudo -e /opt/sites/DCS/services/api/.env
sudo -e /opt/sites/DCS/services/ui/.env.local

# Then run the unified installer (auto-detects first-install vs redeploy):
sudo bash install.sh
```

`install.sh` will:

1. Sync the staging tree into `/opt/sites/DCS` (preserving any existing
   venv, node_modules, and .env files).
2. On first install, run `scripts/setup-server.sh` (groups, nginx,
   systemd, venv build, UI build), generate the initial Alembic
   revision, run `alembic upgrade head`, run `seed.py`, and run
   `seed_policy_packs.py --activate`.
3. On redeploy, run `scripts/deploy.sh` (stop services, refresh deps,
   `alembic upgrade head`, reseed policy-pack DRAFTS only, restart).
4. Smoke-test the API and UI.
5. **Remove the staging directory** so `/tmp` is left with only the
   original `.zip` file.

Useful flags:

| Flag | Meaning |
|---|---|
| `--first-install` | Force first-install path even if a previous install was detected |
| `--redeploy`      | Force redeploy path |
| `--skip-seed`     | Do not run `seed.py` or activate policy packs (first install only) |
| `--no-cleanup`    | Keep the staging directory after install (for debugging) |

### 2a. Set the admin password

The migration / sample seed creates `admin@falonilaw.com` with a NULL
password hash. Set one before logging in:

```bash
sudo -u www-data bash -c "
    cd /opt/sites/DCS/services/api
    source venv/bin/activate
    python -c \"
import asyncio, sqlalchemy as sa
from dcs_api.auth.security import hash_password
from dcs_api.database import async_session_factory
async def main():
    async with async_session_factory() as s:
        await s.execute(
            sa.text('UPDATE users SET password_hash=:h WHERE email=:e'),
            {'h': hash_password('CHANGE_ME_ON_FIRST_LOGIN'),
             'e': 'admin@falonilaw.com'},
        )
        await s.commit()
asyncio.run(main())
\"
"
```

Log in at `https://dcs.<your-domain>` and change the password from the
UI immediately.

### 2b. Optional: TLS

```bash
sudo bash /opt/sites/DCS/scripts/setup-ssl.sh    # self-signed for staging
# or use certbot for production:
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d dcs.<your-domain>
```

---

## 3. Subsequent redeploys

Same flow as the first install — `install.sh` detects the existing
deployment and dispatches to `scripts/deploy.sh` instead of bootstrapping
from scratch:

```bash
# Workstation
scp dcs-deploy-<stamp>.zip cquinn@<server>:/tmp/

# Server
ssh cquinn@<server>
cd /tmp && unzip -q dcs-deploy-<stamp>.zip && cd DCS && sudo bash install.sh
```

When you only need to touch one service or seed data, the targeted
helpers are still available on the installed server:

| Scenario                        | Run this                                                     |
|---------------------------------|--------------------------------------------------------------|
| Full redeploy from a new zip    | `sudo bash install.sh` (from the unzipped staging dir)       |
| API only (no zip change)        | `sudo bash /opt/sites/DCS/scripts/deploy-api.sh`             |
| UI only (no zip change)         | `sudo bash /opt/sites/DCS/scripts/deploy-ui.sh`              |
| Reseed sample data + packs      | `sudo bash /opt/sites/DCS/scripts/seed-db.sh`                |
| Reseed policy packs (DRAFT)     | `sudo bash /opt/sites/DCS/scripts/seed-policy-packs.sh`      |
| Activate a new draft pack       | `sudo bash /opt/sites/DCS/scripts/seed-policy-packs.sh --activate` |
| Tail live logs                  | `sudo bash /opt/sites/DCS/scripts/logs.sh`                   |
| Health summary                  | `sudo bash /opt/sites/DCS/scripts/status.sh`                 |
| Wipe DB (dev only)              | `sudo bash /opt/sites/DCS/scripts/nuke-db.sh`                |

`install.sh` (and `scripts/deploy.sh` underneath it) re-runs the Alembic
upgrade and the policy-pack DRAFT reseed automatically; it does **not**
auto-activate new pack versions on redeploy (intentional — staging
review required first).

---

## 5. Smoke tests after deploy

```bash
# Service health
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:3000 > /dev/null && echo "UI OK"

# Active policy packs
sudo -u www-data bash -c "
    cd /opt/sites/DCS/services/api && source venv/bin/activate
    python -c \"
import asyncio, sqlalchemy as sa
from dcs_api.database import async_session_factory
async def main():
    async with async_session_factory() as s:
        rows = await s.execute(sa.text(
            \\\"SELECT jurisdiction, version, status FROM policy_packs ORDER BY jurisdiction\\\"))
        for r in rows: print(r)
asyncio.run(main())
\"
"

# Notice templates registered
sudo -u www-data bash -c "
    cd /opt/sites/DCS/services/api && source venv/bin/activate
    python -c 'from dcs_api.notices import list_templates; \
[print(t.jurisdiction, t.template_id, t.version) for t in list_templates()]'
"
```

Expected output:

```
('NJ', 'nj-2026.1', 'ACTIVE')
('NY', 'ny-2026.1', 'ACTIVE')
NJ nj.initial_communication 2026.1
NJ nj.validation_notice 2026.1
NJ nj.dispute_acknowledgement 2026.1
NJ nj.post_judgment_disclosure 2026.1
NY ny.initial_communication 2026.1
NY ny.validation_notice 2026.1
NY ny.dispute_acknowledgement 2026.1
NY ny.post_judgment_disclosure 2026.1
```

---

## 6. Rollback

The deploy scripts do not snapshot the previous release. Recommended:

```bash
# Before each deploy, capture the current tree:
sudo tar -C /opt/sites -czf /opt/sites/dcs-prerelease-$(date +%F-%H%M).tgz DCS
```

To roll back:

```bash
sudo systemctl stop dcs-ui dcs-api
sudo rm -rf /opt/sites/DCS
sudo tar -C /opt/sites -xzf /opt/sites/dcs-prerelease-<stamp>.tgz
sudo bash /opt/sites/DCS/scripts/deploy-api.sh
```

If a policy-pack version was activated and the new pack is bad,
manually flip it back in the DB:

```sql
UPDATE policy_packs SET status='SUPERSEDED' WHERE version='nj-2026.2' AND jurisdiction='NJ';
UPDATE policy_packs SET status='ACTIVE'      WHERE version='nj-2026.1' AND jurisdiction='NJ';
```

---

## 7. Day-2 operations

| Task                                  | Command                                                      |
|---------------------------------------|--------------------------------------------------------------|
| Tail API logs                         | `journalctl -u dcs-api -f`                                   |
| Tail UI logs                          | `journalctl -u dcs-ui -f`                                    |
| Restart API                           | `sudo systemctl restart dcs-api`                             |
| Restart UI                            | `sudo systemctl restart dcs-ui`                              |
| Reload nginx                          | `sudo nginx -t && sudo systemctl reload nginx`               |
| Run CollectMax migration              | See `migration/README.md`                                    |
| Inspect last calculation results      | `psql -U dcs -d dcs -c 'SELECT * FROM calculation_results ORDER BY created_at DESC LIMIT 20;'` |
| Inspect notices sent today            | `psql -U dcs -d dcs -c "SELECT id, template_id, channel, status, content_hash, sent_at FROM notices WHERE sent_at::date = current_date;"` |

---

## 8. Quick reference: which script does what

```
install.sh                      # In the zip — unified installer / redeploy
                                # (auto-detects, runs the right scripts, then
                                #  removes the staging dir so /tmp keeps only
                                #  the .zip you uploaded)

scripts/setup-server.sh         # Internal: first-time bootstrap
scripts/deploy.sh               # Internal: full redeploy (API + UI)
scripts/deploy-api.sh           # API-only redeploy (no zip change required)
scripts/deploy-ui.sh            # UI-only redeploy
scripts/seed-db.sh              # Sample data + activate NJ/NY packs
scripts/seed-policy-packs.sh    # NJ/NY packs only (DRAFT)
scripts/seed-policy-packs.sh --activate   # NJ/NY packs only, ACTIVATE
scripts/setup-ssl.sh            # Self-signed TLS
scripts/logs.sh                 # Tail journalctl for both services
scripts/status.sh               # systemctl + curl health summary
scripts/nuke-db.sh              # WIPE DB (dev only — irreversible)
scripts/rebuild.sh              # Force rebuild venv + node_modules
```

After every install, a copy of the executed `install.sh` is preserved at
`/opt/sites/DCS/install.sh.last-deployed` (read-only) for audit.
