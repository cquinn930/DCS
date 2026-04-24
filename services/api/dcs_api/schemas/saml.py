"""SAML 2.0 SP configuration schemas.

Mirrors the layout of `oidc.py`. Field naming for group/role mapping is
deliberately the same as OIDC so the JIT-provisioning code can consume
either protocol's config object via the same attribute names.

`group_attribute` here corresponds conceptually to OIDC's `group_claim`:
the name of the SAML attribute (in the IdP's AttributeStatement) that
carries the user's group memberships. For Okta this is typically
"groups"; for ADFS it's often
"http://schemas.microsoft.com/ws/2008/06/identity/claims/role".
"""

from pydantic import BaseModel, Field, HttpUrl


class SAMLConfigCreate(BaseModel):
    # IdP side ------------------------------------------------------------
    idp_entity_id: str = Field(..., min_length=1)
    idp_sso_url: HttpUrl
    idp_x509_cert: str = Field(..., min_length=1)
    # Optional IdP single-logout URL. We don't currently initiate SLO,
    # but storing it lets us validate LogoutRequest from the IdP later
    # without a config migration.
    idp_slo_url: HttpUrl | None = None

    # SP side -------------------------------------------------------------
    # Both default to deriving from API_PUBLIC_URL at write time if blank.
    sp_entity_id: str = ""
    sp_acs_url: str = ""

    # AuthnRequest signing is opt-in. When True, both fields must be
    # provided; the SP private key never leaves the server.
    sign_authn_requests: bool = False
    sp_x509_cert: str = ""
    sp_private_key: str = ""

    # Shared (mirror OIDC) -----------------------------------------------
    allowed_domains: list[str] = Field(default_factory=list)
    group_attribute: str = "groups"
    group_role_map: dict[str, str] = Field(default_factory=dict)
    owner_groups: list[str] = Field(default_factory=list)
    sync_groups_on_login: bool = True

    # Attribute name lookups for first/last name. Defaults match Okta.
    first_name_attribute: str = "firstName"
    last_name_attribute: str = "lastName"
    email_attribute: str = "email"


class SAMLConfigUpdate(BaseModel):
    idp_entity_id: str | None = Field(None, min_length=1)
    idp_sso_url: HttpUrl | None = None
    idp_x509_cert: str | None = Field(None, min_length=1)
    idp_slo_url: HttpUrl | None = None

    sp_entity_id: str | None = None
    sp_acs_url: str | None = None

    sign_authn_requests: bool | None = None
    sp_x509_cert: str | None = None
    sp_private_key: str | None = None

    allowed_domains: list[str] | None = None
    group_attribute: str | None = None
    group_role_map: dict[str, str] | None = None
    owner_groups: list[str] | None = None
    sync_groups_on_login: bool | None = None

    first_name_attribute: str | None = None
    last_name_attribute: str | None = None
    email_attribute: str | None = None


class SAMLConfigResponse(BaseModel):
    idp_entity_id: str
    idp_sso_url: str
    # We never echo back the IdP cert; it can be verbose and is only
    # needed at write time. The UI shows a "configured / not configured"
    # indicator instead.
    idp_cert_present: bool
    idp_slo_url: str | None = None

    sp_entity_id: str
    sp_acs_url: str
    # Convenience field for the UI: the URL to download the SP metadata
    # XML. Always derived server-side from API_PUBLIC_URL so the
    # frontend does not need to know the public base URL.
    sp_metadata_url: str = ""

    sign_authn_requests: bool
    sp_cert_present: bool
    sp_key_present: bool

    allowed_domains: list[str]
    group_attribute: str
    group_role_map: dict[str, str]
    owner_groups: list[str]
    sync_groups_on_login: bool

    first_name_attribute: str
    last_name_attribute: str
    email_attribute: str

    enabled: bool
