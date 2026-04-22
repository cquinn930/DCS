"""Condition template schemas."""
from __future__ import annotations
import uuid

from pydantic import Field

from dcs_api.schemas.common import BaseSchema, TimestampSchema


class ConditionTemplateCreate(BaseSchema):
    code: str = Field(max_length=50)
    name: str = Field(max_length=200)
    description: str | None = None
    category: str = "general"
    condition_json: dict
    condition_script: str | None = None
    is_active: bool = True
    test_account_id: uuid.UUID | None = None


class ConditionTemplateUpdate(BaseSchema):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    condition_json: dict | None = None
    condition_script: str | None = None
    is_active: bool | None = None
    test_account_id: uuid.UUID | None = None


class ConditionTemplateResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    category: str
    condition_json: dict
    condition_script: str | None = None
    is_active: bool
    version: int
    test_account_id: uuid.UUID | None = None
    last_test_result: dict | None = None


class ConditionConvertRequest(BaseSchema):
    condition_json: dict


class ConditionConvertResponse(BaseSchema):
    condition_script: str
    valid: bool
    errors: list[str] = []
