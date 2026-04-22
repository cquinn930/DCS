"""Trust accounting and bank reconciliation schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.trust import (
    ReconciliationMatchStatus,
    ReconciliationStatus,
    TrustAccountStatus,
    TrustAccountType,
    TrustTransactionType,
)
from dcs_api.schemas.common import TimestampSchema


class TrustAccountCreate(BaseModel):
    name: str = Field(..., max_length=255)
    account_type: TrustAccountType
    status: TrustAccountStatus = TrustAccountStatus.ACTIVE
    bank_name: str = Field(..., max_length=255)
    account_number_last4: str = Field(..., min_length=4, max_length=4)
    routing_number_last4: str | None = Field(None, min_length=4, max_length=4)
    current_balance: int = 0
    linked_account_id: uuid.UUID | None = None
    allow_overdraft: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class TrustAccountUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    account_type: TrustAccountType | None = None
    status: TrustAccountStatus | None = None
    bank_name: str | None = Field(None, max_length=255)
    account_number_last4: str | None = Field(None, min_length=4, max_length=4)
    routing_number_last4: str | None = Field(None, min_length=4, max_length=4)
    current_balance: int | None = None
    linked_account_id: uuid.UUID | None = None
    allow_overdraft: bool | None = None
    config: dict[str, Any] | None = None


class TrustAccountResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    account_type: TrustAccountType
    status: TrustAccountStatus
    bank_name: str
    account_number_last4: str
    routing_number_last4: str | None
    current_balance: int
    linked_account_id: uuid.UUID | None
    allow_overdraft: bool
    config: dict[str, Any]


class TrustTransactionCreate(BaseModel):
    trust_account_id: uuid.UUID
    transaction_type: TrustTransactionType
    amount: int
    running_balance: int
    reference_number: str | None = Field(None, max_length=100)
    check_number: str | None = Field(None, max_length=50)
    payee: str | None = Field(None, max_length=255)
    memo: str | None = None
    account_id: uuid.UUID | None = None
    payment_id: uuid.UUID | None = None
    linked_transaction_id: uuid.UUID | None = None
    transaction_date: datetime
    posted_by_id: uuid.UUID | None = None
    is_reconciled: bool = False


class TrustTransactionUpdate(BaseModel):
    transaction_type: TrustTransactionType | None = None
    amount: int | None = None
    running_balance: int | None = None
    reference_number: str | None = Field(None, max_length=100)
    check_number: str | None = Field(None, max_length=50)
    payee: str | None = Field(None, max_length=255)
    memo: str | None = None
    account_id: uuid.UUID | None = None
    payment_id: uuid.UUID | None = None
    linked_transaction_id: uuid.UUID | None = None
    transaction_date: datetime | None = None
    posted_by_id: uuid.UUID | None = None
    is_reconciled: bool | None = None


class TrustTransactionResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    trust_account_id: uuid.UUID
    transaction_type: TrustTransactionType
    amount: int
    running_balance: int
    reference_number: str | None
    check_number: str | None
    payee: str | None
    memo: str | None
    account_id: uuid.UUID | None
    payment_id: uuid.UUID | None
    linked_transaction_id: uuid.UUID | None
    transaction_date: datetime
    posted_by_id: uuid.UUID | None
    is_reconciled: bool


class BankReconciliationCreate(BaseModel):
    trust_account_id: uuid.UUID
    period_start: date
    period_end: date
    statement_balance: int
    book_balance: int
    adjusted_balance: int | None = None
    difference: int = 0
    status: ReconciliationStatus = ReconciliationStatus.DRAFT
    reconciled_by_id: uuid.UUID | None = None
    approved_by_id: uuid.UUID | None = None
    completed_at: datetime | None = None
    notes: str | None = None
    import_config: dict[str, Any] = Field(default_factory=dict)


class BankReconciliationUpdate(BaseModel):
    period_start: date | None = None
    period_end: date | None = None
    statement_balance: int | None = None
    book_balance: int | None = None
    adjusted_balance: int | None = None
    difference: int | None = None
    status: ReconciliationStatus | None = None
    reconciled_by_id: uuid.UUID | None = None
    approved_by_id: uuid.UUID | None = None
    completed_at: datetime | None = None
    notes: str | None = None
    import_config: dict[str, Any] | None = None


class BankReconciliationResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    trust_account_id: uuid.UUID
    period_start: date
    period_end: date
    statement_balance: int
    book_balance: int
    adjusted_balance: int | None
    difference: int
    status: ReconciliationStatus
    reconciled_by_id: uuid.UUID | None
    approved_by_id: uuid.UUID | None
    completed_at: datetime | None
    notes: str | None
    import_config: dict[str, Any]


class ReconciliationItemCreate(BaseModel):
    reconciliation_id: uuid.UUID
    match_status: ReconciliationMatchStatus
    statement_amount: int | None = None
    statement_date: date | None = None
    statement_reference: str | None = Field(None, max_length=255)
    statement_description: str | None = Field(None, max_length=500)
    book_transaction_id: uuid.UUID | None = None
    book_amount: int | None = None
    difference: int = 0
    notes: str | None = None


class ReconciliationItemUpdate(BaseModel):
    match_status: ReconciliationMatchStatus | None = None
    statement_amount: int | None = None
    statement_date: date | None = None
    statement_reference: str | None = Field(None, max_length=255)
    statement_description: str | None = Field(None, max_length=500)
    book_transaction_id: uuid.UUID | None = None
    book_amount: int | None = None
    difference: int | None = None
    notes: str | None = None


class ReconciliationItemResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    reconciliation_id: uuid.UUID
    match_status: ReconciliationMatchStatus
    statement_amount: int | None
    statement_date: date | None
    statement_reference: str | None
    statement_description: str | None
    book_transaction_id: uuid.UUID | None
    book_amount: int | None
    difference: int
    notes: str | None
