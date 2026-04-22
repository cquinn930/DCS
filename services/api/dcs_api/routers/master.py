"""Master control plane.

Endpoints under /api/v1/master/* are reachable ONLY by master users
(`is_master=true`) holding a *regular* (non-impersonation) token. They
deal exclusively in metadata about the platform — tenants, system health,
audit logs, impersonation lifecycle — and never read or write a tenant's
operational data.

To touch a tenant's operational data, a master must POST
/master/impersonate/{slug}, swap to the returned impersonation token,
and use the regular tenant-scoped APIs. The impersonation token's
`tenant_id` claim *is* the target tenant, so existing routers
transparently scope to it. Every entry, exit, and (in Phase 2) every
write performed during impersonation is recorded in `audit_logs` with
the master's identity and a session-wide `impersonation_id`.
"""

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.jwt import IMPERSONATION_TOKEN_MINUTES, create_impersonation_token
from dcs_api.auth.rbac import CurrentUser, get_current_user, require_master
from dcs_api.config import get_settings
from dcs_api.database import get_session
from dcs_api.models.tenant import (
    AuditAction,
    AuditLog,
    Tenant,
    TenantStatus,
    User,
)

settings = get_settings()

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SystemStatus(BaseModel):
    """Lightweight platform-health snapshot for the master console."""

    api_version: str
    api_uptime_seconds: int
    database_ok: bool
    database_latency_ms: float | None
    tenant_count: int
    active_tenant_count: int
    master_user_count: int
    impersonations_active_now: int
    impersonations_last_24h: int
    server_time_utc: datetime


class TenantSummary(BaseModel):
    """Tenant row for the master tenant list. Metadata only — no money."""

    id: uuid.UUID
    slug: str
    name: str
    status: TenantStatus
    business_model: str
    default_jurisdiction: str
    user_count: int
    last_user_login: datetime | None
    auto_approve_master_access: bool
    created_at: datetime


class ImpersonateRequest(BaseModel):
    reason: str = Field(min_length=4, max_length=500)
    mode: Literal["read", "write"] = "read"


class ImpersonateResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    impersonation_id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_slug: str
    mode: Literal["read", "write"]


class ImpersonationAuditEntry(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    event: str  # impersonation.start | impersonation.end | master.login
    master_email: str | None
    target_tenant_slug: str | None
    mode: str | None
    reason: str | None
    impersonation_id: uuid.UUID | None
    ip_address: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Process start time, captured at module import. Good enough for a
# "this API process has been up for X seconds" indicator on the dash.
_API_PROCESS_START = time.monotonic()


def _client_ip(request: Request) -> str | None:
    if not request.client:
        return None
    # Honor common reverse-proxy headers first
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host


def _ua(request: Request) -> str | None:
    return request.headers.get("user-agent")


async def _write_audit(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    master_user_id: uuid.UUID,
    event: str,
    description: str,
    extra: dict[str, Any],
    ip: str | None,
    user_agent: str | None,
) -> AuditLog:
    """Insert an audit-log row for a master/impersonation event.

    Phase 1 stores the event-type discriminator in `new_values.event` so
    we don't need an Alembic migration to add new AuditAction enum
    values. Phase 2 will introduce dedicated AuditAction values
    (MASTER_LOGIN, IMPERSONATION_START, IMPERSONATION_END) and a backfill.
    """
    row = AuditLog(
        tenant_id=tenant_id,
        user_id=master_user_id,
        # Best fit available without a schema change:
        action=AuditAction.LOGIN if event != "impersonation.end" else AuditAction.LOGOUT,
        description=description,
        ip_address=ip,
        user_agent=user_agent,
        new_values={"event": event, **extra},
    )
    session.add(row)
    await session.flush()
    return row


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/system-status", response_model=SystemStatus)
async def system_status(
    session: Annotated[AsyncSession, Depends(get_session)],
    _master: Annotated[CurrentUser, Depends(require_master)],
) -> SystemStatus:
    """Platform-level health and counts for the master dashboard."""

    db_ok = True
    db_latency_ms: float | None = None
    try:
        t0 = time.perf_counter()
        await session.execute(select(func.now()))
        db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    except Exception:
        db_ok = False

    tenant_count = (await session.execute(select(func.count(Tenant.id)))).scalar_one()
    active_tenant_count = (
        await session.execute(
            select(func.count(Tenant.id)).where(Tenant.status == TenantStatus.ACTIVE)
        )
    ).scalar_one()
    master_user_count = (
        await session.execute(select(func.count(User.id)).where(User.is_master.is_(True)))
    ).scalar_one()

    # Impersonation counts. Active = "started in last IMPERSONATION_TOKEN_MINUTES" —
    # approximate (we don't track per-session expiry yet). Good enough for a dashboard.
    now = datetime.now(timezone.utc)
    cutoff_active = now - timedelta(minutes=IMPERSONATION_TOKEN_MINUTES)
    cutoff_24h = now - timedelta(hours=24)

    impersonations_active_now = (
        await session.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == AuditAction.LOGIN,
                AuditLog.new_values["event"].astext == "impersonation.start",
                AuditLog.created_at >= cutoff_active,
            )
        )
    ).scalar_one()
    impersonations_last_24h = (
        await session.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == AuditAction.LOGIN,
                AuditLog.new_values["event"].astext == "impersonation.start",
                AuditLog.created_at >= cutoff_24h,
            )
        )
    ).scalar_one()

    return SystemStatus(
        api_version=settings.app_version,
        api_uptime_seconds=int(time.monotonic() - _API_PROCESS_START),
        database_ok=db_ok,
        database_latency_ms=db_latency_ms,
        tenant_count=int(tenant_count or 0),
        active_tenant_count=int(active_tenant_count or 0),
        master_user_count=int(master_user_count or 0),
        impersonations_active_now=int(impersonations_active_now or 0),
        impersonations_last_24h=int(impersonations_last_24h or 0),
        server_time_utc=datetime.now(timezone.utc),
    )


