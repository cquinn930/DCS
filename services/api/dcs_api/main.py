"""DCS API - Main application entry point.

Non-legal guidance: This software assists with debt collection compliance
but does not guarantee compliance. Consult legal counsel.
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from dcs_api.auth.rbac import require_operational_scope
from dcs_api.config import get_settings
from dcs_api.database import engine
from dcs_api.routers import (
    accounts,
    audit_trail,
    auth,
    automation,
    batch_letters,
    calculations,
    cases,
    client_portal,
    compliance,
    conditions,
    consumers,
    costs,
    courts,
    credit_reporting,
    dashboard,
    demographics,
    disputes,
    doc_drafts,
    documents,
    edi,
    exports,
    fees,
    flash_messages,
    health,
    imports,
    intake,
    integrations,
    judgments,
    litigation,
    masking,
    master,
    notices,
    payment_plans,
    payments,
    performance,
    printing,
    remittance,
    reports,
    reviews,
    safeguards,
    scanning,
    scripting,
    skip_trace,
    subplans,
    tags,
    telephony,
    tenants,
    trends,
    trust,
    users,
    waterfall,
    workflow,
)

settings = get_settings()


class ImpersonationWriteGuardMiddleware(BaseHTTPMiddleware):
    """Block mutating requests during read-only impersonation.

    Decoded outside the FastAPI dependency graph so we can short-circuit
    BEFORE the request body is read or any DB work is done. The actual
    permission model lives in `require_operational_scope` /
    `require_operational_write`; this middleware is a coarse-grained
    safety net for write operations during read-only sessions.
    """

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    # Even during a read-only impersonation, the master must be able to end it.
    EXEMPT_PATH_PREFIXES = ("/api/v1/master/exit-impersonation",)

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        if request.method in self.SAFE_METHODS:
            return await call_next(request)
        if any(request.url.path.startswith(p) for p in self.EXEMPT_PATH_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return await call_next(request)

        token = auth_header[7:].strip()
        from dcs_api.auth.jwt import decode_token

        payload = decode_token(token)
        if not payload:
            return await call_next(request)  # let the auth dep produce a clean 401

        if payload.get("acting_as_master") and not payload.get("acting_can_write"):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "Read-only impersonation: this session cannot perform "
                        "write operations. Re-enter the tenant in 'write' mode "
                        "(POST /api/v1/master/impersonate/{slug} with mode='write')."
                    ),
                    "type": "impersonation_read_only",
                },
            )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter for critical endpoints."""

    def __init__(self, app: Any, requests_per_window: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        import time

        path = request.url.path
        if path in ("/api/v1/auth/login", "/api/v1/auth/refresh") or path.startswith(
            "/api/v1/auth/sso/"
        ):
            client_ip = request.client.host if request.client else "unknown"
            now = time.monotonic()
            key = f"{client_ip}:{request.url.path}"

            hits = self._buckets.setdefault(key, [])
            hits[:] = [t for t in hits if now - t < self.window_seconds]

            login_limit = min(self.requests_per_window, 10)
            if len(hits) >= login_limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please try again later."},
                    headers={"Retry-After": str(self.window_seconds)},
                )
            hits.append(now)

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Debt Collection System API - A compliant, auditable platform for debt collection. "
        "Non-legal guidance: This software does not guarantee compliance."
    ),
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Rate limiting on auth endpoints
app.add_middleware(
    RateLimitMiddleware,
    requests_per_window=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)

