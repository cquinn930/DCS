"""Skip trace request and result schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.skip_trace import SkipRequestStatus, SkipRequestType, SkipResultType, SkipVendor
from dcs_api.schemas.common import TimestampSchema


class SkipTraceRequestCreate(BaseModel):
    account_id: uuid.UUID
    consumer_id: uuid.UUID
    vendor: SkipVendor
    request_type: SkipRequestType
    status: SkipRequestStatus = SkipRequestStatus.PENDING
    search_parameters: dict[str, Any] = Field(default_factory=dict)
    vendor_reference: str | None = Field(None, max_length=255)
    cost_cents: int = Field(default=0, ge=0)
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    requested_by_id: uuid.UUID | None = None
    error_message: str | None = None


class SkipTraceRequestUpdate(BaseModel):
    vendor: SkipVendor | None = None
    request_type: SkipRequestType | None = None
    status: SkipRequestStatus | None = None
    search_parameters: dict[str, Any] | None = None
    vendor_reference: str | None = Field(None, max_length=255)
    cost_cents: int | None = Field(None, ge=0)
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    requested_by_id: uuid.UUID | None = None
    error_message: str | None = None


class SkipTraceRequestResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID
    consumer_id: uuid.UUID
    vendor: SkipVendor
    request_type: SkipRequestType
    status: SkipRequestStatus
    search_parameters: dict[str, Any]
    vendor_reference: str | None
    cost_cents: int
    submitted_at: datetime | None
    completed_at: datetime | None
    requested_by_id: uuid.UUID | None
    error_message: str | None


class SkipTraceResultCreate(BaseModel):
    request_id: uuid.UUID
    result_type: SkipResultType
    confidence_score: int | None = Field(None, ge=0, le=100)
    data: dict[str, Any] = Field(default_factory=dict)
    is_applied: bool = False
    applied_at: datetime | None = None
    applied_by_id: uuid.UUID | None = None


class SkipTraceResultUpdate(BaseModel):
    result_type: SkipResultType | None = None
    confidence_score: int | None = Field(None, ge=0, le=100)
    data: dict[str, Any] | None = None
    is_applied: bool | None = None
    applied_at: datetime | None = None
    applied_by_id: uuid.UUID | None = None


class SkipTraceResultResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    request_id: uuid.UUID
    result_type: SkipResultType
    confidence_score: int | None
    data: dict[str, Any]
    is_applied: bool
    applied_at: datetime | None
    applied_by_id: uuid.UUID | None
