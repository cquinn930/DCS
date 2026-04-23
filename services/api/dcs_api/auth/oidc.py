"""OIDC client and JIT user provisioning."""

import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from jose import jwt as jose_jwt
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.models.tenant import Role, Tenant, User, UserRole


class OIDCConfig(BaseModel):
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str] = Field(
        default_factory=lambda: ["openid", "email", "profile", "groups"],
    )
    allowed_domains: list[str] = Field(default_factory=list)

    # ---- Group / role mapping --------------------------------------------
    # Which JWT/userinfo claim holds the IdP group memberships. Okta
    # defaults to "groups", Azure AD to "roles" or "groups", Auth0 to
    # whichever name the rule emits.
    group_claim: str = "groups"

    # Map of IdP group name -> DCS role name. The DCS role must already
    # exist in the tenant's roles table; unknown role names are skipped
    # with a warning. Example:
    #   {"DCS Owners": "owner", "DCS Collectors": "collector"}
    group_role_map: dict[str, str] = Field(default_factory=dict)

    # Membership in any of these IdP groups grants is_owner=true on the
    # tenant. Useful when you do not want to mirror "owner" through the
    # role table. Comparison is case-sensitive against the values in the
    # IdP claim.
    owner_groups: list[str] = Field(default_factory=list)

    # When True (default), every login resets the user's roles to the
    # set derived from their current IdP groups. Roles assigned manually
    # in DCS that are not represented in the IdP will be REMOVED.
    # Set False to use the IdP groups only as an additive hint and
    # preserve any roles assigned manually in DCS.
    sync_groups_on_login: bool = True


async def get_tenant_oidc_config(session: AsyncSession, tenant_id: uuid.UUID) -> OIDCConfig | None:
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant or not tenant.settings:
        return None
    raw = tenant.settings.get("oidc")
    if not raw or not isinstance(raw, dict):
        return None
    try:
        return OIDCConfig.model_validate(raw)
    except ValidationError:
        return None


async def discover_oidc(issuer: str) -> dict[str, Any]:
    base = issuer.rstrip("/")
    url = f"{base}/.well-known/openid-configuration"
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OIDC discovery failed: HTTP {e.response.status_code}",
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OIDC discovery request failed",
        ) from e
    if not isinstance(data, dict) or "authorization_endpoint" not in data:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid OpenID configuration response",
        )
    return data


async def exchange_code(config: OIDCConfig, code: str, discovery: dict[str, Any]) -> dict[str, Any]:
    token_endpoint = discovery.get("token_endpoint")
    if not token_endpoint:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OIDC discovery missing token_endpoint",
        )
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.redirect_uri,
        "client_id": config.client_id,
        "client_secret": config.client_secret,
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.post(
                token_endpoint,
                data=form,
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPStatusError as e:
        detail = "Token exchange failed"
        try:
            err_body = e.response.json()
            if isinstance(err_body, dict) and "error_description" in err_body:
                detail = str(err_body["error_description"])
            elif isinstance(err_body, dict) and "error" in err_body:
                detail = str(err_body["error"])
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Token exchange request failed",
        ) from e
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid token response",
        )
    return body


async def get_userinfo(access_token: str, discovery: dict[str, Any]) -> dict[str, Any]:
    endpoint = discovery.get("userinfo_endpoint")
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OIDC discovery missing userinfo_endpoint",
        )
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(
                endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Userinfo request failed: HTTP {e.response.status_code}",
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Userinfo request failed",
        ) from e
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid userinfo response",
        )
    return data


async def resolve_oidc_user_claims(
    token_response: dict[str, Any],
    discovery: dict[str, Any],
) -> dict[str, Any]:
    access = token_response.get("access_token")
    if isinstance(access, str) and discovery.get("userinfo_endpoint"):
        try:
            claims = await get_userinfo(access, discovery)
            if claims.get("sub"):
                return claims
        except HTTPException:
            pass
    id_token = token_response.get("id_token")
    if isinstance(id_token, str) and id_token:
        try:
            return jose_jwt.get_unverified_claims(id_token)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not parse id_token",
            ) from e
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Could not obtain OIDC user profile",
    )


def build_authorization_url(config: OIDCConfig, discovery: dict[str, Any], state: str) -> str:
    auth_endpoint = discovery.get("authorization_endpoint")
    if not auth_endpoint:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OIDC discovery missing authorization_endpoint",
        )
    params = {
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": " ".join(config.scopes),
        "state": state,
    }
    sep = "&" if "?" in auth_endpoint else "?"
    return f"{auth_endpoint}{sep}{urlencode(params)}"


def email_domain_allowed(email: str, allowed_domains: list[str]) -> bool:
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[-1].lower()
    allowed = {d.lower().lstrip("@") for d in allowed_domains}
    return domain in allowed


def _extract_groups(userinfo: dict[str, Any], claim_name: str) -> list[str]:
    """Pull the groups list out of an OIDC userinfo / id_token payload.

    Tolerates the common shapes we see in the wild:
      * list[str]:                  ["DCS Admins", "DCS Collectors"]
      * comma/space-separated str:  "DCS Admins,DCS Collectors"
      * missing / null:             returns []

    Anything that is not a string after coercion is dropped.
    """
    raw = userinfo.get(claim_name)
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(g).strip() for g in raw if str(g).strip()]
    if isinstance(raw, str):
        # Some IdPs emit a single string when the user has only one group,
        # or a delimited string when configured oddly. Split conservatively.
        parts = [p.strip() for p in raw.replace(";", ",").split(",")]
        return [p for p in parts if p]
    return []


