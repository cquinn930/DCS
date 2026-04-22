"""Credit bureau configuration and batch schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.credit_reporting import BureauBatchStatus, BureauRecordStatus, CreditBureau
from dcs_api.schemas.common import TimestampSchema


class BureauConfigCreate(BaseModel):
    bureau: CreditBureau
    subscriber_code: str = Field(..., max_length=20)
    subscriber_name: str = Field(..., max_length=255)
    sic_code: str | None = Field(None, max_length=4)
    portfolio_type: str = Field(default="I", max_length=1)
    account_type: str = Field(default="48", max_length=2)
    suppress_during_dispute: bool = True
    min_balance_to_report: int = Field(default=0, ge=0)
    min_days_delinquent: int = Field(default=0, ge=0)
    reporting_schedule: dict[str, Any] = Field(default_factory=dict)
    field_mapping: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class BureauConfigUpdate(BaseModel):
    bureau: CreditBureau | None = None
    subscriber_code: str | None = Field(None, max_length=20)
    subscriber_name: str | None = Field(None, max_length=255)
    sic_code: str | None = Field(None, max_length=4)
    portfolio_type: str | None = Field(None, max_length=1)
    account_type: str | None = Field(None, max_length=2)
    suppress_during_dispute: bool | None = None
    min_balance_to_report: int | None = Field(None, ge=0)
    min_days_delinquent: int | None = Field(None, ge=0)
    reporting_schedule: dict[str, Any] | None = None
    field_mapping: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class BureauConfigResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    bureau: CreditBureau
    subscriber_code: str
    subscriber_name: str
    sic_code: str | None
    portfolio_type: str
    account_type: str
    suppress_during_dispute: bool
    min_balance_to_report: int
    min_days_delinquent: int
    reporting_schedule: dict[str, Any]
    field_mapping: dict[str, Any]
    config: dict[str, Any]
    is_active: bool


class BureauBatchCreate(BaseModel):
    bureau_config_id: uuid.UUID
    reporting_period: date
    status: BureauBatchStatus = BureauBatchStatus.PENDING
    total_records: int = Field(default=0, ge=0)
    accepted_records: int = Field(default=0, ge=0)
    rejected_records: int = Field(default=0, ge=0)
    suppressed_records: int = Field(default=0, ge=0)
    file_name: str | None = Field(None, max_length=255)
    file_hash: str | None = Field(None, max_length=64)
    filter_criteria: dict[str, Any] = Field(default_factory=dict)
    errors: list[Any] = Field(default_factory=list)
    generated_at: datetime | None = None
    submitted_at: datetime | None = None
    response_received_at: datetime | None = None
    generated_by_id: uuid.UUID | None = None


class BureauBatchUpdate(BaseModel):
    reporting_period: date | None = None
    status: BureauBatchStatus | None = None
    total_records: int | None = Field(None, ge=0)
    accepted_records: int | None = Field(None, ge=0)
    rejected_records: int | None = Field(None, ge=0)
    suppressed_records: int | None = Field(None, ge=0)
    file_name: str | None = Field(None, max_length=255)
    file_hash: str | None = Field(None, max_length=64)
    filter_criteria: dict[str, Any] | None = None
    errors: list[Any] | None = None
    generated_at: datetime | None = None
    submitted_at: datetime | None = None
    response_received_at: datetime | None = None
    generated_by_id: uuid.UUID | None = None


class BureauBatchResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    bureau_config_id: uuid.UUID
    reporting_period: date
    status: BureauBatchStatus
    total_records: int
    accepted_records: int
    rejected_records: int
    suppressed_records: int
    file_name: str | None
    file_hash: str | None
    filter_criteria: dict[str, Any]
    errors: list[Any]
    generated_at: datetime | None
    submitted_at: datetime | None
    response_received_at: datetime | None
    generated_by_id: uuid.UUID | None


class BureauRecordCreate(BaseModel):
    batch_id: uuid.UUID
    account_id: uuid.UUID
    record_status: BureauRecordStatus = BureauRecordStatus.INCLUDED
    reported_balance: int
    account_status_code: str = Field(..., max_length=2)
    payment_rating: str | None = Field(None, max_length=1)
    date_of_first_delinquency: date | None = None
    special_comment: str | None = Field(None, max_length=2)
    raw_segment: str | None = None
    suppression_reason: str | None = Field(None, max_length=255)
    error_details: str | None = None


class BureauRecordUpdate(BaseModel):
    record_status: BureauRecordStatus | None = None
    reported_balance: int | None = None
    account_status_code: str | None = Field(None, max_length=2)
    payment_rating: str | None = Field(None, max_length=1)
    date_of_first_delinquency: date | None = None
    special_comment: str | None = Field(None, max_length=2)
    raw_segment: str | None = None
    suppression_reason: str | None = Field(None, max_length=255)
    error_details: str | None = None


class BureauRecordResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    batch_id: uuid.UUID
    account_id: uuid.UUID
    record_status: BureauRecordStatus
    reported_balance: int
    account_status_code: str
    payment_rating: str | None
    date_of_first_delinquency: date | None
    special_comment: str | None
    raw_segment: str | None
    suppression_reason: str | None
    error_details: str | None
