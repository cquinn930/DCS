"""Audit trail schemas."""
from __future__ import annotations
import uuid
from datetime import datetime

from pydantic import Field

from dcs_api.schemas.common import BaseSchema, TimestampSchema


class AccountAccessLogResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID | None = None
    user_id: uuid.UUID
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    details: dict | None = None
    session_id: str | None = None


class AuditConfigCreate(BaseSchema):
    name: str = Field(max_length=200)
    client_id: uuid.UUID | None = None
    track_views: bool = True
    track_edits: bool = True
    track_exports: bool = True
    track_prints: bool = True
    prevent_print_screen: bool = False
    retention_days: int = 365
    alert_on_suspicious: bool = False
    suspicious_threshold: int = 100
    is_active: bool = True
    settings: dict | None = None


class AuditConfigUpdate(BaseSchema):
    name: str | None = None
    track_views: bool | None = None
    track_edits: bool | None = None
    track_exports: bool | None = None
    track_prints: bool | None = None
    prevent_print_screen: bool | None = None
    retention_days: int | None = None
    alert_on_suspicious: bool | None = None
    suspicious_threshold: int | None = None
    is_active: bool | None = None
    settings: dict | None = None


class AuditConfigResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID | None = None
    name: str
    track_views: bool
    track_edits: bool
    track_exports: bool
    track_prints: bool
    prevent_print_screen: bool
    retention_days: int
    alert_on_suspicious: bool
    suspicious_threshold: int
    is_active: bool
    settings: dict | None = None


class LoginAuditLogResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    action: str
    ip_address: str | None = None
    user_agent: str | None = None
    success: bool
    failure_reason: str | None = None
    workstation: str | None = None
