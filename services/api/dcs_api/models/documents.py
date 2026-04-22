"""Document template and generation models.

Handles letter/notice generation with merge field substitution,
batch document runs, and delivery tracking.
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
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import TenantScopedModel


class TemplateCategory(str, Enum):
    VALIDATION_NOTICE = "validation_notice"
    DEMAND_LETTER = "demand_letter"
    SETTLEMENT_OFFER = "settlement_offer"
    PAYMENT_CONFIRMATION = "payment_confirmation"
    DISPUTE_RESPONSE = "dispute_response"
    COURT_FILING = "court_filing"
    GARNISHMENT = "garnishment"
    COMPLIANCE = "compliance"
    GENERAL = "general"
    CUSTOM = "custom"


class TemplateFormat(str, Enum):
    HTML = "html"
    TEXT = "text"
    PDF_LAYOUT = "pdf_layout"


class DocumentTemplate(TenantScopedModel):
    """Reusable document template with merge fields.

    Templates contain placeholders like {{consumer.full_name}},
    {{account.total_balance}}, etc. that are resolved at generation time.
    """

    __tablename__ = "document_templates"
    __table_args__ = (
        Index("ix_doc_templates_tenant_code", "tenant_id", "code", unique=True),
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[TemplateCategory] = mapped_column(
        SQLEnum(TemplateCategory), default=TemplateCategory.GENERAL, nullable=False
    )
    template_format: Mapped[TemplateFormat] = mapped_column(
        SQLEnum(TemplateFormat), default=TemplateFormat.HTML, nullable=False
    )

    subject: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    header: Mapped[str | None] = mapped_column(Text)
    footer: Mapped[str | None] = mapped_column(Text)

    merge_fields: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    pre_merge_script_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    generations: Mapped[list["DocumentGeneration"]] = relationship(
        "DocumentGeneration", back_populates="template"
    )


class GenerationStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    SENT = "sent"
    DELIVERED = "delivered"
    RETURNED = "returned"


class DeliveryChannel(str, Enum):
    PRINT = "print"
    EMAIL = "email"
    PORTAL = "portal"
    FAX = "fax"
    EFILING = "efiling"
    NONE = "none"


class DocumentGeneration(TenantScopedModel):
    """A generated document instance for a specific account."""

    __tablename__ = "document_generations"
    __table_args__ = (
        Index("ix_doc_gen_account", "account_id"),
        Index("ix_doc_gen_template", "template_id"),
        Index("ix_doc_gen_batch", "batch_id"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_templates.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )

    status: Mapped[GenerationStatus] = mapped_column(
        SQLEnum(GenerationStatus), default=GenerationStatus.PENDING, nullable=False
    )
    channel: Mapped[DeliveryChannel] = mapped_column(
        SQLEnum(DeliveryChannel), default=DeliveryChannel.PRINT, nullable=False
    )

    rendered_subject: Mapped[str | None] = mapped_column(String(500))
    rendered_body: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))

    merge_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    generated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    activity_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activity_entries.id")
    )

    template: Mapped["DocumentTemplate"] = relationship(
        "DocumentTemplate", back_populates="generations"
    )


class DocumentBatch(TenantScopedModel):
    """A batch run of document generation across multiple accounts."""

    __tablename__ = "document_batches"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_templates.id"), nullable=False
    )

    filter_criteria: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    total_accounts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