@router.get("/tenants", response_model=list[TenantSummary])
async def list_tenants(
    session: Annotated[AsyncSession, Depends(get_session)],
    master: Annotated[CurrentUser, Depends(require_master)],
) -> list[TenantSummary]:
    """All tenants on the platform — metadata only.

    Excludes the master's own tenant from the list (they're already in it).
    """
    user_count_sub = (
        select(User.tenant_id, func.count(User.id).label("uc"), func.max(User.last_login).label("ll"))
        .group_by(User.tenant_id)
        .subquery()
    )

    rows = (
        await session.execute(
            select(Tenant, user_count_sub.c.uc, user_count_sub.c.ll)
            .outerjoin(user_count_sub, user_count_sub.c.tenant_id == Tenant.id)
            .where(Tenant.id != master.tenant_id)
            .order_by(Tenant.slug)
        )
    ).all()

    out: list[TenantSummary] = []
    for tenant, user_count, last_login in rows:
        master_settings = (tenant.settings or {}).get("master_access", {})
        out.append(
            TenantSummary(
                id=tenant.id,
                slug=tenant.slug,
                name=tenant.name,
                status=tenant.status,
                business_model=str(tenant.business_model.value if hasattr(tenant.business_model, "value") else tenant.business_model),
                default_jurisdiction=tenant.default_jurisdiction,
                user_count=int(user_count or 0),
                last_user_login=last_login,
                auto_approve_master_access=bool(master_settings.get("auto_approve", True)),
                created_at=tenant.created_at,
            )
        )
    return out


