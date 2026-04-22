"""Court management schemas."""
from __future__ import annotations
import uuid
from decimal import Decimal

from pydantic import Field

from dcs_api.schemas.common import BaseSchema, TimestampSchema


class CourtCreate(BaseSchema):
    code: str = Field(max_length=50)
    name: str = Field(max_length=300)
    court_type: str | None = None
    jurisdiction: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    county: str | None = None
    phone: str | None = None
    fax: str | None = None
    email: str | None = None
    website: str | None = None
    filing_fee_default: Decimal | None = None
    service_fee_default: Decimal | None = None
    is_active: bool = True
    notes: str | None = None
    settings: dict | None = None


class CourtUpdate(BaseSchema):
    name: str | None = None
    court_type: str | None = None
    jurisdiction: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    county: str | None = None
    phone: str | None = None
    fax: str | None = None
    email: str | None = None
    website: str | None = None
    filing_fee_default: Decimal | None = None
    service_fee_default: Decimal | None = None
    is_active: bool | None = None
    notes: str | None = None
    settings: dict | None = None


class CourtResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    name: str
    court_type: str | None = None
    jurisdiction: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    county: str | None = None
    phone: str | None = None
    fax: str | None = None
    email: str | None = None
    website: str | None = None
    filing_fee_default: Decimal | None = None
    service_fee_default: Decimal | None = None
    is_active: bool
    notes: str | None = None
    settings: dict | None = None


class CourtCostOverrideCreate(BaseSchema):
    court_id: uuid.UUID
    cost_type: str = Field(max_length=50)
    min_balance: Decimal = Decimal("0")
    max_balance: Decimal | None = None
    cost_amount: Decimal
    description: str | None = None
    is_active: bool = True


class CourtCostOverrideResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    court_id: uuid.UUID
    cost_type: str
    min_balance: Decimal
    max_balance: Decimal | None = None
    cost_amount: Decimal
    description: str | None = None
    is_active: bool


class CourtRepresentativeCreate(BaseSchema):
    court_id: uuid.UUID
    name: str = Field(max_length=200)
    title: str | None = None
    firm: str | None = None
    role: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool = True
    notes: str | None = None


class CourtRepresentativeResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    court_id: uuid.UUID
    name: str
    title: str | None = None
    firm: str | None = None
    role: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool
    notes: str | None = None
