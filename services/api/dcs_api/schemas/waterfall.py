"""Payment waterfall and allocation rule schemas."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.models.waterfall import AllocationBucket, CollectionPhase
from dcs_api.schemas.common import TimestampSchema


class PaymentWaterfallCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    jurisdiction: str | None = Field(None, min_length=2, max_length=2)
    is_default: bool = False
    is_active: bool = True
    is_system: bool = False
    overpayment_handling: str = Field(default="refund", max_length=20)
    config: dict[str, Any] = Field(default_factory=dict)


class PaymentWaterfallUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    jurisdiction: str | None = Field(None, min_length=2, max_length=2)
    is_default: bool | None = None
    is_active: bool | None = None
    is_system: bool | None = None
    overpayment_handling: str | None = Field(None, max_length=20)
    config: dict[str, Any] | None = None


class PaymentWaterfallResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    jurisdiction: str | None
    is_default: bool
    is_active: bool
    is_system: bool
    overpayment_handling: str
    config: dict[str, Any]


class WaterfallRuleCreate(BaseModel):
    waterfall_id: uuid.UUID
    phase: CollectionPhase = CollectionPhase.DEFAULT
    bucket: AllocationBucket
    priority: int = Field(..., ge=0)
    max_percentage: int | None = Field(None, ge=0, le=100)
    max_amount: int | None = Field(None, ge=0)
    conditions: dict[str, Any] = Field(default_factory=dict)


class WaterfallRuleUpdate(BaseModel):
    phase: CollectionPhase | None = None
    bucket: AllocationBucket | None = None
    priority: int | None = Field(None, ge=0)
    max_percentage: int | None = Field(None, ge=0, le=100)
    max_amount: int | None = Field(None, ge=0)
    conditions: dict[str, Any] | None = None


class WaterfallRuleResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    waterfall_id: uuid.UUID
    phase: CollectionPhase
    bucket: AllocationBucket
    priority: int
    max_percentage: int | None
    max_amount: int | None
    conditions: dict[str, Any]
