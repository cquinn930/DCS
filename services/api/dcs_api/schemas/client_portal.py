"""Client portal schemas."""
from __future__ import annotations
import uuid
from datetime import datetime

from pydantic import Field

from dcs_api.schemas.common import BaseSchema, TimestampSchema


class ClientPortalUserCreate(BaseSchema):
    client_id: uuid.UUID
    email: str = Field(max_length=320)
    name: str = Field(max_length=200)
    password: str = Field(min_length=8, max_length=128)
    access_level: str = "view_only"
    permissions: dict | None = None
    notification_preferences: dict | None = None
    ip_whitelist: dict | None = None


class ClientPortalUserUpdate(BaseSchema):
    name: str | None = None
    email: str | None = None
    access_level: str | None = None
    is_active: bool | None = None
    permissions: dict | None = None
    notification_preferences: dict | None = None
    ip_whitelist: dict | None = None


class ClientPortalUserResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    email: str
    name: str
    access_level: str
    is_active: bool
    last_login: datetime | None = None
    permissions: dict | None = None
    notification_preferences: dict | None = None
    ip_whitelist: dict | None = None
