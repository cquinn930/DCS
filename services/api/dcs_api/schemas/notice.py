"""Notice and communication record schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from dcs_api.models.account import NoticeStatus, NoticeType
from dcs_api.schemas.common import TimestampSchema


class NoticeCreate(BaseModel):
    account_id: uuid.UUID
    notice_type: NoticeType
    status: NoticeStatus = NoticeStatus.PENDING
    template_id: str = Field(..., max_length=100)
    template_version: str = Field(..., max_length=50)
    channel: str = Field(..., max_length=50)
    recipient: str = Field(..., max_length=500)
    content_hash: str | None = Field(None, max_length=64)
    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    error_message: str | None = None


class NoticeUpdate(BaseModel):
    notice_type: NoticeType | None = None
    status: NoticeStatus | None = None
    template_id: str | None = Field(None, max_length=100)
    template_version: str | None = Field(None, max_length=50)
    channel: str | None = Field(None, max_length=50)
    recipient: str | None = Field(None, max_length=500)
    content_hash: str | None = Field(None, max_length=64)
    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    error_message: str | None = None


class NoticeResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID
    notice_type: NoticeType
    status: NoticeStatus
    template_id: str
    template_version: str
    channel: str
    recipient: str
    content_hash: str | None
    scheduled_at: datetime | None
    sent_at: datetime | None
    delivered_at: datetime | None
    error_message: str | None
