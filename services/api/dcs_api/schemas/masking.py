"""Field masking policy schemas."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.masking import MaskType
from dcs_api.schemas.common import TimestampSchema


class MaskingPolicyCreate(BaseModel):
    entity_type: str = Field(..., max_length=50)
    field_name: str = Field(..., max_length=100)
    mask_type: MaskType
    mask_character: str = Field(default="*", max_length=1, min_length=1)
    visible_chars: int = Field(default=4, ge=0)
    exempt_roles: list[Any] = Field(default_factory=list)
    apply_to_exports: bool = True
    apply_to_api: bool = True
    apply_to_logs: bool = True
    is_active: bool = True
    description: str | None = None


class MaskingPolicyUpdate(BaseModel):
    entity_type: str | None = Field(None, max_length=50)
    field_name: str | None = Field(None, max_length=100)
    mask_type: MaskType | None = None
    mask_character: str | None = Field(None, max_length=1, min_length=1)
    visible_chars: int | None = Field(None, ge=0)
    exempt_roles: list[Any] | None = None
    apply_to_exports: bool | None = None
    apply_to_api: bool | None = None
    apply_to_logs: bool | None = None
    is_active: bool | None = None
    description: str | None = None


class MaskingPolicyResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_type: str
    field_name: str
    mask_type: MaskType
    mask_character: str
    visible_chars: int
    exempt_roles: list[Any]
    apply_to_exports: bool
    apply_to_api: bool
    apply_to_logs: bool
    is_active: bool
    description: str | None
