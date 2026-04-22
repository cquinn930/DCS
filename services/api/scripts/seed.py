"""Seed development data for the DCS API.

Run from services/api:
    python scripts/seed.py
"""

from __future__ import annotations

import asyncio
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure `dcs_api` is importable when run as `python scripts/seed.py`
_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dcs_api.auth.password import hash_password
from dcs_api.auth.rbac import Permissions
from dcs_api.config import get_settings
from dcs_api.engines.report_library import get_standard_report_definitions
from dcs_api.models.account import Account, AccountStatus, DebtType
from dcs_api.models.consumer import Consumer, ContactMethod, ContactType
from dcs_api.models.customization import (
    OutputFormat,
    ReportEntity,
    ReportTemplate,
    ReportType,
)
from dcs_api.models.tenant import (
    BusinessModel,
    Permission,
    Role,
    RolePermission,
    RoleType,
    Tenant,
    TenantStatus,
    User,
    UserRole,
)

MASTER_SLUG = "master"


def _collect_permission_definitions() -> list[tuple[str, str, str, bool]]:
    """Build (code, display name, category, is_owner_only) from Permissions constants."""
    rows: list[tuple[str, str, str, bool]] = []
    owner_only_codes = {
        Permissions.ASSIGN_OWNER_PERMISSIONS,
        Permissions.CONFIGURE_RETENTION,
    }
    for name in sorted(dir(Permissions)):
        if name.startswith("_"):
            continue
        val = getattr(Permissions, name)
        if not isinstance(val, str) or ":" not in val:
            continue
        code = val
        category = code.split(":", 1)[0]
        display = name.replace("_", " ").title()
        rows.append((code, display, category, code in owner_only_codes))
    return rows


async def _ensure_permissions(session: AsyncSession) -> dict[str, uuid.UUID]:
    """Insert missing Permission rows; return code -> id."""
    mapping: dict[str, uuid.UUID] = {}
    for code, display, category, owner_only in _collect_permission_definitions():
        result = await session.execute(select(Permission).where(Permission.code == code))
        existing = result.scalar_one_or_none()
        if existing:
            mapping[code] = existing.id
            continue
        perm = Permission(
            id=uuid.uuid4(),
            code=code,
            name=display,
            description=None,
            category=category,
            is_owner_only=owner_only,
        )
        session.add(perm)
        await session.flush()
        mapping[code] = perm.id
    return mapping


def _perm_ids(codes: list[str], by_code: dict[str, uuid.UUID]) -> list[uuid.UUID]:
    return [by_code[c] for c in codes]


