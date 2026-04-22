"""Common schema types."""

import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class TimestampSchema(BaseSchema):
    """Schema with timestamp fields."""

    created_at: datetime
    updated_at: datetime


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class ErrorResponse(BaseModel):
    """Error response schema."""

    detail: str
    type: str
    errors: list[dict] | None = None


class AuditMetadata(BaseModel):
    """Audit metadata for compliance."""

    policy_pack_id: uuid.UUID | None = None
    policy_pack_version: str | None = None
    calculation_version: str | None = None
    source_snapshot_hash: str | None = None
