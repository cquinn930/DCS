"""Remittance schemas."""
from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from dcs_api.schemas.common import BaseSchema, TimestampSchema


class RemittanceStatementCreate(BaseSchema):
    client_id: uuid.UUID
    statement_number: str = Field(max_length=50)
    period_start: datetime
    period_end: datetime
    notes: str | None = None
    config: dict | None = None


class RemittanceStatementUpdate(BaseSchema):
    status: str | None = None
    notes: str | None = None
    config: dict | None = None


class RemittanceStatementResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    statement_number: str
    period_start: datetime
    period_end: datetime
    status: str
    total_collected: Decimal
    total_fees: Decimal
    total_costs: Decimal
    total_invoices: Decimal
    net_remittance: Decimal
    trust_balance_before: Decimal
    trust_balance_after: Decimal
    notes: str | None = None
    generated_by: uuid.UUID | None = None
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    finalized_at: datetime | None = None
    sent_at: datetime | None = None
    config: dict | None = None


class RemittanceLineItemCreate(BaseSchema):
    statement_id: uuid.UUID
    account_id: uuid.UUID | None = None
    payment_id: uuid.UUID | None = None
    description: str = Field(max_length=500)
    line_type: str = Field(max_length=50)
    gross_amount: Decimal
    fee_amount: Decimal = Decimal("0")
    cost_amount: Decimal = Decimal("0")
    net_amount: Decimal
    transaction_date: datetime | None = None
    reference_number: str | None = None


class RemittanceLineItemResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    statement_id: uuid.UUID
    account_id: uuid.UUID | None = None
    payment_id: uuid.UUID | None = None
    description: str
    line_type: str
    gross_amount: Decimal
    fee_amount: Decimal
    cost_amount: Decimal
    net_amount: Decimal
    transaction_date: datetime | None = None
    reference_number: str | None = None


class RemittanceConfigCreate(BaseSchema):
    name: str = Field(max_length=200)
    client_id: uuid.UUID | None = None
    include_payments: bool = True
    include_fees: bool = True
    include_costs: bool = True
    include_invoices: bool = True
    include_trust_summary: bool = True
    group_by: str = "account"
    sort_by: str = "date"
    output_format: str = "pdf"
    email_on_finalize: bool = False
    email_recipients: dict | None = None
    template_overrides: dict | None = None


class RemittanceConfigUpdate(BaseSchema):
    name: str | None = None
    include_payments: bool | None = None
    include_fees: bool | None = None
    include_costs: bool | None = None
    include_invoices: bool | None = None
    include_trust_summary: bool | None = None
    group_by: str | None = None
    sort_by: str | None = None
    output_format: str | None = None
    email_on_finalize: bool | None = None
    email_recipients: dict | None = None
    template_overrides: dict | None = None


class RemittanceConfigResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID | None = None
    name: str
    include_payments: bool
    include_fees: bool
    include_costs: bool
    include_invoices: bool
    include_trust_summary: bool
    group_by: str
    sort_by: str
    output_format: str
    email_on_finalize: bool
    email_recipients: dict | None = None
    template_overrides: dict | None = None
