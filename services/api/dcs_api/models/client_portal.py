"""Client portal access models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from dcs_api.models.base import TenantScopedModel


class PortalAccessLevel(str, enum.Enum):
    VIEW_ONLY = "view_only"
    STANDARD = "standard"
    FULL = "full"
    CUSTOM = "custom"


class ClientPortalUser(TenantScopedModel):
    __tablename__ = "client_portal_users"

    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    access_level: Mapped[PortalAccessLevel] = mapped_column(Enum(PortalAccessLevel), default=PortalAccessLevel.VIEW_ONLY, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    permissions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notification_preferences: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_whitelist: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ClientPortalSession(TenantScopedModel):
    __tablename__ = "client_portal_sessions"

    portal_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("client_portal_users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
