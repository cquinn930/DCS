"""Flash message schemas."""
from __future__ import annotations
import uuid
from datetime import datetime

from pydantic import Field

from dcs_api.schemas.common import BaseSchema, TimestampSchema


class FlashMessageTemplateCreate(BaseSchema):
    name: str = Field(max_length=200)
    message_text: str
    priority: str = "medium"
    scope: str = "account"
    condition_script: str | None = None
    is_active: bool = True
    auto_apply: bool = False
    require_acknowledgment: bool = False
    icon: str | None = None
    color: str | None = None
    display_config: dict | None = None


class FlashMessageTemplateUpdate(BaseSchema):
    name: str | None = None
    message_text: str | None = None
    priority: str | None = None
    scope: str | None = None
    condition_script: str | None = None
    is_active: bool | None = None
    auto_apply: bool | None = None
    require_acknowledgment: bool | None = None
    icon: str | None = None
    color: str | None = None
    display_config: dict | None = None


class FlashMessageTemplateResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    message_text: str
    priority: str
    scope: str
    condition_script: str | None = None
    is_active: bool
    auto_apply: bool
    require_acknowledgment: bool
    icon: str | None = None
    color: str | None = None
    display_config: dict | None = None


class AccountFlashMessageCreate(BaseSchema):
    account_id: uuid.UUID
    template_id: uuid.UUID | None = None
    message_text: str
    priority: str = "medium"


class AccountFlashMessageResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID
    template_id: uuid.UUID | None = None
    message_text: str
    priority: str
    is_active: bool
    acknowledged: bool
    acknowledged_by: uuid.UUID | None = None
    acknowledged_at: datetime | None = None
    expires_at: datetime | None = None
    source: str | None = None
