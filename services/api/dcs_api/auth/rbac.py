"""Role-Based Access Control (RBAC) implementation.

Implements the permission matrix from 05_rbac.md with the following roles:
- Collector: Manage assigned cases, contacts, payments, disputes
- Supervisor: All collector permissions plus assignment and escalation
- Legal: Review disputes, litigation actions, notices
- Admin: Manage users, roles, integrations, configurations
- Owner: Full tenant control including retention, lockdown, and billing
- Master: Cross-tenant administration (metadata only, no data visibility)

Non-legal guidance: RBAC configuration should be reviewed by legal counsel.
"""

import uuid
from functools import wraps
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dcs_api.auth.jwt import decode_token
from dcs_api.database import get_session
from dcs_api.models.tenant import Permission, Role, RolePermission, User, UserRole

security = HTTPBearer()


class CurrentUser:
    """Current authenticated user context.

    For master users, three states are possible:

    - is_master=True, acting_as_master=False:
        Master is logged in but has not entered any tenant. Only the
        master control plane (/api/v1/master/*) and a small set of
        always-allowed endpoints (auth, health, tenant metadata) are
        accessible. Operational endpoints return 403.

    - is_master=True, acting_as_master=True, acting_can_write=False:
        Master has entered a tenant in read-only mode. Tenant-scoped
        queries work and resolve to the impersonated tenant. The
        write-guard middleware rejects non-GET requests.

    - is_master=True, acting_as_master=True, acting_can_write=True:
        Same as above but writes are permitted; every mutation is
        audited with master_user_id + impersonation_id.
    """

    def __init__(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        email: str,
        roles: list[str],
        permissions: set[str],
        is_owner: bool = False,
        is_master: bool = False,
        acting_as_master: bool = False,
        acting_can_write: bool = False,
        master_user_id: uuid.UUID | None = None,
        master_tenant_id: uuid.UUID | None = None,
        impersonation_id: uuid.UUID | None = None,
    ):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.email = email
        self.roles = roles
        self.permissions = permissions
        self.is_owner = is_owner
        self.is_master = is_master
        self.acting_as_master = acting_as_master
        self.acting_can_write = acting_can_write
        self.master_user_id = master_user_id
        self.master_tenant_id = master_tenant_id
        self.impersonation_id = impersonation_id

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions or self.is_owner

    def has_any_permission(self, permissions: list[str]) -> bool:
        """Check if user has any of the given permissions."""
        return any(self.has_permission(p) for p in permissions) or self.is_owner

    def has_all_permissions(self, permissions: list[str]) -> bool:
        """Check if user has all of the given permissions."""
        return all(self.has_permission(p) for p in permissions) or self.is_owner

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles


def _opt_uuid(payload: dict, key: str) -> uuid.UUID | None:
    val = payload.get(key)
    if not val:
        return None
    try:
        return uuid.UUID(val)
    except (ValueError, TypeError):
        return None


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CurrentUser:
    """Get the current authenticated user from the JWT token."""
    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # Verify user still exists and is active
    user_id = uuid.UUID(payload["sub"])
    query = select(User).where(User.id == user_id)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    acting_as_master = bool(payload.get("acting_as_master"))

    # For regular tokens, the user's home tenant must match the token's
    # tenant_id. For impersonation tokens, the token's tenant_id is the
    # *target* tenant (intentionally different from the master user's
    # home tenant), and we instead validate against master_tenant_id.
    if acting_as_master:
        master_tenant_str = payload.get("master_tenant_id")
        if not master_tenant_str or str(user.tenant_id) != master_tenant_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Impersonation token home-tenant mismatch",
            )
    else:
        if str(user.tenant_id) != payload.get("tenant_id"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token tenant mismatch",
            )

    return CurrentUser(
        user_id=user_id,
        tenant_id=uuid.UUID(payload["tenant_id"]),
        email=payload["email"],
        roles=payload.get("roles", []),
        permissions=set(payload.get("permissions", [])),
        is_owner=payload.get("is_owner", False),
        is_master=payload.get("is_master", False),
        acting_as_master=acting_as_master,
        acting_can_write=bool(payload.get("acting_can_write")),
        master_user_id=_opt_uuid(payload, "master_user_id"),
        master_tenant_id=_opt_uuid(payload, "master_tenant_id"),
        impersonation_id=_opt_uuid(payload, "impersonation_id"),
    )


async def require_operational_scope(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Block master users who have not entered a tenant.

    Applied via include_router(dependencies=[...]) in main.py to every
    operational router. Master users see 403 unless they explicitly
    POST /api/v1/master/impersonate/{slug} first.
    """
    if user.is_master and not user.acting_as_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Master account must enter a tenant to access operational "
                "endpoints. POST /api/v1/master/impersonate/{tenant_slug} first."
            ),
        )
    return user


async def require_master(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Master control-plane only. Rejects impersonation tokens."""
    if not user.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master account required",
        )
    if user.acting_as_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exit impersonation before using the master control plane",
        )
    return user


