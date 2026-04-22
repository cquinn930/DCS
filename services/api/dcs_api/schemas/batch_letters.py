"""Batch letter schemas."""
from __future__ import annotations
import uuid

from pydantic import Field

from dcs_api.schemas.common import BaseSchema, TimestampSchema


class BatchLetterRuleCreate(BaseSchema):
    sort_order: int = 0
    action_code: str = Field(max_length=50)
    document_template_id: uuid.UUID | None = None
    document_template_name: str | None = None
    completion_code: str | None = None
    new_action_code: str | None = None
    delay_days: int = 0
    is_active: bool = True
    condition_script: str | None = None


class BatchLetterRuleResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    config_id: uuid.UUID
    sort_order: int
    action_code: str
    document_template_id: uuid.UUID | None = None
    document_template_name: str | None = None
    completion_code: str | None = None
    new_action_code: str | None = None
    delay_days: int
    is_active: bool
    condition_script: str | None = None


class BatchLetterConfigCreate(BaseSchema):
    name: str = Field(max_length=200)
    description: str | None = None
    is_active: bool = True
    status_filter: dict | None = None
    date_range_type: str | None = None
    selection_criteria: dict | None = None
    rules: list[BatchLetterRuleCreate] = []


class BatchLetterConfigUpdate(BaseSchema):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    status_filter: dict | None = None
    date_range_type: str | None = None
    selection_criteria: dict | None = None


class BatchLetterConfigResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool
    status_filter: dict | None = None
    date_range_type: str | None = None
    selection_criteria: dict | None = None
    rules: list[BatchLetterRuleResponse] = []
