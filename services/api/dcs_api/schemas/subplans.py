"""SubPlan schemas."""
from __future__ import annotations
import uuid

from pydantic import Field

from dcs_api.schemas.common import BaseSchema, TimestampSchema


class SubPlanStepCreate(BaseSchema):
    sort_order: int = 0
    step_type: str = Field(max_length=50)
    name: str = Field(max_length=200)
    description: str | None = None
    condition_script: str | None = None
    action_on_true: dict | None = None
    action_on_false: dict | None = None
    config: dict | None = None
    delay_days: int = 0
    is_active: bool = True


class SubPlanStepResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    sub_plan_id: uuid.UUID
    sort_order: int
    step_type: str
    name: str
    description: str | None = None
    condition_script: str | None = None
    action_on_true: dict | None = None
    action_on_false: dict | None = None
    config: dict | None = None
    delay_days: int
    is_active: bool


class SubPlanCreate(BaseSchema):
    name: str = Field(max_length=200)
    description: str | None = None
    category: str | None = None
    is_active: bool = True
    steps: list[SubPlanStepCreate] = []


class SubPlanUpdate(BaseSchema):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    is_active: bool | None = None


class SubPlanResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    category: str | None = None
    is_active: bool
    version: int
    steps: list[SubPlanStepResponse] = []
