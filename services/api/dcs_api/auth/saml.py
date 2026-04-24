"""SAML 2.0 SP support.

Sits alongside ``auth/oidc.py`` and is invoked from the same SSO
dispatcher in ``routers/auth.py``. The runtime config object
(``SAMLConfig``) deliberately mirrors ``OIDCConfig`` for the four
group-mapping fields (``group_claim``, ``group_role_map``,
``owner_groups``, ``sync_groups_on_login``) so that
``provision_or_update_user`` from ``auth/oidc.py`` can consume either
without branching.

The on-disk schema (``schemas/saml.py``) uses ``group_attribute`` —
the SAML-native term — and we translate to ``group_claim`` here, so the
admin UI shows the right vocabulary while the provisioning code stays
uniform.

Heavy XML / signature work is delegated to ``python3-saml``
(``onelogin.saml2.*``). That library is synchronous; we call it from
async route handlers without ``run_in_executor`` because each call is
CPU-bound, deterministic, and finishes in single-digit milliseconds.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.models.tenant import Tenant

logger = logging.getLogger("dcs_api.auth.saml")

# python3-saml is imported lazily inside each function so import errors
# (e.g. libxmlsec1-dev not installed yet) only surface when SAML is
# actually exercised — the rest of the app keeps booting.

POST_BINDING = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
REDIRECT_BINDING = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"


@dataclass
class SAMLConfig:
    """Runtime SAML configuration for one tenant."""

    # IdP -----------------------------------------------------------------
    idp_entity_id: str
    idp_sso_url: str
    idp_x509_cert: str
    idp_slo_url: str | None = None

    # SP ------------------------------------------------------------------
    sp_entity_id: str = ""
    sp_acs_url: str = ""

    sign_authn_requests: bool = False
    sp_x509_cert: str = ""
    sp_private_key: str = ""

    # Claim mapping (mirrors OIDCConfig field names for shared
    # provisioning -- see SSOClaimMapping protocol in auth/oidc.py).
    allowed_domains: list[str] = field(default_factory=list)
    group_claim: str = "groups"  # populated from schema's group_attribute
    group_role_map: dict[str, str] = field(default_factory=dict)
    owner_groups: list[str] = field(default_factory=list)
    sync_groups_on_login: bool = True

    # SAML attribute name lookups (Okta defaults; ADFS / Azure AD use
    # different names and the admin can override per-tenant in the UI).
    first_name_attribute: str = "firstName"
    last_name_attribute: str = "lastName"
    email_attribute: str = "email"


async def get_tenant_saml_config(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> SAMLConfig | None:
    """Load a tenant's SAML config from ``tenant.settings.saml``.

    Returns None if the tenant doesn't exist or hasn't configured the
    minimum SAML fields (entity id, SSO URL, IdP certificate). The
    caller can then 4xx with a clear "SAML not configured" error.
    """
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant or not tenant.settings:
        return None
    raw = tenant.settings.get("saml")
    if not raw or not isinstance(raw, dict):
        return None

    required = ("idp_entity_id", "idp_sso_url", "idp_x509_cert")
    if not all(raw.get(k) for k in required):
        return None

    return SAMLConfig(
        idp_entity_id=str(raw["idp_entity_id"]),
        idp_sso_url=str(raw["idp_sso_url"]),
        idp_x509_cert=str(raw["idp_x509_cert"]),
        idp_slo_url=(str(raw["idp_slo_url"]) if raw.get("idp_slo_url") else None),
        sp_entity_id=str(raw.get("sp_entity_id") or ""),
        sp_acs_url=str(raw.get("sp_acs_url") or ""),
        sign_authn_requests=bool(raw.get("sign_authn_requests")),
        sp_x509_cert=str(raw.get("sp_x509_cert") or ""),
        sp_private_key=str(raw.get("sp_private_key") or ""),
        allowed_domains=list(raw.get("allowed_domains") or []),
        # SAML schema stores the SAML-native `group_attribute`; surface
        # it as `group_claim` to the provisioning code.
        group_claim=str(raw.get("group_attribute") or "groups"),
        group_role_map=dict(raw.get("group_role_map") or {}),
        owner_groups=list(raw.get("owner_groups") or []),
        sync_groups_on_login=bool(raw.get("sync_groups_on_login", True)),
        first_name_attribute=str(raw.get("first_name_attribute") or "firstName"),
        last_name_attribute=str(raw.get("last_name_attribute") or "lastName"),
        email_attribute=str(raw.get("email_attribute") or "email"),
    )


def _build_settings_dict(config: SAMLConfig) -> dict[str, Any]:
    """Translate our SAMLConfig into the dict shape python3-saml wants."""
    if not config.sp_entity_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SAML SP entity_id not configured for this tenant",
        )
    if not config.sp_acs_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SAML SP ACS URL not configured for this tenant",
        )

    if config.sign_authn_requests and (
        not config.sp_x509_cert or not config.sp_private_key
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "SAML AuthnRequest signing is enabled but the SP certificate "
                "or private key is missing"
            ),
        )

    settings: dict[str, Any] = {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": config.sp_entity_id,
            "assertionConsumerService": {
                "url": config.sp_acs_url,
                "binding": POST_BINDING,
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": config.sp_x509_cert,
            "privateKey": config.sp_private_key,
        },
        "idp": {
            "entityId": config.idp_entity_id,
            "singleSignOnService": {
                "url": config.idp_sso_url,
                "binding": REDIRECT_BINDING,
            },
            "x509cert": config.idp_x509_cert,
        },
        "security": {
            "authnRequestsSigned": config.sign_authn_requests,
            # Always require the IdP to sign at least the assertion;
            # without this any unsigned response would be accepted.
            "wantAssertionsSigned": True,
            "wantMessagesSigned": False,
            "wantNameId": True,
            "wantNameIdEncrypted": False,
            "wantAssertionsEncrypted": False,
            "signMetadata": False,
            "requestedAuthnContext": False,
            "signatureAlgorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
            "digestAlgorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
        },
    }

    if config.idp_slo_url:
        settings["idp"]["singleLogoutService"] = {
            "url": config.idp_slo_url,
            "binding": REDIRECT_BINDING,
        }

    return settings


def _request_to_saml_data(request: Request, post_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Convert a FastAPI Request into the dict python3-saml expects.

    python3-saml is framework-agnostic and asks for the request data in
    a Flask-WSGI-ish shape. ``post_data`` is supplied separately because
    we need to ``await`` the form body in the async route, then pass the
    already-parsed dict in here.
    """
    url = request.url
    parsed_root = urlparse(str(request.base_url))
    return {
        "https": "on" if url.scheme == "https" else "off",
        "http_host": url.hostname or parsed_root.hostname or "",
        "server_port": str(url.port) if url.port else ("443" if url.scheme == "https" else "80"),
        "script_name": url.path,
        "get_data": dict(request.query_params),
        "post_data": post_data or {},
    }


