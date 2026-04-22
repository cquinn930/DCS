"""Legal review checklist schemas."""
from __future__ import annotations
import uuid
from datetime import datetime

from pydantic import Field

from dcs_api.schemas.common import BaseSchema, TimestampSchema


class ReviewTemplateItemCreate(BaseSchema):
    sort_order: int = 0
    label: str = Field(max_length=500)
    description: str | None = None
    is_required: bool = True
    condition_script: str | None = None
    fail_codes: dict | None = None
    data_fields: dict | None = None


class ReviewTemplateItemResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    template_id: uuid.UUID
    sort_order: int
    label: str
    description: str | None = None
    is_required: bool
    condition_script: str | None = None
    fail_codes: dict | None = None
    data_fields: dict | None = None


class ReviewTemplateCreate(BaseSchema):
    name: str = Field(max_length=200)
    description: str | None = None
    category: str | None = None
    is_active: bool = True
    require_all_items: bool = True
    auto_complete_on_all_pass: bool = False
    items: list[ReviewTemplateItemCreate] = []


class ReviewTemplateUpdate(BaseSchema):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    is_active: bool | None = None
    require_all_items: bool | None = None
    auto_complete_on_all_pass: bool | None = None


class ReviewTemplateResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    category: str | None = None
    is_active: bool
    require_all_items: bool
    auto_complete_on_all_pass: bool
    items: list[ReviewTemplateItemResponse] = []


class AccountReviewCreate(BaseSchema):
    account_id: uuid.UUID
    template_id: uuid.UUID


class AccountReviewItemUpdate(BaseSchema):
    result: str
    fail_code: str | None = None
    notes: str | None = None


class AccountReviewResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_id: uuid.UUID
    template_id: uuid.UUID
    reviewer_id: uuid.UUID
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    overall_result: str | None = None
    notes: str | None = None


class AccountReviewItemResponse(TimestampSchema):
    id: uuid.UUID
    review_id: uuid.UUID
    template_item_id: uuid.UUID
    result: str
    fail_code: str | None = None
    notes: str | None = None
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
