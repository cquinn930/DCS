"""Attorney/Legal review checklist models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import TenantScopedModel


class ReviewStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReviewItemResult(str, enum.Enum):
    PENDING = "pending"
    PASS = "pass"
    FAIL = "fail"
    NA = "na"


class ReviewTemplate(TenantScopedModel):
    __tablename__ = "review_templates"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    require_all_items: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_complete_on_all_pass: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    items: Mapped[list["ReviewTemplateItem"]] = relationship(back_populates="template", cascade="all, delete-orphan", order_by="ReviewTemplateItem.sort_order")


class ReviewTemplateItem(TenantScopedModel):
    __tablename__ = "review_template_items"

    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("review_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    condition_script: Mapped[str | None] = mapped_column(Text, nullable=True)
    fail_codes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    data_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    template: Mapped["ReviewTemplate"] = relationship(back_populates="items")


class AccountReview(TenantScopedModel):
    __tablename__ = "account_reviews"

    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("review_templates.id", ondelete="CASCADE"), nullable=False)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), default=ReviewStatus.NOT_STARTED, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    overall_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    template: Mapped["ReviewTemplate"] = relationship()
    items: Mapped[list["AccountReviewItem"]] = relationship(back_populates="review", cascade="all, delete-orphan")


class AccountReviewItem(TenantScopedModel):
    __tablename__ = "account_review_items"

    review_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("account_reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    template_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("review_template_items.id", ondelete="CASCADE"), nullable=False)
    result: Mapped[ReviewItemResult] = mapped_column(Enum(ReviewItemResult), default=ReviewItemResult.PENDING, nullable=False)
    fail_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    review: Mapped["AccountReview"] = relationship(back_populates="items")