# Read-only impersonation guard. Registered AFTER the rate limiter so
# rate limiting still applies to login attempts. Starlette runs middleware
# in reverse-add order, so this fires first on inbound, last on outbound.
app.add_middleware(ImpersonationWriteGuardMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors."""
    # Log the error (would use structlog in production)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": "internal_error",
        },
    )


# ---------------------------------------------------------------------------
# Router registration
#
# Three categories:
#
#   1. Public / always-on routers (health, auth, tenants/users self-mgmt,
#      master control plane). No `require_operational_scope` guard — these
#      need to work whether or not a master has entered a tenant.
#
#   2. Operational routers (everything else). Guarded by
#      `require_operational_scope`, which 403s any master user holding a
#      regular (non-impersonation) token. This is what prevents the
#      "master sees flg's money on the dashboard" bug at the edge,
#      without having to edit ~40 router files individually.
#
# When a master wants to look at a tenant's operational data, they POST
# /api/v1/master/impersonate/{slug} and swap to the impersonation token
# returned. That token has acting_as_master=true, so the guard passes,
# and tenant_id points at the impersonated tenant — so existing
# tenant-scoped queries Just Work and resolve to the right tenant.
# ---------------------------------------------------------------------------

OPERATIONAL_GUARD = [Depends(require_operational_scope)]

# 1. Public / always-on
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["Tenants"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(master.router, prefix="/api/v1/master", tags=["Master"])
# Public intake: MFP scan-to-cloud, telephony provider webhooks, print
# bureau status callbacks. Authenticated per-endpoint via intake tokens
# / signed webhooks, NOT via tenant JWT.
app.include_router(intake.router, prefix="/api/v1/intake", tags=["Intake"])

# 2. Operational (master must impersonate to reach these)
app.include_router(consumers.router, prefix="/api/v1/consumers", tags=["Consumers"], dependencies=OPERATIONAL_GUARD)
app.include_router(accounts.router, prefix="/api/v1/accounts", tags=["Accounts"], dependencies=OPERATIONAL_GUARD)
app.include_router(cases.router, prefix="/api/v1/cases", tags=["Cases"], dependencies=OPERATIONAL_GUARD)
app.include_router(fees.router, prefix="/api/v1/fees", tags=["Fees"], dependencies=OPERATIONAL_GUARD)
app.include_router(litigation.router, prefix="/api/v1/litigation", tags=["Litigation"], dependencies=OPERATIONAL_GUARD)
app.include_router(notices.router, prefix="/api/v1/notices", tags=["Notices"], dependencies=OPERATIONAL_GUARD)
app.include_router(workflow.router, prefix="/api/v1/workflow", tags=["Workflow"], dependencies=OPERATIONAL_GUARD)
app.include_router(disputes.router, prefix="/api/v1/disputes", tags=["Disputes"], dependencies=OPERATIONAL_GUARD)
app.include_router(payments.router, prefix="/api/v1/payments", tags=["Payments"], dependencies=OPERATIONAL_GUARD)
app.include_router(judgments.router, prefix="/api/v1/judgments", tags=["Judgments"], dependencies=OPERATIONAL_GUARD)
app.include_router(calculations.router, prefix="/api/v1/calculations", tags=["Calculations"], dependencies=OPERATIONAL_GUARD)
app.include_router(compliance.router, prefix="/api/v1/compliance", tags=["Compliance"], dependencies=OPERATIONAL_GUARD)
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["Integrations"], dependencies=OPERATIONAL_GUARD)
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"], dependencies=OPERATIONAL_GUARD)
app.include_router(imports.router, prefix="/api/v1/imports", tags=["Imports"], dependencies=OPERATIONAL_GUARD)
app.include_router(exports.router, prefix="/api/v1/exports", tags=["Exports"], dependencies=OPERATIONAL_GUARD)
app.include_router(scripting.router, prefix="/api/v1/scripts", tags=["Scripting"], dependencies=OPERATIONAL_GUARD)
app.include_router(trust.router, prefix="/api/v1/trust", tags=["Trust"], dependencies=OPERATIONAL_GUARD)
app.include_router(waterfall.router, prefix="/api/v1/waterfalls", tags=["Waterfalls"], dependencies=OPERATIONAL_GUARD)
app.include_router(costs.router, prefix="/api/v1/costs", tags=["Costs"], dependencies=OPERATIONAL_GUARD)
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"], dependencies=OPERATIONAL_GUARD)
app.include_router(automation.router, prefix="/api/v1/automation", tags=["Automation"], dependencies=OPERATIONAL_GUARD)
app.include_router(masking.router, prefix="/api/v1/masking", tags=["Masking"], dependencies=OPERATIONAL_GUARD)
app.include_router(credit_reporting.router, prefix="/api/v1/credit-bureau", tags=["Credit bureau"], dependencies=OPERATIONAL_GUARD)
app.include_router(tags.router, prefix="/api/v1/tags", tags=["Tags"], dependencies=OPERATIONAL_GUARD)
app.include_router(performance.router, prefix="/api/v1/performance", tags=["Performance"], dependencies=OPERATIONAL_GUARD)
app.include_router(edi.router, prefix="/api/v1/edi", tags=["EDI"], dependencies=OPERATIONAL_GUARD)
app.include_router(skip_trace.router, prefix="/api/v1/skip-trace", tags=["Skip trace"], dependencies=OPERATIONAL_GUARD)
app.include_router(demographics.router, prefix="/api/v1/demographics", tags=["Demographics"], dependencies=OPERATIONAL_GUARD)
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"], dependencies=OPERATIONAL_GUARD)
app.include_router(remittance.router, prefix="/api/v1/remittance", tags=["Remittance"], dependencies=OPERATIONAL_GUARD)
app.include_router(flash_messages.router, prefix="/api/v1/flash-messages", tags=["Flash messages"], dependencies=OPERATIONAL_GUARD)
app.include_router(reviews.router, prefix="/api/v1/reviews", tags=["Reviews"], dependencies=OPERATIONAL_GUARD)
app.include_router(courts.router, prefix="/api/v1/courts", tags=["Courts"], dependencies=OPERATIONAL_GUARD)
app.include_router(payment_plans.router, prefix="/api/v1/payment-plans", tags=["Payment plans"], dependencies=OPERATIONAL_GUARD)
app.include_router(batch_letters.router, prefix="/api/v1/batch-letters", tags=["Batch letters"], dependencies=OPERATIONAL_GUARD)
app.include_router(subplans.router, prefix="/api/v1/subplans", tags=["SubPlans"], dependencies=OPERATIONAL_GUARD)
app.include_router(audit_trail.router, prefix="/api/v1/audit-trail", tags=["Audit trail"], dependencies=OPERATIONAL_GUARD)
app.include_router(conditions.router, prefix="/api/v1/conditions", tags=["Conditions"], dependencies=OPERATIONAL_GUARD)
app.include_router(trends.router, prefix="/api/v1/trends", tags=["Trends"], dependencies=OPERATIONAL_GUARD)
app.include_router(safeguards.router, prefix="/api/v1/safeguards", tags=["Safeguards"], dependencies=OPERATIONAL_GUARD)
app.include_router(client_portal.router, prefix="/api/v1/client-portal", tags=["Client portal"], dependencies=OPERATIONAL_GUARD)
app.include_router(doc_drafts.router, prefix="/api/v1/doc-drafts", tags=["Document drafts"], dependencies=OPERATIONAL_GUARD)
app.include_router(telephony.router, prefix="/api/v1/telephony", tags=["Telephony"], dependencies=OPERATIONAL_GUARD)
app.include_router(printing.router, prefix="/api/v1/printing", tags=["Print & Mail"], dependencies=OPERATIONAL_GUARD)
app.include_router(scanning.router, prefix="/api/v1/scanning", tags=["Scan & Capture"], dependencies=OPERATIONAL_GUARD)


DCS_SYSTEM_PROMPT = """You are a DCS (Debt Collection System) assistant. You help users create:
- DCS Script code (a safe DSL with PARAM, SET, QUERY, FOR EACH, IF/ELIF/ELSE, FLAG, LOG, RETURN)
- Report templates (JSON with columns, filters, grouping, aggregations for entities: accounts, consumers, payments, disputes, judgments, litigation, audit_logs, users)
- Import/export templates (field mappings with transforms like cents, last_four, date, uppercase)
- Automation rules (event conditions and actions)

Built-in functions: days_since(date), days_until(date), sol_years(jurisdiction), abs(), round(), upper(), lower(), len(), now(), today(), format_currency(cents), min(), max(), str(), int(), float().
Filter operators: eq, neq, gt, gte, lt, lte, in, not_in, like, between, is_null, not_null.
Aggregations: count, sum, avg, min, max.

Always return ready-to-use code or JSON that the user can paste directly into the DCS platform."""


@app.post("/api/v1/ai/assist", tags=["AI"])
async def ai_assist(request: Request) -> dict[str, Any]:
    """AI assistant — uses tenant-configured LLM or returns a fallback."""
    import httpx
    from dcs_api.auth.rbac import get_current_user
    from dcs_api.database import get_session
    from sqlalchemy import select

    body = await request.json()
    prompt = body.get("prompt", "")
    history = body.get("history", [])

    ai_config: dict[str, Any] = {}
    try:
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token:
            from dcs_api.auth.jwt import decode_access_token
            payload = decode_access_token(token)
            tenant_id = payload.get("tenant_id")
            if tenant_id:
                from dcs_api.models.tenant import Tenant
                async for session in get_session():
                    result = await session.execute(
                        select(Tenant).where(Tenant.id == tenant_id)
                    )
                    tenant = result.scalar_one_or_none()
                    if tenant and tenant.settings:
                        ai_config = tenant.settings.get("ai_assistant", {})
                    break
    except Exception:
        pass

    provider = ai_config.get("provider", "")
    api_key = ai_config.get("api_key", "")
    model = ai_config.get("model", "")
    enabled = ai_config.get("enabled", False)

    if not enabled or not api_key:
        return {
            "response": (
                f"[AI not configured]\n\n"
                f"Your request: \"{prompt}\"\n\n"
                f"To enable AI-powered generation, go to Settings → AI Assistant "
                f"and configure your provider, model, and API key.\n\n"
                f"In the meantime, use the Help & Docs tabs for reference guides "
                f"and code examples."
            ),
            "model": "placeholder",
            "connected": False,
        }

    system_prompt = ai_config.get("system_prompt") or DCS_SYSTEM_PROMPT
    temperature = ai_config.get("temperature", 0.3)
    max_tokens = ai_config.get("max_tokens", 2048)

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-10:]:
        if isinstance(msg, dict) and msg.get("role") in ("user", "assistant"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if provider in ("openai", "azure_openai"):
                endpoint = ai_config.get("api_endpoint") or "https://api.openai.com"
                url = f"{endpoint.rstrip('/')}/v1/chat/completions"
                if provider == "azure_openai":
                    url = f"{endpoint.rstrip('/')}/openai/deployments/{model}/chat/completions?api-version=2024-02-01"

                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                if provider == "azure_openai":
                    headers = {"api-key": api_key, "Content-Type": "application/json"}

                resp = await client.post(url, headers=headers, json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                })
                resp.raise_for_status()
                data = resp.json()
                return {
                    "response": data["choices"][0]["message"]["content"],
                    "model": model,
                    "connected": True,
                }

            elif provider == "anthropic":
                endpoint = ai_config.get("api_endpoint") or "https://api.anthropic.com"
                resp = await client.post(
                    f"{endpoint.rstrip('/')}/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": max_tokens,
                        "system": system_prompt,
                        "messages": [m for m in messages if m["role"] != "system"],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = "".join(b.get("text", "") for b in data.get("content", []))
                return {
                    "response": text,
                    "model": model,
                    "connected": True,
                }

            elif provider == "local":
                endpoint = ai_config.get("api_endpoint", "http://localhost:11434")
                resp = await client.post(
                    f"{endpoint.rstrip('/')}/v1/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "response": data["choices"][0]["message"]["content"],
                    "model": model,
                    "connected": True,
                }

    except httpx.HTTPStatusError as e:
        return {
            "response": f"AI provider returned an error (HTTP {e.response.status_code}).\n\nCheck your API key and model settings in Settings → AI Assistant.",
            "model": model,
            "connected": False,
        }
    except Exception as e:
        return {
            "response": f"Failed to reach AI provider: {str(e)}\n\nCheck your endpoint and network settings.",
            "model": model,
            "connected": False,
        }

    return {
        "response": f"Unknown provider: {provider}",
        "model": "unknown",
        "connected": False,
    }


@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "operational",
        "disclaimer": "Non-legal guidance: This software does not guarantee compliance.",
    }
