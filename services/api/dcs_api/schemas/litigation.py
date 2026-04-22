"""Litigation case schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.litigation import LitigationStatus
from dcs_api.schemas.common import TimestampSchema


class LitigationCaseCreate(BaseModel):
    account_id: uuid.UUID
    court_id: str = Field(..., max_length=100)
    court_name: str = Field(..., max_length=255)
    court_type: str = Field(..., max_length=50)
    docket_number: str | None = Field(None, max_length=100)
    case_number: str | None = Field(None, max_length=100)
    status: LitigationStatus = LitigationStatus.PENDING_FILING
    filed_date: datetime | None = None
    served_date: datetime | None = None
    answer_due_date: datetime | None = None
    trial_date: datetime | None = None
    principal_claimed: int = Field(..., ge=0)
    interest_claimed: int = Field(default=0, ge=0)
    fees_claimed: int = Field(default=0, ge=0)
    costs_claimed: int = Field(default=0, ge=0)
    attorney_name: str | None = Field(None, max_length=255)
    attorney_bar_id: str | None = Field(None, max_length=50)
    notes: str | None = None
    documents: dict[str, Any] = Field(default_factory=dict)
    efiling_submission_id: str | None = Field(None, max_length=255)
    efiling_status: str | None = Field(None, max_length=50)


class LitigationCaseUpdate(BaseModel):
    court_id: str | None = Field(None, max_length=100)
    court_name: str | None = Field(None, max_length=255)
    court_type: str | None = Field(None, max_length=50)
    docket_number: str | None = Field(None, max_length=100)
    case_number: str | None = Field(None, max_length=100)
    status: LitigationStatus | None = None
    filed_date: datetime | None = None
    served_date: datetime | None = None
    answer_due_date: datetime | None = None
    trial_date: datetime | None = None
    principal_claimed: int | None = Field(None, ge=0)
    interest_claimed: int | None = Field(None, ge=0)
    fees_claimed: int | None = Field(None, ge=0)
    costs_claimed: int | None = Field(None, ge=0)
    attorney_name: str | None = Field(None, max_length=255)
    attorney_bar_id: str | None = Field(None, max_length=50)
    notes: str | None = None
    documents: dict[str, Any] | None = None
    efiling_submission_id: str | None = Field(None, max_length=255)
    efiling_status: str | None = Field(None, max_length=50)


class LitigationCaseResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID
    court_id: str
    court_name: str
    court_type: str
    docket_number: str | None
    case_number: str | None
    status: LitigationStatus
    filed_date: datetime | None
    served_date: datetime | None
    answer_due_date: datetime | None
    trial_date: datetime | None
    principal_claimed: int
    interest_claimed: int
    fees_claimed: int
    costs_claimed: int
    attorney_name: str | None
    attorney_bar_id: str | None
    notes: str | None
    documents: dict[str, Any]
    efiling_submission_id: str | None
    efiling_status: str | None
