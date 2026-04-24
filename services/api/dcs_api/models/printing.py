"""Print & Mail models — provider-agnostic print jobs and printer registry.

Two delivery targets share one ``PrintJob`` table:

* ``BUREAU`` — server submits the rendered PDF + recipient address
  to a print/mail bureau (Lob, PostGrid, Click2Mail). Bureau prints,
  stuffs, mails, and returns USPS tracking. Used for compliance mail.
* ``LOCAL`` — printed on a physical printer the tenant has registered.
  Either the user's browser opens a print dialog (fallback) or the
  Electron client / DCS Print Agent silently prints the PDF to the
  named printer over IPP, ESC/POS, or ZPL.

Tenants can mix-and-match per ``Printer`` row. The adapter wired to
each printer determines what really happens at submit time.
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import TenantScopedModel


class PrinterKind(str, Enum):
    """Physical class of the device.

    The kind drives which adapter family can bind to it (e.g., a
    THERMAL printer can only use ESC/POS adapters, not IPP) and which
    UI controls render (paper sizes, tray selection, etc.).
    """

    OFFICE = "office"
    THERMAL = "thermal"
    LABEL = "label"
    CHECK = "check"
    OTHER = "other"


class PrinterTransport(str, Enum):
    """How the agent reaches the printer."""

    IPP = "ipp"
    ESCPOS_TCP = "escpos_tcp"
    ZPL_TCP = "zpl_tcp"
    USB = "usb"
    ELECTRON_DEFAULT = "electron_default"
    PDF_DOWNLOAD = "pdf_download"


class PrintTarget(str, Enum):
    BUREAU = "bureau"
    LOCAL = "local"


class PrintJobStatus(str, Enum):
    QUEUED = "queued"
    SUBMITTED = "submitted"
    RENDERING = "rendering"
    PRINTING = "printing"
    PRINTED = "printed"
    MAILED = "mailed"
    DELIVERED = "delivered"
    RETURNED = "returned"
    FAILED = "failed"
    CANCELED = "canceled"


class Printer(TenantScopedModel):
    """A printer the tenant has configured.

    For a SaaS browser-only tenant, ``transport=PDF_DOWNLOAD`` is the
    safe default — the user's browser opens a print dialog. For
    Electron tenants, ``ELECTRON_DEFAULT`` lets the desktop client
    silently print to the OS default. Network printers use IPP, label
    printers use ZPL_TCP, etc.
    """

    __tablename__ = "printers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_printer_name"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))

    kind: Mapped[PrinterKind] = mapped_column(
        SQLEnum(PrinterKind), default=PrinterKind.OFFICE, nullable=False
    )
    transport: Mapped[PrinterTransport] = mapped_column(
        SQLEnum(PrinterTransport), default=PrinterTransport.PDF_DOWNLOAD, nullable=False
    )

    host: Mapped[str | None] = mapped_column(String(255))
    port: Mapped[int | None] = mapped_column(Integer)
    queue_name: Mapped[str | None] = mapped_column(String(255))

    options: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PrintJob(TenantScopedModel):
    """A request to print a rendered document somewhere.

    Either ``printer_id`` (LOCAL) or ``bureau_provider`` (BUREAU) is
    set, never both. ``provider_job_id`` is whatever the adapter
    returns for status polling. ``document_id`` is the source artifact
    in the existing documents pipeline.
    """

    __tablename__ = "print_jobs"
    __table_args__ = (
        Index("ix_printjob_status", "status"),
        Index("ix_printjob_target", "target"),
        Index("ix_printjob_document", "document_id"),
    )

    target: Mapped[PrintTarget] = mapped_column(SQLEnum(PrintTarget), nullable=False)
    status: Mapped[PrintJobStatus] = mapped_column(
        SQLEnum(PrintJobStatus), default=PrintJobStatus.QUEUED, nullable=False
    )

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_generations.id", ondelete="SET NULL"),
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL")
    )
    consumer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consumers.id", ondelete="SET NULL")
    )

    printer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("printers.id", ondelete="SET NULL")
    )
    bureau_provider: Mapped[str | None] = mapped_column(String(64))

    provider_job_id: Mapped[str | None] = mapped_column(String(255))

    copies: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    options: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    recipient: Mapped[dict | None] = mapped_column(JSONB)

    requires_certified_mail: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    tracking_number: Mapped[str | None] = mapped_column(String(255))

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    raw_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    printer: Mapped["Printer | None"] = relationship("Printer", lazy="joined")
