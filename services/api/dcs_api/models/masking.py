"""Data masking and privacy models.

Provides field-level masking policies that control how sensitive
data (SSN, DOB, bank accounts) is displayed per role.
"""

import uuid
from enum import Enum

from sqlalchemy import (
    Boolean,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from dcs_api.models.base import TenantScopedModel


class MaskType(str, Enum):
    FULL = "full"
    PARTIAL_LAST4 = "partial_last4"
    PARTIAL_FIRST2 = "partial_first2"
    HASH = "hash"
    REDACT = "redact"
    NONE = "none"


class MaskingPolicy(TenantScopedModel):
    """A masking rule for a specific field on a specific entity."""

    __tablename__ = "masking_policies"
    __table_args__ = (
        Index("ix_masking_policy_tenant", "tenant_id"),
        Index("ix_masking_policy_entity_field", "entity_type", "field_name"),
    )

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    mask_type: Mapped[MaskType] = mapped_column(SQLEnum(MaskType), nullable=False)

    mask_character: Mapped[str] = mapped_column(String(1), default="*", nullable=False)
    visible_chars: Mapped[int] = mapped_column(Integer, default=4, nullable=False)

    exempt_roles: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    apply_to_exports: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    apply_to_api: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    apply_to_logs: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
