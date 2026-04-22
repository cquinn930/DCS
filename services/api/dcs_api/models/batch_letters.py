"""Batch letter processing by action code models."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import TenantScopedModel


class BatchLetterConfig(TenantScopedModel):
    __tablename__ = "batch_letter_configs"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status_filter: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    date_range_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    selection_criteria: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    rules: Mapped[list["BatchLetterRule"]] = relationship(back_populates="config", cascade="all, delete-orphan", order_by="BatchLetterRule.sort_order")


class BatchLetterRule(TenantScopedModel):
    __tablename__ = "batch_letter_rules"

    config_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("batch_letter_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    action_code: Mapped[str] = mapped_column(String(50), nullable=False)
    document_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    document_template_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    completion_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_action_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    delay_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    condition_script: Mapped[str | None] = mapped_column(Text, nullable=True)

    config: Mapped["BatchLetterConfig"] = relationship(back_populates="rules")
