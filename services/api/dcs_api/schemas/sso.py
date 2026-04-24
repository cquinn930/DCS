"""Unified SSO configuration schemas.

A tenant can have either OIDC or SAML enabled at any given time, never
both. The wire shape is a discriminated union keyed on `protocol`.

On disk in `tenant.settings`:

    {
      "sso": { "protocol": "oidc" | "saml" | "none" },
      "oidc": { ... },
      "saml": { ... }
    }

`oidc` and `saml` may both be populated (so an admin can toggle without
losing the other config), but only the one selected by `sso.protocol`
is honoured at login time. If `sso.protocol` is missing, we fall back
to the legacy behaviour of inferring from whichever sub-object looks
populated, defaulting to "oidc" for tenants set up before SAML existed.
"""

from typing import Literal

from pydantic import BaseModel, Field

from dcs_api.schemas.oidc import OIDCConfigResponse
from dcs_api.schemas.saml import SAMLConfigResponse

SSOProtocol = Literal["oidc", "saml", "none"]


class SSOProtocolUpdate(BaseModel):
    """PUT body for switching the active SSO protocol."""

    protocol: SSOProtocol


class SSOConfigResponse(BaseModel):
    """Unified read response for the Settings → SSO page.

    Both `oidc` and `saml` are always returned (with safe placeholder /
    empty values when unconfigured) so the UI can render either form
    without a separate fetch when the admin toggles protocols.
    """

    protocol: SSOProtocol = "none"
    oidc: OIDCConfigResponse
    saml: SAMLConfigResponse


def infer_protocol(settings: dict | None) -> SSOProtocol:
    """Pick the active SSO protocol for a tenant.

    Order of precedence:
      1. Explicit `settings.sso.protocol` if set to a known value.
      2. If a populated `settings.oidc` exists, "oidc" (legacy default).
      3. If a populated `settings.saml` exists, "saml".
      4. "none".
    """
    settings = settings or {}
    sso = settings.get("sso") or {}
    explicit = sso.get("protocol")
    if explicit in ("oidc", "saml", "none"):
        return explicit  # type: ignore[return-value]

    oidc = settings.get("oidc") or {}
    if oidc.get("issuer") and oidc.get("client_id") and oidc.get("client_secret"):
        return "oidc"

    saml = settings.get("saml") or {}
    if saml.get("idp_entity_id") and saml.get("idp_sso_url") and saml.get("idp_x509_cert"):
        return "saml"

    return "none"
