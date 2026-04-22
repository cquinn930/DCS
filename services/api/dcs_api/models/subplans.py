"""SubPlan models - reusable workflow fragments."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import TenantScopedModel


class SubPlan(TenantScopedModel):
    __tablename__ = "sub_plans"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    steps: Mapped[list["SubPlanStep"]] = relationship(back_populates="sub_plan", cascade="all, delete-orphan", order_by="SubPlanStep.sort_order")


class SubPlanStep(TenantScopedModel):
    __tablename__ = "sub_plan_steps"

    sub_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sub_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    condition_script: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_on_true: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    action_on_false: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    delay_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sub_plan: Mapped["SubPlan"] = relationship(back_populates="steps")
