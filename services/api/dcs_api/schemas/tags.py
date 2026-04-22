"""Tag definition and assignment schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.tags import TagCategory, TagVisibility
from dcs_api.schemas.common import TimestampSchema


class TagDefinitionCreate(BaseModel):
    code: str = Field(..., max_length=30)
    name: str = Field(..., max_length=255)
    description: str | None = None
    category: TagCategory = TagCategory.CUSTOM
    visibility: TagVisibility = TagVisibility.PUBLIC
    color: str | None = Field(None, max_length=7)
    auto_activity_code_id: uuid.UUID | None = None
    auto_status_change: str | None = Field(None, max_length=30)
    auto_queue_id: uuid.UUID | None = None
    triggers: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    is_system: bool = False


class TagDefinitionUpdate(BaseModel):
    code: str | None = Field(None, max_length=30)
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    category: TagCategory | None = None
    visibility: TagVisibility | None = None
    color: str | None = Field(None, max_length=7)
    auto_activity_code_id: uuid.UUID | None = None
    auto_status_change: str | None = Field(None, max_length=30)
    auto_queue_id: uuid.UUID | None = None
    triggers: dict[str, Any] | None = None
    is_active: bool | None = None
    is_system: bool | None = None


class TagDefinitionResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    name: str
    description: str | None
    category: TagCategory
    visibility: TagVisibility
    color: str | None
    auto_activity_code_id: uuid.UUID | None
    auto_status_change: str | None
    auto_queue_id: uuid.UUID | None
    triggers: dict[str, Any]
    is_active: bool
    is_system: bool


class TagAssignmentCreate(BaseModel):
    account_id: uuid.UUID
    tag_definition_id: uuid.UUID
    applied_at: datetime
    applied_by_id: uuid.UUID | None = None
    removed_at: datetime | None = None
    removed_by_id: uuid.UUID | None = None
    notes: str | None = None
    tag_metadata: dict[str, Any] = Field(default_factory=dict)


class TagAssignmentUpdate(BaseModel):
    tag_definition_id: uuid.UUID | None = None
    applied_at: datetime | None = None
    applied_by_id: uuid.UUID | None = None
    removed_at: datetime | None = None
    removed_by_id: uuid.UUID | None = None
    notes: str | None = None
    tag_metadata: dict[str, Any] | None = None


class TagAssignmentResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID
    tag_definition_id: uuid.UUID
    applied_at: datetime
    applied_by_id: uuid.UUID | None
    removed_at: datetime | None
    removed_by_id: uuid.UUID | None
    notes: str | None
    tag_metadata: dict[str, Any]
