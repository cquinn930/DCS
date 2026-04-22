"""Cost entry, disbursement, and client billing schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.costs import (
    ClientBillingStatus,
    CostStatus,
    CostType,
    DisbursementMethod,
)
from dcs_api.schemas.common import TimestampSchema


class CostEntryCreate(BaseModel):
    account_id: uuid.UUID
    cost_type: CostType
    status: CostStatus = CostStatus.INCURRED
    amount: int
    recovered_amount: int = Field(default=0, ge=0)
    is_recoverable: bool = True
    is_firm_cost: bool = False
    vendor_name: str | None = Field(None, max_length=255)
    vendor_reference: str | None = Field(None, max_length=100)
    description: str | None = None
    incurred_date: datetime
    approved_by_id: uuid.UUID | None = None
    approved_at: datetime | None = None
    trust_account_id: uuid.UUID | None = None


class CostEntryUpdate(BaseModel):
    cost_type: CostType | None = None
    status: CostStatus | None = None
    amount: int | None = None
    recovered_amount: int | None = Field(None, ge=0)
    is_recoverable: bool | None = None
    is_firm_cost: bool | None = None
    vendor_name: str | None = Field(None, max_length=255)
    vendor_reference: str | None = Field(None, max_length=100)
    description: str | None = None
    incurred_date: datetime | None = None
    approved_by_id: uuid.UUID | None = None
    approved_at: datetime | None = None
    trust_account_id: uuid.UUID | None = None


class CostEntryResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID
    cost_type: CostType
    status: CostStatus
    amount: int
    recovered_amount: int
    is_recoverable: bool
    is_firm_cost: bool
    vendor_name: str | None
    vendor_reference: str | None
    description: str | None
    incurred_date: datetime
    approved_by_id: uuid.UUID | None
    approved_at: datetime | None
    trust_account_id: uuid.UUID | None


class CostDisbursementCreate(BaseModel):
    cost_entry_id: uuid.UUID
    amount: int
    method: DisbursementMethod
    check_number: str | None = Field(None, max_length=50)
    reference_number: str | None = Field(None, max_length=100)
    payee: str = Field(..., max_length=255)
    disbursed_at: datetime
    disbursed_by_id: uuid.UUID | None = None
    trust_transaction_id: uuid.UUID | None = None


class CostDisbursementUpdate(BaseModel):
    amount: int | None = None
    method: DisbursementMethod | None = None
    check_number: str | None = Field(None, max_length=50)
    reference_number: str | None = Field(None, max_length=100)
    payee: str | None = Field(None, max_length=255)
    disbursed_at: datetime | None = None
    disbursed_by_id: uuid.UUID | None = None
    trust_transaction_id: uuid.UUID | None = None


class CostDisbursementResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    cost_entry_id: uuid.UUID
    amount: int
    method: DisbursementMethod
    check_number: str | None
    reference_number: str | None
    payee: str
    disbursed_at: datetime
    disbursed_by_id: uuid.UUID | None
    trust_transaction_id: uuid.UUID | None


class CostBillingCreate(BaseModel):
    client_name: str = Field(..., max_length=255)
    client_reference: str | None = Field(None, max_length=100)
    status: ClientBillingStatus = ClientBillingStatus.DRAFT
    total_amount: int
    paid_amount: int = Field(default=0, ge=0)
    line_items: list[Any] = Field(default_factory=list)
    billing_period_start: datetime | None = None
    billing_period_end: datetime | None = None
    sent_at: datetime | None = None
    due_date: datetime | None = None
    paid_at: datetime | None = None
    notes: str | None = None


class CostBillingUpdate(BaseModel):
    client_name: str | None = Field(None, max_length=255)
    client_reference: str | None = Field(None, max_length=100)
    status: ClientBillingStatus | None = None
    total_amount: int | None = None
    paid_amount: int | None = Field(None, ge=0)
    line_items: list[Any] | None = None
    billing_period_start: datetime | None = None
    billing_period_end: datetime | None = None
    sent_at: datetime | None = None
    due_date: datetime | None = None
    paid_at: datetime | None = None
    notes: str | None = None


class CostBillingResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    client_name: str
    client_reference: str | None
    status: ClientBillingStatus
    total_amount: int
    paid_amount: int
    line_items: list[Any]
    billing_period_start: datetime | None
    billing_period_end: datetime | None
    sent_at: datetime | None
    due_date: datetime | None
    paid_at: datetime | None
    notes: str | None
