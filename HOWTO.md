# DCS - How to Install and Run

## Prerequisites

| Tool | Version | Check with |
|------|---------|------------|
| Python | 3.11+ | `python3 --version` |
| Node.js | 20+ | `node --version` |
| npm | 9+ | `npm --version` |
| Docker & Docker Compose | Latest | `docker compose version` |

## Step 1: Start Database and Cache Services

From the project root, spin up PostgreSQL and Redis:

```bash
cd DCS
docker compose -f docker/docker-compose.yml up -d
```

Verify both are healthy:

```bash
docker compose -f docker/docker-compose.yml ps
```

You should see `dcs-postgres` and `dcs-redis` both running.

## Step 2: Set Up the API Backend

### 2a. Create virtual environment and install dependencies

```bash
cd services/api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2b. Create your .env file

```bash
cp .env.example .env
```

The defaults work with the Docker Compose services out of the box.

### 2c. Run database migrations

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

### 2d. Start the API server

```bash
uvicorn dcs_api.main:app --reload --host 0.0.0.0 --port 8000
```

Verify at:
- Health check: http://localhost:8000/health
- API docs (dev only): http://localhost:8000/docs

## Step 3: Set Up the Frontend UI

Open a **new terminal**:

### 3a. Install dependencies

```bash
cd DCS/services/ui
npm install
```

### 3b. Create .env file

```bash
cp .env.example .env
```

### 3c. Start Next.js dev server

```bash
npm run dev
```

Web UI available at http://localhost:3000

## Step 4 (Optional): Run as Electron Desktop App

```bash
cd DCS/services/ui
npm run electron:dev
```

## Step 5: Run Tests

```bash
cd DCS/services/api
source venv/bin/activate
pytest
```

## Services Reference

| Service | URL | Credentials |
|---------|-----|-------------|
| PostgreSQL | `localhost:5432` | User: `dcs`, Password: `dcs`, DB: `dcs` |
| Redis | `localhost:6379` | Password: `dcs_redis_dev` |
| API | http://localhost:8000 | — |
| API Docs | http://localhost:8000/docs | Only when `DEBUG=true` |
| Web UI | http://localhost:3000 | — |

## Troubleshooting

- **"relation does not exist"** — Run `alembic upgrade head` from `services/api`.
- **Port 5432 in use** — Stop existing PostgreSQL or change port in `docker/docker-compose.yml`.
- **pip install fails on asyncpg** — Install Postgres headers: `brew install postgresql` (macOS) or `sudo apt install libpq-dev` (Ubuntu).
- **UI can't reach API** — Verify API is on port 8000 and `NEXT_PUBLIC_API_URL=http://localhost:8000` in `services/ui/.env`.
