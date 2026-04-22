"""Document template and generation schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.documents import (
    DeliveryChannel,
    GenerationStatus,
    TemplateCategory,
    TemplateFormat,
)
from dcs_api.schemas.common import TimestampSchema


class DocumentTemplateCreate(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    description: str | None = None
    category: TemplateCategory = TemplateCategory.GENERAL
    template_format: TemplateFormat = TemplateFormat.HTML
    subject: str | None = Field(None, max_length=500)
    body: str
    header: str | None = None
    footer: str | None = None
    merge_fields: dict[str, Any] = Field(default_factory=dict)
    pre_merge_script_id: uuid.UUID | None = None
    version: int = Field(default=1, ge=1)
    is_active: bool = True
    is_system: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class DocumentTemplateUpdate(BaseModel):
    code: str | None = Field(None, max_length=50)
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    category: TemplateCategory | None = None
    template_format: TemplateFormat | None = None
    subject: str | None = Field(None, max_length=500)
    body: str | None = None
    header: str | None = None
    footer: str | None = None
    merge_fields: dict[str, Any] | None = None
    pre_merge_script_id: uuid.UUID | None = None
    version: int | None = Field(None, ge=1)
    is_active: bool | None = None
    is_system: bool | None = None
    config: dict[str, Any] | None = None


class DocumentTemplateResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    name: str
    description: str | None
    category: TemplateCategory
    template_format: TemplateFormat
    subject: str | None
    body: str
    header: str | None
    footer: str | None
    merge_fields: dict[str, Any]
    pre_merge_script_id: uuid.UUID | None
    version: int
    is_active: bool
    is_system: bool
    config: dict[str, Any]


class DocumentGenerationCreate(BaseModel):
    template_id: uuid.UUID
    account_id: uuid.UUID
    status: GenerationStatus = GenerationStatus.PENDING
    channel: DeliveryChannel = DeliveryChannel.PRINT
    rendered_subject: str | None = Field(None, max_length=500)
    rendered_body: str | None = None
    content_hash: str | None = Field(None, max_length=64)
    merge_data: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    error_message: str | None = None
    generated_by_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None
    activity_entry_id: uuid.UUID | None = None


class DocumentGenerationUpdate(BaseModel):
    status: GenerationStatus | None = None
    channel: DeliveryChannel | None = None
    rendered_subject: str | None = Field(None, max_length=500)
    rendered_body: str | None = None
    content_hash: str | None = Field(None, max_length=64)
    merge_data: dict[str, Any] | None = None
    generated_at: datetime | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    error_message: str | None = None
    generated_by_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None
    activity_entry_id: uuid.UUID | None = None


class DocumentGenerationResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    template_id: uuid.UUID
    account_id: uuid.UUID
    status: GenerationStatus
    channel: DeliveryChannel
    rendered_subject: str | None
    rendered_body: str | None
    content_hash: str | None
    merge_data: dict[str, Any]
    generated_at: datetime | None
    sent_at: datetime | None
    delivered_at: datetime | None
    error_message: str | None
    generated_by_id: uuid.UUID | None
    batch_id: uuid.UUID | None
    activity_entry_id: uuid.UUID | None


class DocumentBatchCreate(BaseModel):
    name: str = Field(..., max_length=255)
    template_id: uuid.UUID
    filter_criteria: dict[str, Any] = Field(default_factory=dict)
    total_accounts: int = Field(default=0, ge=0)
    completed_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    status: str = Field(default="pending", max_length=20)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    started_by_id: uuid.UUID | None = None


class DocumentBatchUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    template_id: uuid.UUID | None = None
    filter_criteria: dict[str, Any] | None = None
    total_accounts: int | None = Field(None, ge=0)
    completed_count: int | None = Field(None, ge=0)
    failed_count: int | None = Field(None, ge=0)
    status: str | None = Field(None, max_length=20)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    started_by_id: uuid.UUID | None = None


class DocumentBatchResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    template_id: uuid.UUID
    filter_criteria: dict[str, Any]
    total_accounts: int
    completed_count: int
    failed_count: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    started_by_id: uuid.UUID | None
