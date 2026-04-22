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

from dcs_api.models.tenant import Tenant, User


class OIDCConfig(BaseModel):
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str] = Field(default_factory=lambda: ["openid", "email", "profile"])
    allowed_domains: list[str] = Field(default_factory=list)


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


async def provision_or_update_user(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    userinfo: dict[str, Any],
    idp_provider: str,
) -> User:
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
        is_owner=False,
        is_master=False,
        failed_login_attempts=0,
        locked_until=None,
        last_login=now,
    )
    session.add(user)
    await session.flush()
    return user