async def _sync_user_roles_from_groups(
    session: AsyncSession,
    user: User,
    groups: list[str],
    config: "OIDCConfig",
) -> None:
    """Reconcile the user's roles against the IdP group membership.

    Uses ``config.group_role_map`` to translate IdP group names into DCS
    role names. Unknown role names (no row in the tenant's roles table)
    are silently skipped -- callers can verify by checking the role
    table themselves.

    Behaviour summary:
      * sync_groups_on_login=True (default):
          The set of roles is REPLACED with whatever the mapping
          resolves to. Manually-assigned roles are removed if the IdP
          no longer reports the corresponding group. This is what most
          customers want -- demote in Okta -> demote in DCS.
      * sync_groups_on_login=False:
          Newly-mapped roles are ADDED. Existing roles are left alone.
    """
    if not config.group_role_map:
        return  # nothing to do

    target_role_names: set[str] = set()
    for grp in groups:
        mapped = config.group_role_map.get(grp)
        if mapped:
            target_role_names.add(mapped)

    # Resolve role names -> Role rows scoped to this tenant. Names not
    # present in the roles table are dropped (logged via warning would
    # be ideal, but logging infra varies; keep it silent for now).
    if target_role_names:
        rows = await session.execute(
            select(Role).where(
                Role.tenant_id == user.tenant_id,
                Role.name.in_(list(target_role_names)),
            )
        )
        target_roles = list(rows.scalars())
    else:
        target_roles = []
    target_role_ids = {r.id for r in target_roles}

    # Current assignments
    current_rows = await session.execute(
        select(UserRole).where(UserRole.user_id == user.id)
    )
    current_assignments = list(current_rows.scalars())
    current_role_ids = {ur.role_id for ur in current_assignments}

    # Add the missing ones
    for role_id in target_role_ids - current_role_ids:
        session.add(UserRole(user_id=user.id, role_id=role_id))

    # Remove the stale ones (only when full sync is enabled)
    if config.sync_groups_on_login:
        for ur in current_assignments:
            if ur.role_id not in target_role_ids:
                await session.delete(ur)


async def provision_or_update_user(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    userinfo: dict[str, Any],
    idp_provider: str,
    config: "OIDCConfig | None" = None,
) -> User:
    """JIT-provision (or refresh) a user from OIDC claims.

    If ``config`` is supplied, IdP group membership is also synced into
    the user's role assignments and is_owner flag according to
    ``config.group_role_map`` and ``config.owner_groups``.
    """
    sub = userinfo.get("sub")
    email = userinfo.get("email")
    if not email or not isinstance(email, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC userinfo missing email",
        )
    email = email.strip().lower()
    if not sub or not isinstance(sub, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC userinfo missing sub",
        )

    q_sub = select(User).where(User.tenant_id == tenant_id, User.external_id == sub)
    r_sub = await session.execute(q_sub)
    user = r_sub.scalar_one_or_none()

    if not user:
        q_email = select(User).where(User.tenant_id == tenant_id, User.email == email)
        r_email = await session.execute(q_email)
        user = r_email.scalar_one_or_none()

    given = userinfo.get("given_name")
    family = userinfo.get("family_name")
    name = userinfo.get("name")
    first_name = given if isinstance(given, str) else None
    last_name = family if isinstance(family, str) else None
    if first_name is None and last_name is None and isinstance(name, str) and name.strip():
        parts = name.strip().split(None, 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else None

    # Extract IdP groups once so we can apply them consistently to both
    # the create and update branches below.
    groups: list[str] = []
    if config is not None:
        groups = _extract_groups(userinfo, config.group_claim)

    now = datetime.now(timezone.utc)
    if user:
        user.external_id = sub
        user.idp_provider = idp_provider
        user.email = email
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        user.last_login = now
        user.failed_login_attempts = 0
        user.locked_until = None

        if config is not None:
            # Owner flag is mirrored from group membership when the
            # tenant configures owner_groups. Empty owner_groups list
            # means "do not touch is_owner via SSO" -- leaves manual
            # assignments alone. This is intentional: a typo in the
            # owner group name should not silently demote everyone.
            if config.owner_groups:
                user.is_owner = any(g in groups for g in config.owner_groups)
            await _sync_user_roles_from_groups(session, user, groups, config)

        await session.flush()
        return user

    user = User(
        tenant_id=tenant_id,
        email=email,
        password_hash=None,
        external_id=sub,
        idp_provider=idp_provider,
        first_name=first_name,
        last_name=last_name,
        is_active=True,
        is_owner=bool(
            config and config.owner_groups
            and any(g in groups for g in config.owner_groups),
        ),
        is_master=False,
        failed_login_attempts=0,
        locked_until=None,
        last_login=now,
    )
    session.add(user)
    await session.flush()  # need user.id before we can assign roles

    if config is not None:
        await _sync_user_roles_from_groups(session, user, groups, config)
        await session.flush()

    return user
