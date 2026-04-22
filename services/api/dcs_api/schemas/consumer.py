"""Consumer schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.consumer import ConsentChannel, ConsentStatus, ContactType
from dcs_api.schemas.common import TimestampSchema


class ContactMethodCreate(BaseModel):
    """Create contact method request."""

    contact_type: ContactType
    value: str = Field(..., max_length=500)
    is_primary: bool = False
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = Field(None, max_length=2)
    postal_code: str | None = None
    country: str = "US"


class ContactMethodResponse(TimestampSchema):
    """Contact method response."""

    id: uuid.UUID
    contact_type: ContactType
    value: str
    is_primary: bool
    is_valid: bool
    is_suppressed: bool


class ConsumerCreate(BaseModel):
    """Create consumer request."""

    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    suffix: str | None = Field(None, max_length=20)
    ssn_last_four: str | None = Field(None, min_length=4, max_length=4)
    date_of_birth: datetime | None = None
    language_preference: str = Field(default="en", max_length=5)
    timezone: str = Field(default="America/New_York", max_length=50)
    external_id: str | None = None
    contact_methods: list[ContactMethodCreate] = []
    extra_data: dict[str, Any] = {}


class ConsumerUpdate(BaseModel):
    """Update consumer request."""

    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    suffix: str | None = Field(None, max_length=20)
    language_preference: str | None = None
    timezone: str | None = None
    is_represented: bool | None = None
    attorney_name: str | None = None
    attorney_contact: str | None = None
    extra_data: dict[str, Any] | None = None


class ConsumerResponse(TimestampSchema):
    """Consumer response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    first_name: str
    last_name: str
    middle_name: str | None = None
    suffix: str | None = None
    ssn_last_four: str | None = None
    date_of_birth: datetime | None = None
    language_preference: str
    timezone: str
    is_deceased: bool
    is_represented: bool
    attorney_name: str | None = None
    legal_hold: bool
    legal_hold_reason: str | None = None
    external_id: str | None = None
    contact_methods: list[ContactMethodResponse] = []


class ConsentCreate(BaseModel):
    """Create consent record request."""

    consumer_id: uuid.UUID
    contact_method_id: uuid.UUID | None = None
    channel: ConsentChannel
    granted_source: str = Field(..., max_length=255)
    scope_value: str | None = Field(None, max_length=500)


class ConsentResponse(TimestampSchema):
    """Consent response."""

    id: uuid.UUID
    consumer_id: uuid.UUID
    channel: ConsentChannel
    status: ConsentStatus
    granted_at: datetime
    granted_source: str
    scope_value: str | None = None
    revoked_at: datetime | None = None
    expires_at: datetime | None = None
