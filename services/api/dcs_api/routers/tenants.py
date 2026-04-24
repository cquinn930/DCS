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
from dcs_api.schemas.saml import SAMLConfigResponse, SAMLConfigUpdate
from dcs_api.schemas.sso import (
    SSOConfigResponse,
    SSOProtocol,
    SSOProtocolUpdate,
    infer_protocol,
)
from dcs_api.schemas.printing import PrintingTenantConfig, PrintingTenantConfigUpdate
from dcs_api.schemas.scanning import ScanningTenantConfig, ScanningTenantConfigUpdate
from dcs_api.schemas.telephony import (
    TelephonyTenantConfig,
    TelephonyTenantConfigUpdate,
)
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
        scopes=list(oidc.get("scopes") or ["openid", "email", "profile", "groups"]),
        enabled=enabled,
        group_claim=str(oidc.get("group_claim") or "groups"),
        group_role_map=dict(oidc.get("group_role_map") or {}),
        owner_groups=list(oidc.get("owner_groups") or []),
        sync_groups_on_login=bool(oidc.get("sync_groups_on_login", True)),
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
        group_claim=cfg.group_claim,
        group_role_map=dict(cfg.group_role_map),
        owner_groups=list(cfg.owner_groups),
        sync_groups_on_login=cfg.sync_groups_on_login,
    )


# ---------------------------------------------------------------------------
# SAML / unified SSO endpoints
#
# The legacy OIDC-only endpoints above stay in place so the existing UI
# keeps working unchanged. The endpoints below add SAML support and a
# unified read that the new Settings → SSO page uses to render a
# protocol selector with both forms pre-filled.
# ---------------------------------------------------------------------------


def _saml_response_from_settings(
    saml: dict,
    sp_acs_default: str,
    sp_entity_default: str,
    sp_metadata_default: str,
) -> SAMLConfigResponse:
    """Render the public SAML view of a tenant config dict.

    Cert + private-key material is reduced to "_present" booleans so we
    never echo it back to the UI (it's write-only on this endpoint).
    """
    enabled = bool(
        saml.get("idp_entity_id")
        and saml.get("idp_sso_url")
        and saml.get("idp_x509_cert"),
    )
    return SAMLConfigResponse(
        idp_entity_id=str(saml.get("idp_entity_id") or ""),
        idp_sso_url=str(saml.get("idp_sso_url") or ""),
        idp_cert_present=bool(saml.get("idp_x509_cert")),
        idp_slo_url=(str(saml["idp_slo_url"]) if saml.get("idp_slo_url") else None),
        sp_entity_id=str(saml.get("sp_entity_id") or sp_entity_default),
        sp_acs_url=str(saml.get("sp_acs_url") or sp_acs_default),
        sp_metadata_url=sp_metadata_default,
        sign_authn_requests=bool(saml.get("sign_authn_requests")),
        sp_cert_present=bool(saml.get("sp_x509_cert")),
        sp_key_present=bool(saml.get("sp_private_key")),
        allowed_domains=list(saml.get("allowed_domains") or []),
        group_attribute=str(saml.get("group_attribute") or "groups"),
        group_role_map=dict(saml.get("group_role_map") or {}),
        owner_groups=list(saml.get("owner_groups") or []),
        sync_groups_on_login=bool(saml.get("sync_groups_on_login", True)),
        first_name_attribute=str(saml.get("first_name_attribute") or "firstName"),
        last_name_attribute=str(saml.get("last_name_attribute") or "lastName"),
        email_attribute=str(saml.get("email_attribute") or "email"),
        enabled=enabled,
    )


def _oidc_response_from_settings(oidc: dict) -> OIDCConfigResponse:
    enabled = bool(
        oidc.get("issuer")
        and oidc.get("client_id")
        and oidc.get("client_secret")
        and oidc.get("redirect_uri"),
    )
    return OIDCConfigResponse(
        issuer=oidc.get("issuer") or "https://example.invalid/",
        client_id=oidc.get("client_id") or "",
        redirect_uri=oidc.get("redirect_uri") or "",
        allowed_domains=list(oidc.get("allowed_domains") or []),
        scopes=list(oidc.get("scopes") or ["openid", "email", "profile", "groups"]),
        enabled=enabled,
        group_claim=str(oidc.get("group_claim") or "groups"),
        group_role_map=dict(oidc.get("group_role_map") or {}),
        owner_groups=list(oidc.get("owner_groups") or []),
        sync_groups_on_login=bool(oidc.get("sync_groups_on_login", True)),
    )