def build_login_redirect(
    config: SAMLConfig,
    request: Request,
    relay_state: str | None = None,
) -> str:
    """Build the IdP-bound URL for SP-initiated login.

    Returns a fully-formed Redirect-binding URL (with the deflated +
    base64'd AuthnRequest in the query string). The caller should
    issue a 302 to it.
    """
    from onelogin.saml2.auth import OneLogin_Saml2_Auth

    saml_settings = _build_settings_dict(config)
    saml_request_data = _request_to_saml_data(request)
    auth = OneLogin_Saml2_Auth(saml_request_data, saml_settings)
    # `login()` returns the redirect URL; passing return_to lets us
    # round-trip our `state` value through the IdP via RelayState.
    return auth.login(return_to=relay_state or "/")


def build_sp_metadata(config: SAMLConfig) -> str:
    """Render the SP metadata XML (for handing to the IdP admin)."""
    from onelogin.saml2.settings import OneLogin_Saml2_Settings

    saml_settings = _build_settings_dict(config)
    s = OneLogin_Saml2_Settings(saml_settings, sp_validation_only=True)
    metadata = s.get_sp_metadata()
    errors = s.validate_metadata(metadata)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SAML SP metadata invalid: {errors}",
        )
    if isinstance(metadata, bytes):
        metadata = metadata.decode("utf-8")
    return metadata


