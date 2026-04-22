# DCS - Debt Collection System

A compliant, auditable, production-ready debt collection platform for U.S. markets.

## Overview

DCS is a web-first debt collection platform designed for:
- Collection agencies
- Law firms
- In-house collections
- Debt buyers

**Shipped jurisdictions:** New Jersey (`nj-2026.1`) and New York (`ny-2026.1`).
Additional state packs follow the same shape — see
[docs/08_nj_policy_pack.md](docs/08_nj_policy_pack.md) and
[docs/09_ny_policy_pack.md](docs/09_ny_policy_pack.md).

## Compliance Framework

- **FDCPA** — 15 U.S.C. § 1692 et seq.
- **CFPB Regulation F** — 12 C.F.R. Part 1006 (validation: § 1006.34;
  7-in-7: § 1006.14(b)(2)(i); dispute pause: § 1006.38(d))
- **TCPA** — 47 U.S.C. § 227; 47 C.F.R. § 64.1200 (consent for autodialed
  calls / SMS)
- **NJ overlay** — N.J. Court Rules R. 4:42-11(a) (post-judgment),
  N.J.S.A. 2A:14-1 / 2A:14-5 (SOL), N.J.S.A. 45:18 et seq. (licensing)
- **NY overlay** — N.Y. C.P.L.R. § 5004(a)/(b) (post-judgment),
  CPLR § 213(2) / § 214-i CCFA (SOL), N.Y. Gen. Bus. Law Art. 29-H

*Non-legal guidance: This software assists with compliance but does not guarantee it. Consult legal counsel for compliance verification.*

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend                                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │  Collector UI   │  │  Consumer Portal│  │   Admin Panel   │              │
│  │  (React/Next)   │  │  (React/Next)   │  │  (React/Next)   │              │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘              │
└───────────┼─────────────────────┼─────────────────────┼─────────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API Layer                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    FastAPI (Python 3.11+)                           │    │
│  │  - REST endpoints                                                   │    │
│  │  - RBAC enforcement                                                 │    │
│  │  - Audit logging                                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Core Services                                      │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌──────────────┐  │
│  │ Calculation   │  │  Compliance   │  │   Workflow    │  │   Consent    │  │
│  │    Engine     │  │    Engine     │  │    Engine     │  │   Manager    │  │
│  └───────────────┘  └───────────────┘  └───────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Data Layer                                         │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                    │
│  │  PostgreSQL   │  │    Redis      │  │  Audit Store  │                    │
│  │  (Primary DB) │  │   (Cache)     │  │ (Append-only) │                    │
│  └───────────────┘  └───────────────┘  └───────────────┘                    │
└─────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Integrations                                        │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌──────────────┐  │
│  │   IdP (OIDC)  │  │    Tratta     │  │    Vonage     │  │  E-Filing    │  │
│  │  Azure/Okta   │  │   Payments    │  │  Voice/SMS    │  │  Connector   │  │
│  └───────────────┘  └───────────────┘  └───────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Key Features

### Multi-Tenant SaaS
- Tenant isolation
- Custom role configuration
- Business model flexibility (subscription, per-account, contingency, debt-buyer)

### Compliance Engine
- Jurisdiction-specific policy packs
- Automatic contact hour enforcement
- Consent tracking (TCPA)
- Validation notice workflows (Reg F)
- Legal hold management

### Calculation Engine
- Simple and compound interest
- Post-judgment interest (jurisdiction-specific)
- Payment allocation (configurable)
- Full audit trail with version tracking

### Consumer Portal
- Dispute submission
- Payment processing
- Opt-out management

### Collector Workflows
- Account management
- Contact scheduling
- Litigation support
- Judgment tracking

## Project Structure

```
DCS/
├── docs/                    # Design documentation
├── services/
│   ├── api/                 # FastAPI backend
│   │   ├── dcs_api/
│   │   │   ├── models/      # SQLAlchemy models
│   │   │   ├── schemas/     # Pydantic schemas
│   │   │   ├── routers/     # API endpoints
│   │   │   ├── auth/        # Authentication/RBAC
│   │   │   └── compliance/  # Policy packs, rules
│   │   └── tests/
│   └── ui/                  # Next.js + Electron frontend
│       ├── src/
│       │   ├── app/         # Next.js pages
│       │   ├── components/  # React components
│       │   ├── stores/      # Zustand state
│       │   └── lib/         # Utilities
│       └── electron/        # Electron main process
├── docker/                  # Docker Compose for dev
└── scripts/                 # Utility scripts
```

## Clients

DCS provides two client options:

### Web Client (Next.js)
- Modern React UI with Next.js 14
- Server-side rendering for SEO and performance
- Responsive design with Tailwind CSS
- Dark mode support

### Desktop Client (Electron)
- Cross-platform (Windows, macOS, Linux)
- System SSO integration (no embedded secrets)
- Offline-capable for field use
- Native OS integration

```bash
# Run web client
cd services/ui && npm run dev

# Run Electron client (development)
cd services/ui && npm run electron:dev

# Build Electron for distribution
npm run electron:build:win   # Windows
npm run electron:build:mac   # macOS
npm run electron:build:linux # Linux
```

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Node.js 20+ (for UI)

### Installation

```bash
cd services/api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# Seed NJ + NY policy packs (idempotent; activates v2026.1 packs)
python scripts/seed_policy_packs.py --activate

uvicorn dcs_api.main:app --reload
```

## Documentation

| Document | Description |
|----------|-------------|
| [00_overview.md](docs/00_overview.md) | Project scope and defaults |
| [01_policies.md](docs/01_policies.md) | Compliance policies |
| [02_compliance_nj_truth_set.md](docs/02_compliance_nj_truth_set.md) | NJ legal requirements |
| [03_data_model.md](docs/03_data_model.md) | Database entities |
| [04_workflows.md](docs/04_workflows.md) | Business workflows |
| [05_rbac.md](docs/05_rbac.md) | Role-based access control |
| [06_calculation_engine.md](docs/06_calculation_engine.md) | Interest calculations |
| [07_integrations.md](docs/07_integrations.md) | Third-party integrations |
| [08_nj_policy_pack.md](docs/08_nj_policy_pack.md) | NJ-specific rules and rates (`nj-2026.1`) |
| [09_ny_policy_pack.md](docs/09_ny_policy_pack.md) | NY-specific rules and rates (`ny-2026.1`) |
| [10_notice_templates.md](docs/10_notice_templates.md) | Notice templates and renderer |

## Compliance Disclaimer

This software provides tools to assist with debt collection compliance. It is not a substitute for legal advice. Users must:
- Verify all regulatory requirements with qualified legal counsel
- Maintain appropriate licenses and bonds
- Configure system policies according to applicable law
- Conduct regular compliance audits

**Non-legal guidance:** All compliance features are provided as assistance only.

## License

Proprietary - All rights reserved.
