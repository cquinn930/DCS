"""Account access audit trail models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from dcs_api.models.base import TenantScopedModel


class AuditAction(str, enum.Enum):
    VIEW = "view"
    EDIT = "edit"
    CREATE = "create"
    DELETE = "delete"
    EXPORT = "export"
    PRINT = "print"
    LOGIN = "login"
    LOGOUT = "logout"
    PERMISSION_CHANGE = "permission_change"


class AccountAccessLog(TenantScopedModel):
    __tablename__ = "account_access_logs"

    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class AuditConfig(TenantScopedModel):
    __tablename__ = "audit_configs"

    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    track_views: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    track_edits: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    track_exports: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    track_prints: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    prevent_print_screen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=365, nullable=False)
    alert_on_suspicious: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suspicious_threshold: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class LoginAuditLog(TenantScopedModel):
    __tablename__ = "login_audit_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    workstation: Mapped[str | None] = mapped_column(String(200), nullable=True)