def require_permission(permission: str) -> Callable:
    """Dependency that requires a specific permission."""

    async def check(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission} required",
            )
        return user

    return check


def require_role(role: str) -> Callable:
    """Dependency that requires a specific role."""

    async def check(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if not user.has_role(role) and not user.is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role denied: {role} required",
            )
        return user

    return check


def check_permission(user: CurrentUser, permission: str) -> None:
    """Check if user has permission, raise if not."""
    if not user.has_permission(permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission} required",
        )


# Permission constants based on 05_rbac.md
class Permissions:
    """Permission code constants."""

    # Account permissions
    VIEW_ASSIGNED_ACCOUNTS = "accounts:view_assigned"
    VIEW_ALL_ACCOUNTS = "accounts:view_all"
    EDIT_ACCOUNT_CONTACT = "accounts:edit_contact"
    EDIT_BALANCES_FEES = "accounts:edit_balances"

    # Contact permissions
    CREATE_OUTBOUND_CONTACT = "contacts:create"
    OVERRIDE_SUPPRESSION = "contacts:override_suppression"

    # Dispute permissions
    MANAGE_DISPUTES = "disputes:manage"
    APPROVE_DISPUTE_RESOLUTION = "disputes:approve_resolution"

    # Litigation permissions
    CREATE_LITIGATION = "litigation:create"
    APPROVE_LITIGATION_FILINGS = "litigation:approve_filings"

    # User management
    MANAGE_USERS = "users:manage"
    CREATE_CUSTOM_ROLES = "roles:create"
    ASSIGN_OWNER_PERMISSIONS = "roles:assign_owner"

    # Configuration
    CONFIGURE_INTEGRATIONS = "integrations:configure"
    CONFIGURE_POLICY_PACKS = "policy_packs:configure"
    CONFIGURE_RETENTION = "retention:configure"

    # Security
    LIFT_BREACH_LOCKDOWN = "security:lift_lockdown"
    VIEW_TENANT_METADATA = "tenants:view_metadata"

    # Audit
    VIEW_AUDIT_LOGS = "audit:view"
    EXPORT_AUDIT_LOGS = "audit:export"

    # Workflow & Activities
    MANAGE_WORKFLOW = "workflow:manage"
    MANAGE_ACTIVITIES = "activities:manage"
    MANAGE_QUEUES = "queues:manage"

    # Cases
    MANAGE_CASES = "cases:manage"

    # Notices
    MANAGE_NOTICES = "notices:manage"

    # Trust Accounting
    MANAGE_TRUST = "trust:manage"

    # Payment Waterfall
    MANAGE_WATERFALL = "waterfall:manage"

    # Costs
    MANAGE_COSTS = "costs:manage"

    # Documents
    MANAGE_DOCUMENTS = "documents:manage"

    # Automation
    MANAGE_AUTOMATION = "automation:manage"

    # Data Masking
    MANAGE_MASKING = "masking:manage"

    # Credit Bureau Reporting
    MANAGE_BUREAU = "bureau:manage"

    # Tags
    MANAGE_TAGS = "tags:manage"

    # Performance & Goals
    VIEW_PERFORMANCE = "performance:view"
    MANAGE_PERFORMANCE = "performance:manage"

    # EDI
    MANAGE_EDI = "edi:manage"

    # Skip Tracing
    MANAGE_SKIP_TRACE = "skip_trace:manage"

    # Demographics
    MANAGE_DEMOGRAPHICS = "demographics:manage"

    # Dashboard
    VIEW_DASHBOARD = "dashboard:view"
    MANAGE_DASHBOARD = "dashboard:manage"

    # Litigation (extended)
    MANAGE_LITIGATION = "litigation:manage"

    # Remittance
    MANAGE_REMITTANCE = "remittance:manage"

    # Flash Messages
    MANAGE_FLASH_MESSAGES = "flash_messages:manage"

    # Reviews
    MANAGE_REVIEWS = "reviews:manage"

    # Courts
    MANAGE_COURTS = "courts:manage"

    # Payment Plans
    MANAGE_PAYMENT_PLANS = "payment_plans:manage"

    # Batch Letters
    MANAGE_BATCH_LETTERS = "batch_letters:manage"

    # Safeguards
    MANAGE_SAFEGUARDS = "safeguards:manage"

    # Telephony
    MANAGE_TELEPHONY = "telephony:manage"
    USE_TELEPHONY = "telephony:use"

    # Print & Mail
    MANAGE_PRINTING = "printing:manage"
    USE_PRINTING = "printing:use"

    # Scan & Capture
    MANAGE_SCANNING = "scanning:manage"
    USE_SCANNING = "scanning:use"

    # Checks (point-of-payment scanned checks → trust deposits)
    HANDLE_CHECKS = "checks:handle"


async def get_user_permissions(session: AsyncSession, user_id: uuid.UUID) -> set[str]:
    """Load all permissions for a user based on their roles."""
    query = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    result = await session.execute(query)
    return set(result.scalars().all())


async def get_user_roles(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """Load all roles for a user."""
    query = (
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    result = await session.execute(query)
    return list(result.scalars().all())
