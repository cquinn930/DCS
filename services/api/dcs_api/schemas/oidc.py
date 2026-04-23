"""OIDC / SSO configuration schemas."""

from pydantic import BaseModel, Field, HttpUrl


class OIDCConfigCreate(BaseModel):
    issuer: HttpUrl
    client_id: str = Field(..., min_length=1)
    client_secret: str = Field(..., min_length=1)
    redirect_uri: HttpUrl
    allowed_domains: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(
        default_factory=lambda: ["openid", "email", "profile", "groups"],
    )
    group_claim: str = "groups"
    group_role_map: dict[str, str] = Field(default_factory=dict)
    owner_groups: list[str] = Field(default_factory=list)
    sync_groups_on_login: bool = True


class OIDCConfigUpdate(BaseModel):
    issuer: HttpUrl | None = None
    client_id: str | None = Field(None, min_length=1)
    client_secret: str | None = Field(None, min_length=1)
    redirect_uri: HttpUrl | None = None
    allowed_domains: list[str] | None = None
    scopes: list[str] | None = None
    group_claim: str | None = None
    group_role_map: dict[str, str] | None = None
    owner_groups: list[str] | None = None
    sync_groups_on_login: bool | None = None


class OIDCConfigResponse(BaseModel):
    issuer: HttpUrl
    client_id: str
    redirect_uri: str
    allowed_domains: list[str]
    scopes: list[str]
    enabled: bool
    group_claim: str = "groups"
    group_role_map: dict[str, str] = Field(default_factory=dict)
    owner_groups: list[str] = Field(default_factory=list)
    sync_groups_on_login: bool = True
