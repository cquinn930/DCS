"""Account schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.account import AccountStatus, DebtType, InterestType
from dcs_api.schemas.common import TimestampSchema


class DebtInstrumentCreate(BaseModel):
    """Create debt instrument request."""

    instrument_type: str = Field(..., max_length=100)
    interest_rate: float = Field(..., ge=0, le=100)
    interest_type: InterestType = InterestType.SIMPLE
    contract_date: datetime | None = None
    terms: dict[str, Any] = {}


class AccountCreate(BaseModel):
    """Create account request."""

    consumer_id: uuid.UUID
    account_reference: str = Field(..., max_length=100)
    original_creditor: str = Field(..., max_length=255)
    current_creditor: str | None = None
    client_account_number: str | None = None
    debt_type: DebtType = DebtType.CONSUMER
    jurisdiction: str = Field(default="NJ", min_length=2, max_length=2)

    # Balances in cents
    original_principal: int = Field(..., gt=0)
    current_principal: int = Field(..., gt=0)
    current_interest: int = Field(default=0, ge=0)
    current_fees: int = Field(default=0, ge=0)

    # Dates
    date_of_service: datetime | None = None
    date_of_first_delinquency: datetime | None = None
    date_placed: datetime

    # Optional debt instrument
    debt_instrument: DebtInstrumentCreate | None = None
    extra_data: dict[str, Any] = {}


class AccountUpdate(BaseModel):
    """Update account request."""

    status: AccountStatus | None = None
    current_creditor: str | None = None
    current_principal: int | None = Field(None, ge=0)
    current_interest: int | None = Field(None, ge=0)
    current_fees: int | None = Field(None, ge=0)
    extra_data: dict[str, Any] | None = None


class DebtInstrumentResponse(TimestampSchema):
    """Debt instrument response."""

    id: uuid.UUID
    instrument_type: str
    interest_rate: float
    interest_type: InterestType
    contract_date: datetime | None = None
    terms: dict[str, Any]


class AccountResponse(TimestampSchema):
    """Account response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    consumer_id: uuid.UUID
    account_reference: str
    original_creditor: str
    current_creditor: str | None = None
    client_account_number: str | None = None
    status: AccountStatus
    debt_type: DebtType
    jurisdiction: str

    # Balances in cents
    original_principal: int
    current_principal: int
    current_interest: int
    current_fees: int
    total_balance: int

    # Dates
    date_of_service: datetime | None = None
    date_of_first_delinquency: datetime | None = None
    date_placed: datetime
    statute_expiry_date: datetime | None = None

    # Compliance
    legal_hold: bool
    legal_hold_reason: str | None = None
    validation_notice_sent: bool
    validation_notice_date: datetime | None = None

    # Related
    debt_instrument: DebtInstrumentResponse | None = None
    extra_data: dict[str, Any]
