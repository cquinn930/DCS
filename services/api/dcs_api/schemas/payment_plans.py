"""Payment plan schemas."""
from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from dcs_api.schemas.common import BaseSchema, TimestampSchema


class PaymentPlanCreate(BaseSchema):
    account_id: uuid.UUID
    consumer_id: uuid.UUID | None = None
    plan_type: str = "standard"
    total_amount: Decimal
    payment_amount: Decimal
    frequency: str = "monthly"
    total_payments: int
    start_date: date
    is_settlement: bool = False
    settlement_amount: Decimal | None = None
    settlement_percentage: Decimal | None = None
    original_balance: Decimal | None = None
    pif_tolerance: Decimal = Decimal("0")
    max_months: int | None = None
    auto_post: bool = False
    payment_method: str | None = None
    notes: str | None = None


class PaymentPlanUpdate(BaseSchema):
    status: str | None = None
    payment_amount: Decimal | None = None
    next_payment_date: date | None = None
    auto_post: bool | None = None
    payment_method: str | None = None
    notes: str | None = None
    default_reason: str | None = None


class PaymentPlanResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID
    consumer_id: uuid.UUID | None = None
    plan_type: str
    status: str
    total_amount: Decimal
    payment_amount: Decimal
    frequency: str
    total_payments: int
    payments_made: int
    payments_remaining: int
    amount_paid: Decimal
    balance_remaining: Decimal
    start_date: date
    next_payment_date: date | None = None
    end_date: date | None = None
    is_settlement: bool
    settlement_amount: Decimal | None = None
    settlement_percentage: Decimal | None = None
    original_balance: Decimal | None = None
    pif_tolerance: Decimal
    max_months: int | None = None
    auto_post: bool
    payment_method: str | None = None
    notes: str | None = None
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    defaulted_at: datetime | None = None
    default_reason: str | None = None
    amortization_schedule: dict | None = None
    projection_data: dict | None = None


class ScheduledPaymentResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    plan_id: uuid.UUID
    payment_number: int
    due_date: date
    amount_due: Decimal
    amount_paid: Decimal
    principal_portion: Decimal | None = None
    interest_portion: Decimal | None = None
    fee_portion: Decimal | None = None
    is_paid: bool
    paid_date: date | None = None
    payment_id: uuid.UUID | None = None
    is_late: bool
    notes: str | None = None
