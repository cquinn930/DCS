"""Payment waterfall (collection order) models.

Defines the configurable sequence in which payments are allocated
across interest, principal, fees, and costs — with separate rules
for pre-suit, post-suit, pre-judgment, and post-judgment phases.
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import TenantScopedModel


class AllocationBucket(str, Enum):
    PRINCIPAL = "principal"
    INTEREST = "interest"
    FEES = "fees"
    COSTS = "costs"
    ATTORNEY_FEES = "attorney_fees"
    STATUTORY_FEES = "statutory_fees"
    EXCESS = "excess"


class CollectionPhase(str, Enum):
    PRE_SUIT = "pre_suit"
    POST_SUIT = "post_suit"
    PRE_JUDGMENT = "pre_judgment"
    POST_JUDGMENT = "post_judgment"
    DEFAULT = "default"


class PaymentWaterfall(TenantScopedModel):
    """A named payment allocation strategy for a tenant."""

    __tablename__ = "payment_waterfalls"
    __table_args__ = (
        Index("ix_waterfall_tenant_name", "tenant_id", "name", unique=True),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    jurisdiction: Mapped[str | None] = mapped_column(String(2))

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    overpayment_handling: Mapped[str] = mapped_column(
        String(20), default="refund", nullable=False
    )

    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    rules: Mapped[list["WaterfallRule"]] = relationship(
        "WaterfallRule", back_populates="waterfall",
        order_by="WaterfallRule.phase, WaterfallRule.priority"
    )


class WaterfallRule(TenantScopedModel):
    """A single allocation rule within a waterfall."""

    __tablename__ = "waterfall_rules"
    __table_args__ = (
        Index("ix_waterfall_rule_waterfall", "waterfall_id"),
    )

    waterfall_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_waterfalls.id", ondelete="CASCADE"),
        nullable=False,
    )

    phase: Mapped[CollectionPhase] = mapped_column(
        SQLEnum(CollectionPhase), default=CollectionPhase.DEFAULT, nullable=False
    )
    bucket: Mapped[AllocationBucket] = mapped_column(
        SQLEnum(AllocationBucket), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)

    max_percentage: Mapped[int | None] = mapped_column(Integer)
    max_amount: Mapped[int | None] = mapped_column(Integer)

    conditions: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    waterfall: Mapped["PaymentWaterfall"] = relationship(
        "PaymentWaterfall", back_populates="rules"
    )
