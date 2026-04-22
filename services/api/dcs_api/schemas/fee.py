"""Account fee schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from dcs_api.models.account import FeeType
from dcs_api.schemas.common import TimestampSchema


class FeeCreate(BaseModel):
    account_id: uuid.UUID
    fee_type: FeeType
    amount: int = Field(..., ge=0)
    description: str | None = None
    is_allowed: bool = False
    jurisdiction_validated: bool = False
    validation_rule: str | None = Field(None, max_length=255)
    applied_at: datetime | None = None
    applied_by_id: uuid.UUID | None = None


class FeeApplyRequest(BaseModel):
    account_id: uuid.UUID
    fee_type: FeeType
    amount: int = Field(..., ge=0)
    description: str | None = None


class FeeUpdate(BaseModel):
    description: str | None = None
    is_allowed: bool | None = None
    jurisdiction_validated: bool | None = None
    validation_rule: str | None = Field(None, max_length=255)


class FeeResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID
    fee_type: FeeType
    amount: int
    description: str | None
    is_allowed: bool
    jurisdiction_validated: bool
    validation_rule: str | None
    applied_at: datetime
    applied_by_id: uuid.UUID | None