def _saml_default_urls(tenant_slug: str) -> tuple[str, str, str]:
    """Compute the default ACS URL, SP entity id, and metadata URL.

    Falls back to empty strings if API_PUBLIC_URL isn't configured;
    the admin can still set them by hand.
    """
    api_base = (getattr(settings, "api_public_url", "") or "").rstrip("/")
    if not api_base:
        return "", "", ""
    acs = f"{api_base}/api/v1/auth/sso/saml/{tenant_slug}/acs"
    metadata = f"{api_base}/api/v1/auth/sso/saml/{tenant_slug}/metadata"
    # Convention: the SP entity id is the metadata URL itself. The IdP
    # only uses it as an opaque identifier, so a self-describing URL
    # avoids one more thing the admin has to type.
    return acs, metadata, metadata


@router.get("/{tenant_id}/sso-config/unified", response_model=SSOConfigResponse)
async def get_tenant_sso_config_unified(
    tenant_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SSOConfigResponse:
    """Return the discriminated SSO config (protocol + both sub-objects).

    Returning both `oidc` and `saml` means the UI can render either
    form when the admin toggles protocol without an extra round-trip.
    Cert and secret material is never included.
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

    s = tenant.settings or {}
    oidc = s.get("oidc") or {}
    saml = s.get("saml") or {}
    sp_acs_default, sp_entity_default, sp_metadata_default = _saml_default_urls(tenant.slug)

    return SSOConfigResponse(
        protocol=infer_protocol(s),
        oidc=_oidc_response_from_settings(oidc),
        saml=_saml_response_from_settings(
            saml, sp_acs_default, sp_entity_default, sp_metadata_default
        ),
    )


@router.put("/{tenant_id}/sso-config/protocol", response_model=SSOConfigResponse)
async def set_tenant_sso_protocol(
    tenant_id: uuid.UUID,
    data: SSOProtocolUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SSOConfigResponse:
    """Switch which SSO protocol is active for a tenant.

    Toggling to `saml` requires the SAML sub-object to already have at
    least the IdP entity_id, SSO URL, and IdP cert configured. Same
    for OIDC. We refuse to enable a protocol that hasn't been
    configured to avoid silently locking users out.
    """
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

    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    base_settings = dict(tenant.settings) if tenant.settings else {}
    target: SSOProtocol = data.protocol

    if target == "saml":
        saml = base_settings.get("saml") or {}
        if not (saml.get("idp_entity_id") and saml.get("idp_sso_url") and saml.get("idp_x509_cert")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SAML not configured: set IdP entity id, SSO URL, and certificate first",
            )
    elif target == "oidc":
        oidc = base_settings.get("oidc") or {}
        if not (oidc.get("issuer") and oidc.get("client_id") and oidc.get("client_secret")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OIDC not configured: set issuer, client_id, and client_secret first",
            )

    sso = dict(base_settings.get("sso") or {})
    sso["protocol"] = target
    base_settings["sso"] = sso
    tenant.settings = base_settings
    await session.flush()

    s = tenant.settings or {}
    sp_acs_default, sp_entity_default, sp_metadata_default = _saml_default_urls(tenant.slug)
    return SSOConfigResponse(
        protocol=infer_protocol(s),
        oidc=_oidc_response_from_settings(s.get("oidc") or {}),
        saml=_saml_response_from_settings(
            s.get("saml") or {}, sp_acs_default, sp_entity_default, sp_metadata_default
        ),
    )


@router.patch("/{tenant_id}/sso-config/saml", response_model=SAMLConfigResponse)
async def update_tenant_saml_config(
    tenant_id: uuid.UUID,
    data: SAMLConfigUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SAMLConfigResponse:
    """Patch the SAML config for a tenant.

    Mirrors the OIDC PATCH endpoint above. Empty `sp_entity_id` /
    `sp_acs_url` are auto-derived from `API_PUBLIC_URL` + the tenant
    slug so admins don't have to construct them by hand.
    """
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
    saml = dict(base_settings.get("saml") or {})
    updates = data.model_dump(exclude_unset=True, mode="json")
    for key, value in updates.items():
        saml[key] = value

    sp_acs_default, sp_entity_default, sp_metadata_default = _saml_default_urls(tenant.slug)
    if not saml.get("sp_acs_url") and sp_acs_default:
        saml["sp_acs_url"] = sp_acs_default
    if not saml.get("sp_entity_id") and sp_entity_default:
        saml["sp_entity_id"] = sp_entity_default

    base_settings["saml"] = saml
    tenant.settings = base_settings
    await session.flush()

    return _saml_response_from_settings(
        saml, sp_acs_default, sp_entity_default, sp_metadata_default
    )


# ---------------------------------------------------------------------------
# Telephony / Print / Scan provider config
#
# All three follow the SSO pattern: a single jsonb blob inside
# tenant.settings.<key>, edited via GET / PATCH on a typed schema.
# Owners and Admins (with the matching MANAGE_* permission) can edit;
# non-owners get 403. Read access is broader — anyone in the tenant can
# read so the UI can render capability-gated controls.
# ---------------------------------------------------------------------------


def _ensure_can_edit(user: CurrentUser, tenant_id: uuid.UUID, perm: str) -> None:
    """Centralized check matching the SSO endpoints' authorization rule."""
    if tenant_id != user.tenant_id and not user.is_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    if tenant_id == user.tenant_id and not (user.is_owner or user.has_permission(perm)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or matching manage permission required",
        )


async def _load_tenant_or_404(session: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )
    return tenant


# --- Telephony --------------------------------------------------------------


@router.get("/{tenant_id}/telephony-config", response_model=TelephonyTenantConfig)
async def get_telephony_config(
    tenant_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> TelephonyTenantConfig:
    if tenant_id != user.tenant_id and not user.is_master:
        raise HTTPException(status_code=403, detail="Access denied")
    tenant = await _load_tenant_or_404(session, tenant_id)
    raw = (tenant.settings or {}).get("telephony") or {}
    try:
        return TelephonyTenantConfig.model_validate(raw)
    except ValidationError:
        return TelephonyTenantConfig()


@router.patch("/{tenant_id}/telephony-config", response_model=TelephonyTenantConfig)
async def update_telephony_config(
    tenant_id: uuid.UUID,
    data: TelephonyTenantConfigUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> TelephonyTenantConfig:
    _ensure_can_edit(user, tenant_id, Permissions.MANAGE_TELEPHONY)
    tenant = await _load_tenant_or_404(session, tenant_id)

    base_settings = dict(tenant.settings) if tenant.settings else {}
    current = dict(base_settings.get("telephony") or {})
    for key, value in data.model_dump(exclude_unset=True, mode="json").items():
        current[key] = value
    base_settings["telephony"] = current
    tenant.settings = base_settings
    await session.flush()

    try:
        return TelephonyTenantConfig.model_validate(current)
    except ValidationError:
        return TelephonyTenantConfig()


# --- Printing ---------------------------------------------------------------


@router.get("/{tenant_id}/printing-config", response_model=PrintingTenantConfig)
async def get_printing_config(
    tenant_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> PrintingTenantConfig:
    if tenant_id != user.tenant_id and not user.is_master:
        raise HTTPException(status_code=403, detail="Access denied")
    tenant = await _load_tenant_or_404(session, tenant_id)
    raw = (tenant.settings or {}).get("printing") or {}
    try:
        return PrintingTenantConfig.model_validate(raw)
    except ValidationError:
        return PrintingTenantConfig()


@router.patch("/{tenant_id}/printing-config", response_model=PrintingTenantConfig)
async def update_printing_config(
    tenant_id: uuid.UUID,
    data: PrintingTenantConfigUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> PrintingTenantConfig:
    _ensure_can_edit(user, tenant_id, Permissions.MANAGE_PRINTING)
    tenant = await _load_tenant_or_404(session, tenant_id)

    base_settings = dict(tenant.settings) if tenant.settings else {}
    current = dict(base_settings.get("printing") or {})
    for key, value in data.model_dump(exclude_unset=True, mode="json").items():
        current[key] = value
    base_settings["printing"] = current
    tenant.settings = base_settings
    await session.flush()

    try:
        return PrintingTenantConfig.model_validate(current)
    except ValidationError:
        return PrintingTenantConfig()


# --- Scanning ---------------------------------------------------------------


@router.get("/{tenant_id}/scanning-config", response_model=ScanningTenantConfig)
async def get_scanning_config(
    tenant_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ScanningTenantConfig:
    if tenant_id != user.tenant_id and not user.is_master:
        raise HTTPException(status_code=403, detail="Access denied")
    tenant = await _load_tenant_or_404(session, tenant_id)
    raw = (tenant.settings or {}).get("scanning") or {}
    try:
        return ScanningTenantConfig.model_validate(raw)
    except ValidationError:
        return ScanningTenantConfig()


@router.patch("/{tenant_id}/scanning-config", response_model=ScanningTenantConfig)
async def update_scanning_config(
    tenant_id: uuid.UUID,
    data: ScanningTenantConfigUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ScanningTenantConfig:
    _ensure_can_edit(user, tenant_id, Permissions.MANAGE_SCANNING)
    tenant = await _load_tenant_or_404(session, tenant_id)

    base_settings = dict(tenant.settings) if tenant.settings else {}
    current = dict(base_settings.get("scanning") or {})
    for key, value in data.model_dump(exclude_unset=True, mode="json").items():
        current[key] = value
    base_settings["scanning"] = current
    tenant.settings = base_settings
    await session.flush()

    try:
        return ScanningTenantConfig.model_validate(current)
    except ValidationError:
        return ScanningTenantConfig()
