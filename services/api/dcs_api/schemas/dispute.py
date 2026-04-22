"""Dispute schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.account import DisputeReason, DisputeStatus
from dcs_api.schemas.common import TimestampSchema


class DisputeCreate(BaseModel):
    """Create dispute request.

    Non-legal guidance: Filing a dispute triggers legal hold and pauses
    outbound contact per Regulation F requirements.
    """

    account_id: uuid.UUID
    reason: DisputeReason
    description: str | None = Field(None, max_length=5000)
    documents: dict[str, Any] = {}


class DisputeUpdate(BaseModel):
    """Update dispute request."""

    status: DisputeStatus | None = None
    resolution_notes: str | None = Field(None, max_length=5000)


class DisputeResponse(TimestampSchema):
    """Dispute response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID
    status: DisputeStatus
    reason: DisputeReason
    description: str | None = None

    # Timeline (Reg F compliance)
    filed_at: datetime
    response_due_date: datetime
    responded_at: datetime | None = None
    resolved_at: datetime | None = None

    # Resolution
    resolution_notes: str | None = None
    resolved_by_id: uuid.UUID | None = None

    # Documents
    documents: dict[str, Any]
