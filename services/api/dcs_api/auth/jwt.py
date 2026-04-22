"""JWT token handling.

Supports two kinds of access tokens:

- "regular" tokens — minted by /auth/login or /auth/sso/callback. The
  `tenant_id` claim is the user's home tenant. For master users
  (`is_master=true`), this token grants access ONLY to the master control
  plane (/api/v1/master/*); it does NOT grant access to any tenant's
  operational data.

- "impersonation" tokens — minted by POST /api/v1/master/impersonate/{slug}.
  The `tenant_id` claim is the IMPERSONATED tenant (so existing
  tenant-scoped queries continue to filter correctly), and additional
  claims record that this is a master acting on behalf of a tenant:

      acting_as_master:  true
      acting_can_write:  bool   (read-only by default)
      master_user_id:    <id of the master user>
      master_tenant_id:  <id of the master tenant>
      impersonation_id:  <uuid> (joins audit logs to a single session)

  Refresh of an impersonation token is intentionally NOT supported — the
  master must re-enter the tenant when it expires (forces a re-audit).
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from pydantic import BaseModel

from dcs_api.config import get_settings

settings = get_settings()

# Impersonation tokens are intentionally short-lived. The master user
# must explicitly re-enter the tenant after this expires.
IMPERSONATION_TOKEN_MINUTES = 30


class TokenData(BaseModel):
    """Token payload data."""

    sub: str  # User ID
    tenant_id: str
    email: str
    roles: list[str]
    permissions: list[str]
    is_owner: bool = False
    is_master: bool = False
    acting_as_master: bool = False
    acting_can_write: bool = False
    master_user_id: str | None = None
    master_tenant_id: str | None = None
    impersonation_id: str | None = None
    exp: datetime
    iat: datetime
    jti: str  # Token ID for revocation


def create_access_token(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    email: str,
    roles: list[str],
    permissions: list[str],
    is_owner: bool = False,
    is_master: bool = False,
) -> str:
    """Create a regular (non-impersonation) access token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "email": email,
        "roles": roles,
        "permissions": permissions,
        "is_owner": is_owner,
        "is_master": is_master,
        "acting_as_master": False,
        "acting_can_write": False,
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "type": "access",
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_impersonation_token(
    *,
    master_user_id: uuid.UUID,
    master_tenant_id: uuid.UUID,
    target_tenant_id: uuid.UUID,
    email: str,
    impersonation_id: uuid.UUID,
    can_write: bool = False,
    minutes: int = IMPERSONATION_TOKEN_MINUTES,
) -> str:
    """Create an impersonation access token.

    The token's `tenant_id` claim is the *target* tenant (so existing
    tenant-scoped routers transparently scope to it). `is_master` stays
    true so the user keeps cross-tenant abilities, but `acting_as_master`
    is set so guards know we've explicitly entered a tenant.

    Permissions are intentionally NOT copied from the master user's
    operational role. During impersonation, the master is acting as a
    surrogate for the tenant — read access is broad, write access is
    gated by `acting_can_write` and the per-method write-guard middleware.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=minutes)

    payload = {
        "sub": str(master_user_id),
        "tenant_id": str(target_tenant_id),
        "email": email,
        "roles": ["master_impersonator"],
        # Owner-equivalent permissions inside the impersonated tenant; the
        # write-guard middleware further restricts mutations when can_write=false.
        "permissions": [],
        "is_owner": True,
        "is_master": True,
        "acting_as_master": True,
        "acting_can_write": bool(can_write),
        "master_user_id": str(master_user_id),
        "master_tenant_id": str(master_tenant_id),
        "impersonation_id": str(impersonation_id),
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "type": "access",
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    """Create a new refresh token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)

    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "type": "refresh",
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None