async def process_acs(
    config: SAMLConfig,
    request: Request,
) -> tuple[dict[str, Any], str | None]:
    """Validate a posted SAMLResponse and return (claims, relay_state).

    `claims` is shaped like an OIDC userinfo dict so the existing
    ``provision_or_update_user`` can consume it unchanged:

        {
          "sub": "<NameID or persistent attribute>",
          "email": "...",
          "given_name": "...",
          "family_name": "...",
          "<config.group_claim>": ["..."]   # IdP group memberships
        }
    """
    from onelogin.saml2.auth import OneLogin_Saml2_Auth

    form = await request.form()
    # python3-saml wants strings only; coerce defensively.
    post_data = {k: (v if isinstance(v, str) else str(v)) for k, v in form.items()}
    saml_settings = _build_settings_dict(config)
    saml_request_data = _request_to_saml_data(request, post_data=post_data)
    auth = OneLogin_Saml2_Auth(saml_request_data, saml_settings)

    auth.process_response()
    errors = auth.get_errors()
    if errors:
        last = auth.get_last_error_reason()
        logger.warning(
            "SAML ACS validation errors=%r reason=%r",
            errors,
            last,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"SAML response invalid: {', '.join(errors)}"
            + (f" ({last})" if last else ""),
        )
    if not auth.is_authenticated():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SAML response did not authenticate user",
        )

    attributes: dict[str, Any] = auth.get_attributes() or {}
    nameid = auth.get_nameid()
    relay_state = post_data.get("RelayState") or None

    logger.warning(
        "SAML ACS success: nameid=%s attribute_keys=%r relay_state=%r",
        nameid,
        sorted(attributes.keys()),
        relay_state,
    )

    claims = _attributes_to_claims(attributes, nameid, config)
    return claims, relay_state


def _first(values: Any) -> str | None:
    """SAML attributes are always lists. Pick the first non-empty value."""
    if isinstance(values, list):
        for v in values:
            if v is None:
                continue
            s = str(v).strip()
            if s:
                return s
        return None
    if values is None:
        return None
    s = str(values).strip()
    return s or None


def _attributes_to_claims(
    attributes: dict[str, Any],
    nameid: str | None,
    config: SAMLConfig,
) -> dict[str, Any]:
    """Map a SAML AttributeStatement onto an OIDC-userinfo-shaped dict.

    Produces the same keys (`sub`, `email`, `given_name`, `family_name`,
    `name`, plus the group-claim key) so ``provision_or_update_user``
    treats the result identically to an OIDC payload.
    """
    email = _first(attributes.get(config.email_attribute)) or _first(
        attributes.get("email")
    )
    if not email and nameid and "@" in nameid:
        # Many IdPs use the email address as NameID when the
        # NameIDFormat is `emailAddress`.
        email = nameid

    given = _first(attributes.get(config.first_name_attribute)) or _first(
        attributes.get("givenName")
    )
    family = _first(attributes.get(config.last_name_attribute)) or _first(
        attributes.get("surname")
    )

    full_name = None
    if given or family:
        full_name = " ".join(p for p in (given, family) if p) or None

    sub = nameid or email
    claims: dict[str, Any] = {
        "sub": sub,
        "email": email,
        "given_name": given,
        "family_name": family,
        "name": full_name,
    }

    # Group/role attribute. Only set the key if the IdP actually sent
    # it -- presence vs absence drives the "don't clobber is_owner"
    # behaviour in provision_or_update_user.
    if config.group_claim in attributes:
        claims[config.group_claim] = list(attributes[config.group_claim] or [])

    return claims


def email_domain_allowed(email: str, allowed_domains: list[str]) -> bool:
    """Same allow-list semantics as `auth/oidc.email_domain_allowed`."""
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[-1].lower()
    allowed = {d.lower().lstrip("@") for d in allowed_domains}
    return domain in allowed