async def _link_role_permissions(
    session: AsyncSession,
    role_id: uuid.UUID,
    permission_ids: list[uuid.UUID],
) -> None:
    for pid in permission_ids:
        rp = RolePermission(
            id=uuid.uuid4(),
            role_id=role_id,
            permission_id=pid,
        )
        session.add(rp)


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        echo=settings.debug,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with session_factory() as session:
            existing = await session.execute(
                select(Tenant).where(Tenant.slug == MASTER_SLUG)
            )
            if existing.scalar_one_or_none():
                print("Seed data already exists, skipping.")
                return

            perm_by_code = await _ensure_permissions(session)

            # --- Tenants
            master_tenant_id = uuid.uuid4()
            acme_tenant_id = uuid.uuid4()

            master_tenant = Tenant(
                id=master_tenant_id,
                name="DCS Platform",
                slug="master",
                status=TenantStatus.ACTIVE,
                business_model=BusinessModel.SUBSCRIPTION,
                default_jurisdiction="NJ",
            )
            acme_tenant = Tenant(
                id=acme_tenant_id,
                name="Acme Collections",
                slug="acme",
                status=TenantStatus.ACTIVE,
                business_model=BusinessModel.CONTINGENCY,
                default_jurisdiction="NJ",
            )
            session.add(master_tenant)
            session.add(acme_tenant)
            await session.flush()

            # --- Users
            master_admin_id = uuid.uuid4()
            acme_owner_id = uuid.uuid4()
            acme_collector_id = uuid.uuid4()

            master_admin = User(
                id=master_admin_id,
                tenant_id=master_tenant_id,
                email="admin@dcs.example.com",
                password_hash=hash_password("Admin123!@#"),
                first_name="System",
                last_name="Admin",
                is_active=True,
                is_owner=True,
                is_master=True,
            )
            acme_owner = User(
                id=acme_owner_id,
                tenant_id=acme_tenant_id,
                email="owner@acme.example.com",
                password_hash=hash_password("Owner123!@#"),
                first_name="Sarah",
                last_name="Johnson",
                is_active=True,
                is_owner=True,
                is_master=False,
            )
            acme_collector = User(
                id=acme_collector_id,
                tenant_id=acme_tenant_id,
                email="collector@acme.example.com",
                password_hash=hash_password("Collect123!@#"),
                first_name="Mike",
                last_name="Williams",
                is_active=True,
                is_owner=False,
                is_master=False,
            )
            session.add(master_admin)
            session.add(acme_owner)
            session.add(acme_collector)
            await session.flush()

            # --- Acme roles + permissions (aligned with tests/test_rbac.py)
            admin_role_id = uuid.uuid4()
            collector_role_id = uuid.uuid4()
            supervisor_role_id = uuid.uuid4()

            role_admin = Role(
                id=admin_role_id,
                tenant_id=acme_tenant_id,
                name="Admin",
                description="Tenant administration",
                role_type=RoleType.ADMIN,
                is_system=True,
            )
            role_collector = Role(
                id=collector_role_id,
                tenant_id=acme_tenant_id,
                name="Collector",
                description="Collection agent",
                role_type=RoleType.COLLECTOR,
                is_system=True,
            )
            role_supervisor = Role(
                id=supervisor_role_id,
                tenant_id=acme_tenant_id,
                name="Supervisor",
                description="Team supervisor",
                role_type=RoleType.SUPERVISOR,
                is_system=True,
            )
            session.add(role_admin)
            session.add(role_collector)
            session.add(role_supervisor)
            await session.flush()

            admin_codes = [
                Permissions.VIEW_ALL_ACCOUNTS,
                Permissions.MANAGE_USERS,
                Permissions.CREATE_CUSTOM_ROLES,
                Permissions.CONFIGURE_INTEGRATIONS,
            ]
            collector_codes = [
                Permissions.VIEW_ASSIGNED_ACCOUNTS,
                Permissions.EDIT_ACCOUNT_CONTACT,
                Permissions.CREATE_OUTBOUND_CONTACT,
                Permissions.MANAGE_DISPUTES,
            ]
            supervisor_codes = [
                Permissions.VIEW_ASSIGNED_ACCOUNTS,
                Permissions.VIEW_ALL_ACCOUNTS,
                Permissions.EDIT_ACCOUNT_CONTACT,
                Permissions.EDIT_BALANCES_FEES,
                Permissions.CREATE_OUTBOUND_CONTACT,
                Permissions.MANAGE_DISPUTES,
                Permissions.APPROVE_DISPUTE_RESOLUTION,
            ]

            await _link_role_permissions(
                session, admin_role_id, _perm_ids(admin_codes, perm_by_code)
            )
            await _link_role_permissions(
                session, collector_role_id, _perm_ids(collector_codes, perm_by_code)
            )
            await _link_role_permissions(
                session, supervisor_role_id, _perm_ids(supervisor_codes, perm_by_code)
            )

            # Master tenant "Master" role (metadata / lockdown) for JWT permissions
            master_role_id = uuid.uuid4()
            role_master = Role(
                id=master_role_id,
                tenant_id=master_tenant_id,
                name="Master",
                description="Platform master operations",
                role_type=RoleType.MASTER,
                is_system=True,
            )
            session.add(role_master)
            await session.flush()
            master_codes = [
                Permissions.VIEW_TENANT_METADATA,
                Permissions.LIFT_BREACH_LOCKDOWN,
            ]
            await _link_role_permissions(
                session, master_role_id, _perm_ids(master_codes, perm_by_code)
            )

            # User ↔ role assignments
            session.add(
                UserRole(
                    id=uuid.uuid4(),
                    user_id=master_admin_id,
                    role_id=master_role_id,
                    granted_by=None,
                )
            )
            session.add(
                UserRole(
                    id=uuid.uuid4(),
                    user_id=acme_owner_id,
                    role_id=admin_role_id,
                    granted_by=master_admin_id,
                )
            )
            session.add(
                UserRole(
                    id=uuid.uuid4(),
                    user_id=acme_collector_id,
                    role_id=collector_role_id,
                    granted_by=acme_owner_id,
                )
            )
            await session.flush()

            # --- Consumers + contact methods
            def _dob(y: int, m: int, d: int) -> datetime:
                return datetime(y, m, d, tzinfo=timezone.utc)

            consumers_spec = [
                {
                    "first_name": "James",
                    "last_name": "Martinez",
                    "middle_name": "A",
                    "ssn_last_four": "4521",
                    "date_of_birth": _dob(1982, 4, 12),
                    "phone": "+1-973-555-0142",
                    "email": "james.martinez@email.example.com",
                    "addr": {
                        "line1": "142 Oak Street",
                        "city": "Newark",
                        "state": "NJ",
                        "postal": "07102",
                    },
                },
                {
                    "first_name": "Emily",
                    "last_name": "Chen",
                    "middle_name": None,
                    "ssn_last_four": "8890",
                    "date_of_birth": _dob(1990, 7, 22),
                    "phone": "+1-201-555-0198",
                    "email": "emily.chen@mail.example.com",
                    "addr": {
                        "line1": "88 River Road, Apt 3B",
                        "city": "Jersey City",
                        "state": "NJ",
                        "postal": "07302",
                    },
                },
                {
                    "first_name": "Robert",
                    "last_name": "Thompson",
                    "middle_name": "L",
                    "ssn_last_four": "3344",
                    "date_of_birth": _dob(1978, 11, 30),
                    "phone": "+1-716-555-0167",
                    "email": "r.thompson@email.example.com",
                    "addr": {
                        "line1": "500 Main Street",
                        "city": "Buffalo",
                        "state": "NY",
                        "postal": "14202",
                    },
                },
            ]

            consumer_ids: list[uuid.UUID] = []
            for spec in consumers_spec:
                cid = uuid.uuid4()
                consumer_ids.append(cid)
                consumer = Consumer(
                    id=cid,
                    tenant_id=acme_tenant_id,
                    first_name=spec["first_name"],
                    last_name=spec["last_name"],
                    middle_name=spec["middle_name"],
                    suffix=None,
                    ssn_last_four=spec["ssn_last_four"],
                    date_of_birth=spec["date_of_birth"],
                )
                session.add(consumer)

                phone_cm = ContactMethod(
                    id=uuid.uuid4(),
                    tenant_id=acme_tenant_id,
                    consumer_id=cid,
                    contact_type=ContactType.PHONE_MOBILE,
                    value=spec["phone"],
                    is_primary=True,
                )
                email_cm = ContactMethod(
                    id=uuid.uuid4(),
                    tenant_id=acme_tenant_id,
                    consumer_id=cid,
                    contact_type=ContactType.EMAIL,
                    value=spec["email"],
                    is_primary=False,
                )
                addr = spec["addr"]
                addr_cm = ContactMethod(
                    id=uuid.uuid4(),
                    tenant_id=acme_tenant_id,
                    consumer_id=cid,
                    contact_type=ContactType.ADDRESS_HOME,
                    value=f"{addr['line1']}, {addr['city']}, {addr['state']} {addr['postal']}",
                    is_primary=False,
                    address_line_1=addr["line1"],
                    city=addr["city"],
                    state=addr["state"],
                    postal_code=addr["postal"],
                )
                session.add(phone_cm)
                session.add(email_cm)
                session.add(addr_cm)

            await session.flush()

            # --- Accounts (balances in cents; total = principal + interest + fees)
            placed = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
            accounts_spec = [
                {
                    "ref": "ACC-1001",
                    "creditor": "Regional Medical Group",
                    "original_cents": 5_000_00,
                    "current_principal_cents": 2_345_00,
                    "interest_cents": 0,
                    "fees_cents": 0,
                },
                {
                    "ref": "ACC-2044",
                    "creditor": "Capital One Bank",
                    "original_cents": 8_000_00,
                    "current_principal_cents": 5_678_90,
                    "interest_cents": 0,
                    "fees_cents": 0,
                },
                {
                    "ref": "ACC-3099",
                    "creditor": "Utility Services Inc.",
                    "original_cents": 15_000_00,
                    "current_principal_cents": 12_345_00,
                    "interest_cents": 0,
                    "fees_cents": 0,
                },
            ]

            account_ids: list[uuid.UUID] = []
            for i, spec in enumerate(accounts_spec):
                aid = uuid.uuid4()
                account_ids.append(aid)
                principal = spec["current_principal_cents"]
                interest = spec["interest_cents"]
                fees = spec["fees_cents"]
                total = principal + interest + fees
                account = Account(
                    id=aid,
                    tenant_id=acme_tenant_id,
                    consumer_id=consumer_ids[i],
                    account_reference=spec["ref"],
                    original_creditor=spec["creditor"],
                    status=AccountStatus.ACTIVE,
                    debt_type=DebtType.CONSUMER,
                    jurisdiction="NJ",
                    original_principal=spec["original_cents"],
                    current_principal=principal,
                    current_interest=interest,
                    current_fees=fees,
                    total_balance=total,
                    date_placed=placed,
                )
                session.add(account)

            # --- Standard report templates for Acme tenant
            report_defs = get_standard_report_definitions()
            report_count = 0
            for rdef in report_defs:
                entity_val = rdef.get("source_entity", "accounts")
                try:
                    entity_enum = ReportEntity(entity_val)
                except ValueError:
                    continue

                report_type_val = rdef.get("report_type", "tabular")
                try:
                    report_type_enum = ReportType(report_type_val)
                except ValueError:
                    report_type_enum = ReportType.TABULAR

                cols = rdef.get("columns", [])
                group_by = rdef.get("group_by", [])
                aggregations = []
                non_agg_cols = []
                for c in cols:
                    if "aggregate" in c:
                        aggregations.append({
                            "field": c["field"],
                            "function": c["aggregate"],
                            "label": c.get("label", c["field"]),
                        })
                    else:
                        non_agg_cols.append(c)

                filters = []
                for f in rdef.get("filters", []):
                    filters.append({
                        "field": f["field"],
                        "op": f.get("operator", f.get("op", "eq")),
                        "value": f.get("value"),
                    })

                sort_order = []
                for s in rdef.get("sort", []):
                    sort_order.append({
                        "field": s["field"],
                        "direction": s.get("direction", "asc"),
                    })

                tmpl = ReportTemplate(
                    id=uuid.uuid4(),
                    tenant_id=acme_tenant_id,
                    name=rdef["name"],
                    description=rdef.get("description"),
                    report_type=report_type_enum,
                    entity=entity_enum,
                    columns=non_agg_cols if group_by else cols,
                    filters=filters,
                    grouping=group_by,
                    aggregations=aggregations,
                    sort_order=sort_order,
                    parameters=rdef.get("parameters", []),
                    default_output_format=OutputFormat.CSV,
                    allowed_output_formats=["csv", "xlsx", "json"],
                    is_system=True,
                    is_active=True,
                    created_by=acme_owner_id,
                )
                session.add(tmpl)
                report_count += 1

            await session.flush()

            await session.commit()

            print("\n=== Seed complete ===\n")
            print(f"Standard report templates: {report_count}")
            print(f"Master tenant: id={master_tenant_id} slug=master name={master_tenant.name}")
            print(f"Acme tenant:   id={acme_tenant_id} slug=acme name={acme_tenant.name}")
            print(
                f"Master admin user: id={master_admin_id} email={master_admin.email} "
                f"(is_owner={master_admin.is_owner}, is_master={master_admin.is_master})"
            )
            print(
                f"Acme owner:        id={acme_owner_id} email={acme_owner.email} "
                f"(is_owner={acme_owner.is_owner})"
            )
            print(f"Acme collector:    id={acme_collector_id} email={acme_collector.email}")
            print(f"Acme roles: Admin id={admin_role_id}, Collector id={collector_role_id}, "
                  f"Supervisor id={supervisor_role_id}")
            print(f"Master role (platform): id={master_role_id}")
            for i, cid in enumerate(consumer_ids):
                print(f"Consumer {i + 1}: id={cid}")
            for i, aid in enumerate(account_ids):
                print(f"Account {i + 1}: id={aid} ref={accounts_spec[i]['ref']}")

    except Exception as exc:
        print("Seed failed:", str(exc), file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1) from exc
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
