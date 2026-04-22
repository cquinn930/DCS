"""Condition template models for visual condition editor."""

import enum
import uuid

from sqlalchemy import Boolean, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from dcs_api.models.base import TenantScopedModel


class ConditionCategory(str, enum.Enum):
    WORKFLOW = "workflow"
    DOCUMENT = "document"
    FLASH_MESSAGE = "flash_message"
    REVIEW = "review"
    AUTOMATION = "automation"
    REPORT = "report"
    GENERAL = "general"


class ConditionTemplate(TenantScopedModel):
    __tablename__ = "condition_templates"

    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[ConditionCategory] = mapped_column(Enum(ConditionCategory, name="conditioncategory"), default=ConditionCategory.GENERAL, nullable=False)
    condition_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    condition_script: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    test_account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    last_test_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
