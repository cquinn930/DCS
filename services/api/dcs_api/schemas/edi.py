"""Data exchange (EDI) format, partner, and batch schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.edi import ExchangeBatchStatus, ExchangeDirection, ExchangeFormatType
from dcs_api.schemas.common import TimestampSchema


class DataExchangeFormatCreate(BaseModel):
    code: str = Field(..., max_length=30)
    name: str = Field(..., max_length=255)
    description: str | None = None
    version: str = Field(default="1.0", max_length=20)
    direction: ExchangeDirection
    format_type: ExchangeFormatType
    record_layouts: dict[str, Any] = Field(default_factory=dict)
    field_mappings: dict[str, Any] = Field(default_factory=dict)
    header_layout: dict[str, Any] = Field(default_factory=dict)
    trailer_layout: dict[str, Any] = Field(default_factory=dict)
    validation_rules: dict[str, Any] = Field(default_factory=dict)
    transform_rules: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    is_system: bool = False


class DataExchangeFormatUpdate(BaseModel):
    code: str | None = Field(None, max_length=30)
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    version: str | None = Field(None, max_length=20)
    direction: ExchangeDirection | None = None
    format_type: ExchangeFormatType | None = None
    record_layouts: dict[str, Any] | None = None
    field_mappings: dict[str, Any] | None = None
    header_layout: dict[str, Any] | None = None
    trailer_layout: dict[str, Any] | None = None
    validation_rules: dict[str, Any] | None = None
    transform_rules: dict[str, Any] | None = None
    is_active: bool | None = None
    is_system: bool | None = None


class DataExchangeFormatResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    name: str
    description: str | None
    version: str
    direction: ExchangeDirection
    format_type: ExchangeFormatType
    record_layouts: dict[str, Any]
    field_mappings: dict[str, Any]
    header_layout: dict[str, Any]
    trailer_layout: dict[str, Any]
    validation_rules: dict[str, Any]
    transform_rules: dict[str, Any]
    is_active: bool
    is_system: bool


class DataExchangePartnerCreate(BaseModel):
    name: str = Field(..., max_length=255)
    partner_code: str = Field(..., max_length=30)
    exchange_format_id: uuid.UUID
    contact_name: str | None = Field(None, max_length=255)
    contact_email: str | None = Field(None, max_length=320)
    connection_config: dict[str, Any] = Field(default_factory=dict)
    partner_settings: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class DataExchangePartnerUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    partner_code: str | None = Field(None, max_length=30)
    exchange_format_id: uuid.UUID | None = None
    contact_name: str | None = Field(None, max_length=255)
    contact_email: str | None = Field(None, max_length=320)
    connection_config: dict[str, Any] | None = None
    partner_settings: dict[str, Any] | None = None
    is_active: bool | None = None


class DataExchangePartnerResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    partner_code: str
    exchange_format_id: uuid.UUID
    contact_name: str | None
    contact_email: str | None
    connection_config: dict[str, Any]
    partner_settings: dict[str, Any]
    is_active: bool


class DataExchangeBatchCreate(BaseModel):
    partner_id: uuid.UUID
    direction: ExchangeDirection
    status: ExchangeBatchStatus = ExchangeBatchStatus.PENDING
    file_name: str | None = Field(None, max_length=255)
    file_hash: str | None = Field(None, max_length=64)
    total_records: int = Field(default=0, ge=0)
    processed_records: int = Field(default=0, ge=0)
    error_records: int = Field(default=0, ge=0)
    new_accounts_created: int = Field(default=0, ge=0)
    accounts_updated: int = Field(default=0, ge=0)
    errors: list[Any] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    processed_by_id: uuid.UUID | None = None


class DataExchangeBatchUpdate(BaseModel):
    direction: ExchangeDirection | None = None
    status: ExchangeBatchStatus | None = None
    file_name: str | None = Field(None, max_length=255)
    file_hash: str | None = Field(None, max_length=64)
    total_records: int | None = Field(None, ge=0)
    processed_records: int | None = Field(None, ge=0)
    error_records: int | None = Field(None, ge=0)
    new_accounts_created: int | None = Field(None, ge=0)
    accounts_updated: int | None = Field(None, ge=0)
    errors: list[Any] | None = None
    summary: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    processed_by_id: uuid.UUID | None = None


class DataExchangeBatchResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    partner_id: uuid.UUID
    direction: ExchangeDirection
    status: ExchangeBatchStatus
    file_name: str | None
    file_hash: str | None
    total_records: int
    processed_records: int
    error_records: int
    new_accounts_created: int
    accounts_updated: int
    errors: list[Any]
    summary: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    processed_by_id: uuid.UUID | None
