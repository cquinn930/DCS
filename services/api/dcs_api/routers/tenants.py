"""Tenant management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.auth.oidc import OIDCConfig as TenantOIDCConfig
from dcs_api.auth.rbac import CurrentUser, Permissions, get_current_user, require_permission
from dcs_api.config import get_settings
from dcs_api.database import get_session
from dcs_api.models.tenant import Tenant
from dcs_api.schemas.oidc import OIDCConfigResponse, OIDCConfigUpdate
from dcs_api.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate

settings = get_settings()

router = APIRouter()


@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_TENANT_METADATA))],
) -> list[TenantResponse]:
    """List all tenants (master account only)."""
    if not user.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master account required",
        )

    query = select(Tenant)
    result = await session.execute(query)
    tenants = list(result.scalars().all())
    return [TenantResponse.model_validate(t) for t in tenants]


@router.get("/current", response_model=TenantResponse)
async def get_current_tenant(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> TenantResponse:
    """Get current user's tenant."""
    query = select(Tenant).where(Tenant.id == user.tenant_id)
    result = await session.execute(query)
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    return TenantResponse.model_validate(tenant)


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> TenantResponse:
    """Get tenant by ID."""
    # Users can only view their own tenant unless they're master
    if tenant_id != user.tenant_id and not user.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    query = select(Tenant).where(Tenant.id == tenant_id)
    result = await session.execute(query)
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    return TenantResponse.model_validate(tenant)


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    data: TenantCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(require_permission(Permissions.VIEW_TENANT_METADATA))],
) -> TenantResponse:
    """Create a new tenant (master account only)."""
    if not user.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master account required",
        )

    # Check slug uniqueness
    existing = await session.execute(select(Tenant).where(Tenant.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant slug already exists",
        )

    tenant = Tenant(
        name=data.name,
        slug=data.slug,
        business_model=data.business_model,
        default_jurisdiction=data.default_jurisdiction,
        retention_years=data.retention_years,
    )
    session.add(tenant)
    await session.flush()

    return TenantResponse.model_validate(tenant)


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: uuid.UUID,
    data: TenantUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> TenantResponse:
    """Update tenant settings."""
    # Only owner or master can update tenant
    if tenant_id != user.tenant_id and not user.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    if tenant_id == user.tenant_id and not user.is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner permission required",
        )

    query = select(Tenant).where(Tenant.id == tenant_id)
    result = await session.execute(query)
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Retention policy changes are owner-only and non-delegable
    if data.retention_years is not None:
        if data.retention_years < 7:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Retention cannot be less than 7 years (statutory minimum)",
            )
        if not user.is_owner and not user.is_master:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Retention changes require owner permission",
            )

    # Apply updates
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(tenant, key, value)

    await session.flush()
    return TenantResponse.model_validate(tenant)


@router.get("/{tenant_id}/sso-config", response_model=OIDCConfigResponse)
async def get_tenant_sso_config(
    tenant_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> OIDCConfigResponse:
    """Read the OIDC config for a tenant.

    Returns a response with empty strings and enabled=false if SSO has
    never been configured (so the settings UI can render an empty form
    instead of error-handling a 404).

    `client_secret` is intentionally NOT returned — it's write-only.
    """
    if tenant_id != user.tenant_id and not user.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    oidc = (tenant.settings or {}).get("oidc") or {}
    enabled = bool(
        oidc.get("issuer")
        and oidc.get("client_id")
        and oidc.get("client_secret")
        and oidc.get("redirect_uri"),
    )
    # Build a permissive response that won't 500 on partially-configured
    # tenants. We populate URL-typed fields with safe placeholders if
    # missing, since OIDCConfigResponse expects HttpUrl on `issuer`.
    return OIDCConfigResponse(
        issuer=oidc.get("issuer") or "https://example.invalid/",
        client_id=oidc.get("client_id") or "",
        redirect_uri=oidc.get("redirect_uri") or "",
        allowed_domains=list(oidc.get("allowed_domains") or []),
        scopes=list(oidc.get("scopes") or ["openid", "email", "profile"]),
        enabled=enabled,
    )


@router.patch("/{tenant_id}/sso-config", response_model=OIDCConfigResponse)
async def update_tenant_sso_config(
    tenant_id: uuid.UUID,
    data: OIDCConfigUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> OIDCConfigResponse:
    if tenant_id != user.tenant_id and not user.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    if tenant_id == user.tenant_id and not user.is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner permission required",
        )

    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    base_settings = dict(tenant.settings) if tenant.settings else {}
    oidc = dict(base_settings.get("oidc") or {})
    updates = data.model_dump(exclude_unset=True, mode="json")
    for key, value in updates.items():
        oidc[key] = value

    if not oidc.get("redirect_uri"):
        # Fall back to the API's public base URL. Use getattr so a missing
        # api_public_url setting yields a clean 400, not a 500.
        api_base = getattr(settings, "api_public_url", "") or ""
        if not api_base:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "redirect_uri is required: server has no API_PUBLIC_URL "
                    "configured to derive a default. Either set API_PUBLIC_URL "
                    "in the API .env or supply redirect_uri in the request body."
                ),
            )
        oidc["redirect_uri"] = f"{api_base.rstrip('/')}/api/v1/auth/sso/callback"

    merged = dict(oidc)
    try:
        cfg = TenantOIDCConfig.model_validate(merged)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    base_settings["oidc"] = oidc
    tenant.settings = base_settings
    await session.flush()

    enabled = bool(
        oidc.get("issuer")
        and oidc.get("client_id")
        and oidc.get("client_secret")
        and oidc.get("redirect_uri"),
    )

    return OIDCConfigResponse(
        issuer=cfg.issuer,
        client_id=cfg.client_id,
        redirect_uri=cfg.redirect_uri,
        allowed_domains=list(cfg.allowed_domains),
        scopes=list(cfg.scopes),
        enabled=enabled,
    )
