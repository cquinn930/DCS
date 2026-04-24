"""Scan & Capture models — provider-agnostic intake from scanners and MFPs.

Scanners come in three behavioral kinds:

* ``DOCUMENT`` — generic page intake; output goes to the document
  routing pipeline so it can be auto-attached to an account by
  account-number OCR / barcode / human review.
* ``CHECK`` — *handled differently*: the adapter parses the MICR line
  (routing/account/check#), stores image front+back per Check 21
  (X9.37) requirements, and creates a ``Check`` row that the payments
  flow can convert into a ``Payment`` after deposit confirmation.
* ``ID`` — identity documents (driver's license, passport) for
  ID-theft disputes; tagged so masking policies hide the result by
  default.

The transport (TWAIN, MFP-SFTP, hot folder, MFP-email, X9.37) is
declared by the adapter, not by the model — so adding a new MFP
vendor doesn't require a schema change.
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


class ScannerKind(str, Enum):
    DOCUMENT = "document"
    CHECK = "check"
    ID = "id"
    OTHER = "other"


class ScannerTransport(str, Enum):
    """How scanned data reaches the server."""

    MFP_SFTP = "mfp_sftp"
    MFP_EMAIL = "mfp_email"
    MFP_HTTPS = "mfp_https"
    HOT_FOLDER = "hot_folder"
    ELECTRON_TWAIN = "electron_twain"
    ELECTRON_WIA = "electron_wia"
    ELECTRON_SANE = "electron_sane"
    DYNAMSOFT = "dynamsoft"
    X937_CHECK_IMAGE = "x937_check_image"
    OTHER = "other"


class ScanJobStatus(str, Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    OCR_RUNNING = "ocr_running"
    UNROUTED = "unrouted"
    ROUTED = "routed"
    REJECTED = "rejected"
    DEPOSITED = "deposited"
    FAILED = "failed"


class CheckStatus(str, Enum):
    """Lifecycle of a scanned check, separate from the scan job itself."""

    SCANNED = "scanned"
    PENDING_DEPOSIT = "pending_deposit"
    DEPOSITED = "deposited"
    CLEARED = "cleared"
    RETURNED = "returned"
    VOIDED = "voided"


class Scanner(TenantScopedModel):
    """A scanner the tenant has registered.

    For a SaaS-only tenant, ``transport=MFP_SFTP`` or ``MFP_EMAIL``
    typically suffice — the office MFP scans to an inbox the server
    polls. Electron tenants additionally get the ``ELECTRON_*`` and
    ``DYNAMSOFT`` transports for in-app scanning bound to an account
    page.
    """

    __tablename__ = "scanners"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_scanner_name"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))

    kind: Mapped[ScannerKind] = mapped_column(
        SQLEnum(ScannerKind), default=ScannerKind.DOCUMENT, nullable=False
    )
    transport: Mapped[ScannerTransport] = mapped_column(
        SQLEnum(ScannerTransport), default=ScannerTransport.MFP_SFTP, nullable=False
    )

    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    intake_token_hash: Mapped[str | None] = mapped_column(String(255))
    intake_inbox_email: Mapped[str | None] = mapped_column(String(255))

    deposit_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trust_accounts.id", ondelete="SET NULL"),
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ScanJob(TenantScopedModel):
    """A single capture session from a scanner.

    A scan job is the *intake* event. If the routing engine
    successfully links it to an account, the resulting artifact also
    appears in the documents table; if it parses as a check, a
    ``Check`` row is created and the scan job is marked ``DEPOSITED``
    once a deposit is confirmed.
    """

    __tablename__ = "scan_jobs"
    __table_args__ = (
        Index("ix_scanjob_status", "status"),
        Index("ix_scanjob_scanner", "scanner_id"),
    )

    scanner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scanners.id", ondelete="SET NULL")
    )
    status: Mapped[ScanJobStatus] = mapped_column(
        SQLEnum(ScanJobStatus), default=ScanJobStatus.PENDING, nullable=False
    )

    page_count: Mapped[int | None] = mapped_column(Integer)
    storage_uri: Mapped[str | None] = mapped_column(String(2048))
    mime_type: Mapped[str | None] = mapped_column(String(128))
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))

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

    routing_confidence: Mapped[int | None] = mapped_column(Integer)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    raw_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    routed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    captured_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class Check(TenantScopedModel):
    """A scanned paper check awaiting deposit / clearance.

    Created automatically by check-kind scanners after MICR parse.
    Links back to the source ``ScanJob`` for image retrieval and
    forward to a ``Payment`` once cleared. We deliberately *do not*
    auto-create the Payment row at scan time — funds aren't
    collected until the bank clears the deposit.
    """

    __tablename__ = "scanned_checks"
    __table_args__ = (
        Index("ix_check_status", "status"),
        Index("ix_check_account", "account_id"),
    )

    scan_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    routing_number: Mapped[str | None] = mapped_column(String(16))
    bank_account_number_last4: Mapped[str | None] = mapped_column(String(8))
    check_number: Mapped[str | None] = mapped_column(String(32))

    amount_cents: Mapped[int | None] = mapped_column(Integer)
    payer_name: Mapped[str | None] = mapped_column(String(255))
    memo: Mapped[str | None] = mapped_column(Text)

    front_image_uri: Mapped[str | None] = mapped_column(String(2048))
    back_image_uri: Mapped[str | None] = mapped_column(String(2048))

    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL")
    )
    consumer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consumers.id", ondelete="SET NULL")
    )

    deposit_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trust_accounts.id", ondelete="SET NULL"),
    )

    status: Mapped[CheckStatus] = mapped_column(
        SQLEnum(CheckStatus), default=CheckStatus.SCANNED, nullable=False
    )
    deposited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    return_reason: Mapped[str | None] = mapped_column(String(255))

    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL")
    )

    raw_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    scan_job: Mapped["ScanJob"] = relationship("ScanJob", lazy="joined")
