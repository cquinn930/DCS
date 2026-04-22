"""Tenant schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.tenant import BusinessModel, TenantStatus
from dcs_api.schemas.common import BaseSchema, TimestampSchema


class TenantCreate(BaseModel):
    """Create tenant request."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=63, pattern=r"^[a-z0-9-]+$")
    business_model: BusinessModel = BusinessModel.SUBSCRIPTION
    default_jurisdiction: str = Field(default="NJ", min_length=2, max_length=2)
    retention_years: int = Field(default=7, ge=7)  # Minimum 7 years


class TenantUpdate(BaseModel):
    """Update tenant request."""

    name: str | None = Field(None, min_length=1, max_length=255)
    business_model: BusinessModel | None = None
    default_jurisdiction: str | None = Field(None, min_length=2, max_length=2)
    retention_years: int | None = Field(None, ge=7)
    license_number: str | None = None
    bond_amount: int | None = None  # cents
    license_expiry: datetime | None = None
    settings: dict[str, Any] | None = None


class TenantResponse(TimestampSchema):
    """Tenant response."""

    id: uuid.UUID
    name: str
    slug: str
    status: TenantStatus
    business_model: BusinessModel
    default_jurisdiction: str
    retention_years: int
    license_number: str | None = None
    bond_amount: int | None = None
    license_expiry: datetime | None = None
    settings: dict[str, Any]
