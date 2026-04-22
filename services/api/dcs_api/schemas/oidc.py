"""OIDC / SSO configuration schemas."""

from pydantic import BaseModel, Field, HttpUrl


class OIDCConfigCreate(BaseModel):
    issuer: HttpUrl
    client_id: str = Field(..., min_length=1)
    client_secret: str = Field(..., min_length=1)
    redirect_uri: HttpUrl
    allowed_domains: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=lambda: ["openid", "email", "profile"])


class OIDCConfigUpdate(BaseModel):
    issuer: HttpUrl | None = None
    client_id: str | None = Field(None, min_length=1)
    client_secret: str | None = Field(None, min_length=1)
    redirect_uri: HttpUrl | None = None
    allowed_domains: list[str] | None = None
    scopes: list[str] | None = None


class OIDCConfigResponse(BaseModel):
    issuer: HttpUrl
    client_id: str
    redirect_uri: str
    allowed_domains: list[str]
    scopes: list[str]
    enabled: bool
