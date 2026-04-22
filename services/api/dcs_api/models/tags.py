"""Tag system for accounts.

Tags are rich operational metadata that can trigger automation rules,
change statuses, fire activities, and drive reporting filters.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from dcs_api.models.base import TenantScopedModel


class TagCategory(str, Enum):
    STATUS = "status"
    COMPLIANCE = "compliance"
    FINANCIAL = "financial"
    LEGAL = "legal"
    OPERATIONAL = "operational"
    CLIENT = "client"
    SYSTEM = "system"
    CUSTOM = "custom"


class TagVisibility(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"


class TagDefinition(TenantScopedModel):
    """A reusable tag type with optional automation triggers."""

    __tablename__ = "tag_definitions"
    __table_args__ = (
        Index("ix_tag_defs_tenant_code", "tenant_id", "code", unique=True),
    )

    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[TagCategory] = mapped_column(
        SQLEnum(TagCategory), default=TagCategory.CUSTOM, nullable=False
    )
    visibility: Mapped[TagVisibility] = mapped_column(
        SQLEnum(TagVisibility), default=TagVisibility.PUBLIC, nullable=False
    )
    color: Mapped[str | None] = mapped_column(String(7))

    auto_activity_code_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    auto_status_change: Mapped[str | None] = mapped_column(String(30))
    auto_queue_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    triggers: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class TagAssignment(TenantScopedModel):
    """An instance of a tag applied to an account."""

    __tablename__ = "tag_assignments"
    __table_args__ = (
        Index("ix_tag_assign_account", "account_id"),
        Index("ix_tag_assign_tag", "tag_definition_id"),
        Index("ix_tag_assign_unique", "account_id", "tag_definition_id", unique=True),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    tag_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tag_definitions.id"), nullable=False
    )

    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    applied_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    notes: Mapped[str | None] = mapped_column(Text)
    tag_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
