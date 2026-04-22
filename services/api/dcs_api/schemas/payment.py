"""Payment schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.account import AllocationTarget, PaymentMethod, PaymentStatus
from dcs_api.schemas.common import TimestampSchema


class PaymentCreate(BaseModel):
    """Create payment request.

    All amounts in cents. Payments are processed via Tratta tokenization.
    """

    account_id: uuid.UUID
    amount: int = Field(..., gt=0)  # cents
    method: PaymentMethod
    processor_token: str | None = None  # Tratta token
    source: str = Field(..., max_length=100)  # portal, phone, mail


class PaymentAllocationResponse(BaseModel):
    """Payment allocation breakdown."""

    target: AllocationTarget
    amount: int  # cents
    order: int


class PaymentResponse(TimestampSchema):
    """Payment response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID
    amount: int  # cents
    method: PaymentMethod
    status: PaymentStatus
    processor_reference: str | None = None
    received_at: datetime
    processed_at: datetime | None = None
    source: str
    allocations: list[PaymentAllocationResponse] = []
