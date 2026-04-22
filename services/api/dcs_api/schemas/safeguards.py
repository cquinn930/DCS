"""Financial safeguard schemas."""
from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from dcs_api.schemas.common import BaseSchema, TimestampSchema


class TransactionLimitCreate(BaseSchema):
    transaction_type: str = Field(max_length=50)
    max_amount: Decimal
    requires_approval_above: Decimal | None = None
    applies_to_role: str | None = None
    is_active: bool = True
    description: str | None = None


class TransactionLimitUpdate(BaseSchema):
    max_amount: Decimal | None = None
    requires_approval_above: Decimal | None = None
    applies_to_role: str | None = None
    is_active: bool | None = None
    description: str | None = None


class TransactionLimitResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    transaction_type: str
    max_amount: Decimal
    requires_approval_above: Decimal | None = None
    applies_to_role: str | None = None
    is_active: bool
    description: str | None = None


class FinancialNoteCreate(BaseSchema):
    account_id: uuid.UUID
    note_text: str
    must_acknowledge: bool = True
    expires_at: datetime | None = None


class FinancialNoteResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID
    note_text: str
    must_acknowledge: bool
    created_by: uuid.UUID
    acknowledged_by: uuid.UUID | None = None
    acknowledged_at: datetime | None = None
    is_active: bool
    expires_at: datetime | None = None


class TemporaryHoldCreate(BaseSchema):
    account_id: uuid.UUID
    reason: str
    hold_type: str = "general"
    block_batch_processing: bool = True
    block_letters: bool = True
    block_credit_reporting: bool = True
    allow_manual_entry: bool = True
    expires_at: datetime | None = None


class TemporaryHoldUpdate(BaseSchema):
    reason: str | None = None
    block_batch_processing: bool | None = None
    block_letters: bool | None = None
    block_credit_reporting: bool | None = None
    allow_manual_entry: bool | None = None
    expires_at: datetime | None = None


class TemporaryHoldResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID
    reason: str
    hold_type: str
    placed_by: uuid.UUID
    block_batch_processing: bool
    block_letters: bool
    block_credit_reporting: bool
    allow_manual_entry: bool
    expires_at: datetime | None = None
    released_by: uuid.UUID | None = None
    released_at: datetime | None = None
    is_active: bool
