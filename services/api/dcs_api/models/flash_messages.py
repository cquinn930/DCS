"""Flash message / account alert models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import TenantScopedModel


class FlashPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FlashScope(str, enum.Enum):
    ACCOUNT = "account"
    CONSUMER = "consumer"
    CLIENT = "client"


class FlashMessageTemplate(TenantScopedModel):
    __tablename__ = "flash_message_templates"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[FlashPriority] = mapped_column(Enum(FlashPriority), default=FlashPriority.MEDIUM, nullable=False)
    scope: Mapped[FlashScope] = mapped_column(Enum(FlashScope), default=FlashScope.ACCOUNT, nullable=False)
    condition_script: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_apply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    require_acknowledgment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    display_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class AccountFlashMessage(TenantScopedModel):
    __tablename__ = "account_flash_messages"

    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("flash_message_templates.id", ondelete="SET NULL"), nullable=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[FlashPriority] = mapped_column(Enum(FlashPriority), default=FlashPriority.MEDIUM, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)

    template: Mapped["FlashMessageTemplate | None"] = relationship()
