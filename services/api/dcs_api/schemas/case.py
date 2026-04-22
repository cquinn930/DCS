"""Collection case workflow schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.account import CaseStatus
from dcs_api.schemas.common import TimestampSchema


class CaseCreate(BaseModel):
    account_id: uuid.UUID
    assigned_to_id: uuid.UUID | None = None
    status: CaseStatus = CaseStatus.NEW
    priority: int = Field(default=5, ge=1, le=10)
    workflow_state: dict[str, Any] = Field(default_factory=dict)
    next_action_date: datetime | None = None
    notes: str | None = None


class CaseUpdate(BaseModel):
    assigned_to_id: uuid.UUID | None = None
    status: CaseStatus | None = None
    priority: int | None = Field(None, ge=1, le=10)
    workflow_state: dict[str, Any] | None = None
    next_action_date: datetime | None = None
    notes: str | None = None


class CaseAssignRequest(BaseModel):
    assigned_to_id: uuid.UUID


class CaseStatusUpdateRequest(BaseModel):
    status: CaseStatus


class CaseBulkStatusRequest(BaseModel):
    case_ids: list[uuid.UUID] = Field(..., min_length=1)
    status: CaseStatus


class CaseResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID
    assigned_to_id: uuid.UUID | None
    status: CaseStatus
    priority: int
    workflow_state: dict[str, Any]
    next_action_date: datetime | None
    notes: str | None