@router.post(
    "/impersonate/{tenant_slug}",
    response_model=ImpersonateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def impersonate(
    tenant_slug: str,
    body: ImpersonateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    master: Annotated[CurrentUser, Depends(require_master)],
) -> ImpersonateResponse:
    """Begin an impersonation session against `tenant_slug`.

    Returns a short-lived access token whose `tenant_id` claim is the
    target tenant. The caller swaps tokens client-side; subsequent
    requests to operational endpoints scope to the target tenant.
    """
    if tenant_slug == "master":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot impersonate the master tenant",
        )

    target = (
        await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    if target.id == master.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot impersonate your own tenant",
        )
    if target.status not in (TenantStatus.ACTIVE, TenantStatus.SUSPENDED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot impersonate tenant in {target.status.value} state",
        )

    # Per-tenant master-access policy. Defaults to auto-approve since the
    # current master is internal-only; tenant owners can flip this off
    # to require an out-of-band approval flow (Phase 2).
    master_policy = (target.settings or {}).get("master_access", {})
    auto_approve = bool(master_policy.get("auto_approve", True))
    allow_write = bool(master_policy.get("allow_write", True))

    if not auto_approve:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Tenant requires explicit owner approval for master access. "
                "Approval flow not yet implemented (Phase 2)."
            ),
        )

    if body.mode == "write" and not allow_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant policy disallows write impersonation",
        )

    impersonation_id = uuid.uuid4()

    token = create_impersonation_token(
        master_user_id=master.user_id,
        master_tenant_id=master.tenant_id,
        target_tenant_id=target.id,
        email=master.email,
        impersonation_id=impersonation_id,
        can_write=(body.mode == "write"),
    )

    await _write_audit(
        session,
        tenant_id=target.id,
        master_user_id=master.user_id,
        event="impersonation.start",
        description=(
            f"Master {master.email} entered tenant {target.slug} "
            f"({body.mode}-only): {body.reason}"
        ),
        extra={
            "impersonation_id": str(impersonation_id),
            "master_email": master.email,
            "master_user_id": str(master.user_id),
            "master_tenant_id": str(master.tenant_id),
            "target_tenant_id": str(target.id),
            "target_tenant_slug": target.slug,
            "mode": body.mode,
            "reason": body.reason,
        },
        ip=_client_ip(request),
        user_agent=_ua(request),
    )

    return ImpersonateResponse(
        access_token=token,
        expires_in_seconds=IMPERSONATION_TOKEN_MINUTES * 60,
        impersonation_id=impersonation_id,
        tenant_id=target.id,
        tenant_slug=target.slug,
        mode=body.mode,
    )


@router.post("/exit-impersonation", status_code=status.HTTP_204_NO_CONTENT)
async def exit_impersonation(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> None:
    """End the current impersonation session.

    Accepts EITHER a master token (records a no-op end event for
    consistency) OR an impersonation token (the typical case). The
    client is responsible for discarding the impersonation token
    after this call and reverting to its stored master token.
    """
    if not user.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master account required",
        )

    target_tenant_id: uuid.UUID | None = user.tenant_id if user.acting_as_master else None
    target_slug: str | None = None
    if target_tenant_id:
        target = (
            await session.execute(select(Tenant).where(Tenant.id == target_tenant_id))
        ).scalar_one_or_none()
        target_slug = target.slug if target else None

    master_user_id = user.master_user_id or user.user_id

    await _write_audit(
        session,
        tenant_id=target_tenant_id,
        master_user_id=master_user_id,
        event="impersonation.end",
        description=(
            f"Master {user.email} exited tenant {target_slug or '(none)'}"
            if user.acting_as_master
            else f"Master {user.email} called exit-impersonation with no active token"
        ),
        extra={
            "impersonation_id": str(user.impersonation_id) if user.impersonation_id else None,
            "master_email": user.email,
            "master_user_id": str(master_user_id),
            "target_tenant_id": str(target_tenant_id) if target_tenant_id else None,
            "target_tenant_slug": target_slug,
        },
        ip=_client_ip(request),
        user_agent=_ua(request),
    )


@router.get("/audit", response_model=list[ImpersonationAuditEntry])
async def list_master_audit(
    session: Annotated[AsyncSession, Depends(get_session)],
    _master: Annotated[CurrentUser, Depends(require_master)],
    limit: int = 100,
    tenant_slug: str | None = None,
) -> list[ImpersonationAuditEntry]:
    """Recent master/impersonation events across all tenants."""
    limit = max(1, min(limit, 500))

    q = (
        select(AuditLog, Tenant.slug)
        .outerjoin(Tenant, Tenant.id == AuditLog.tenant_id)
        .where(
            AuditLog.new_values["event"].astext.in_(
                ("impersonation.start", "impersonation.end", "master.login")
            )
        )
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    if tenant_slug:
        q = q.where(Tenant.slug == tenant_slug)

    rows = (await session.execute(q)).all()

    out: list[ImpersonationAuditEntry] = []
    for log, slug in rows:
        nv = log.new_values or {}
        imp_id_raw = nv.get("impersonation_id")
        imp_id: uuid.UUID | None = None
        if imp_id_raw:
            try:
                imp_id = uuid.UUID(imp_id_raw)
            except (ValueError, TypeError):
                imp_id = None
        out.append(
            ImpersonationAuditEntry(
                id=log.id,
                occurred_at=log.created_at,
                event=str(nv.get("event") or log.action.value),
                master_email=nv.get("master_email"),
                target_tenant_slug=slug or nv.get("target_tenant_slug"),
                mode=nv.get("mode"),
                reason=nv.get("reason"),
                impersonation_id=imp_id,
                ip_address=log.ip_address,
            )
        )
    return out
