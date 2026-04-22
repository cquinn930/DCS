"""Authentication endpoints."""

import base64
import binascii
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import quote, urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.jwt import create_access_token, create_refresh_token, decode_token
from dcs_api.auth.oidc import (
    build_authorization_url,
    discover_oidc,
    email_domain_allowed,
    exchange_code,
    get_tenant_oidc_config,
    provision_or_update_user,
    resolve_oidc_user_claims,
)
from dcs_api.auth.password import verify_password
from dcs_api.auth.rbac import get_user_permissions, get_user_roles
from dcs_api.config import get_settings
from dcs_api.database import get_session
from dcs_api.models.tenant import AuditAction, AuditLog, Tenant, User
from dcs_api.schemas.auth import LoginRequest, LoginResponse, RefreshRequest, TokenResponse

router = APIRouter()
settings = get_settings()


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    credentials: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LoginResponse:
    """Authenticate user and return tokens."""
    # Find user by email
    query = select(User).where(User.email == credentials.email)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        # Log failed attempt (user not found)
        await _log_failed_login(session, None, credentials.email, request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Check if user is active
    if not user.is_active:
        await _log_failed_login(session, user.id, credentials.email, request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
        )

    # Check if locked
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is temporarily locked",
        )

    # Verify password
    if not user.password_hash or not verify_password(credentials.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
        await _log_failed_login(session, user.id, credentials.email, request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Successful login - reset failed attempts
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(timezone.utc)

    # Get roles and permissions
    roles = await get_user_roles(session, user.id)
    permissions = await get_user_permissions(session, user.id)

    # Create tokens
    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        roles=roles,
        permissions=list(permissions),
        is_owner=user.is_owner,
        is_master=user.is_master,
    )
    refresh_token = create_refresh_token(user.id, user.tenant_id)

    # Log successful login
    audit = AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action=AuditAction.LOGIN,
        entity_type="user",
        entity_id=user.id,
        description=f"User {user.email} logged in",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    session.add(audit)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    """Refresh access token using refresh token."""
    payload = decode_token(request.refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Get user
    user_id = payload["sub"]
    query = select(User).where(User.id == user_id)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Get roles and permissions
    roles = await get_user_roles(session, user.id)
    permissions = await get_user_permissions(session, user.id)

    # Create new access token
    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        roles=roles,
        permissions=list(permissions),
        is_owner=user.is_owner,
        is_master=user.is_master,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


def _decode_sso_state(state: str) -> dict:
    try:
        pad = "=" * (-len(state) % 4)
        raw = base64.urlsafe_b64decode(state + pad)
        return json.loads(raw.decode())
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter",
        ) from e


def _validate_post_login_url(url: str | None, allowed_bases: list[str]) -> str | None:
    if not url:
        return None
    for base in allowed_bases:
        if url == base or url.startswith(base + "/") or url.startswith(base + "?"):
            return url
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Redirect URL is not allowed",
    )


@router.get("/sso/{tenant_slug}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
async def sso_start(
    tenant_slug: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    next: str | None = Query(None, alias="next"),
) -> RedirectResponse:
    result = await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    config = await get_tenant_oidc_config(session, tenant.id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO is not configured for this tenant",
        )

    next_ok = _validate_post_login_url(next, settings.cors_origins)
    payload: dict = {
        "tenant_id": str(tenant.id),
        "nonce": secrets.token_hex(16),
    }
    if next_ok:
        payload["next"] = next_ok
    state = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    state = state.rstrip("=")

    discovery = await discover_oidc(config.issuer)
    location = build_authorization_url(config, discovery, state)
    return RedirectResponse(url=location, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/sso/callback", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
async def sso_callback(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    code: str | None = Query(None),
    state: str | None = Query(None),
) -> RedirectResponse:
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing code or state",
        )

    decoded = _decode_sso_state(state)
    try:
        tenant_id = UUID(decoded["tenant_id"])
    except (KeyError, ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state payload",
        ) from e

    config = await get_tenant_oidc_config(session, tenant_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO is not configured for this tenant",
        )

    discovery = await discover_oidc(config.issuer)
    tokens = await exchange_code(config, code, discovery)
    userinfo = await resolve_oidc_user_claims(tokens, discovery)

    email = userinfo.get("email")
    if isinstance(email, str) and not email_domain_allowed(
        email.strip().lower(),
        config.allowed_domains,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email domain is not allowed for this organization",
        )

    issuer = urlparse(str(config.issuer))
    idp_provider = issuer.netloc or "oidc"

    user = await provision_or_update_user(session, tenant_id, userinfo, idp_provider)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is temporarily locked",
        )

    roles = await get_user_roles(session, user.id)
    permissions = await get_user_permissions(session, user.id)

    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        roles=roles,
        permissions=list(permissions),
        is_owner=user.is_owner,
        is_master=user.is_master,
    )
    refresh_token = create_refresh_token(user.id, user.tenant_id)
    expires_in = settings.jwt_access_token_expire_minutes * 60

    audit = AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action=AuditAction.LOGIN,
        entity_type="user",
        entity_id=user.id,
        description=f"User {user.email} logged in via SSO",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    session.add(audit)

    next_raw = decoded.get("next")
    next_url = _validate_post_login_url(next_raw, settings.cors_origins) if next_raw else None
    base = next_url or (settings.cors_origins[0] if settings.cors_origins else "http://localhost:3000")
    sep = "&" if "?" in base else "?"
    target = (
        f"{base}{sep}access_token={quote(access_token)}"
        f"&refresh_token={quote(refresh_token)}&expires_in={expires_in}"
    )
    return RedirectResponse(url=target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


async def _log_failed_login(
    session: AsyncSession,
    user_id: str | None,
    email: str,
    request: Request,
) -> None:
    """Log a failed login attempt."""
    audit = AuditLog(
        tenant_id=None,
        user_id=user_id,
        action=AuditAction.LOGIN_FAILED,
        entity_type="user",
        description=f"Failed login attempt for {email}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    session.add(audit)
