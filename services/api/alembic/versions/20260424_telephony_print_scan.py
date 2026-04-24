"""Add telephony, print & mail, and scan & capture tables.

Adds the canonical tables for the new integrations subsystems:

  - calls, call_events, call_dispositions, phone_numbers
  - printers, print_jobs
  - scanners, scan_jobs, scanned_checks

All tenant-scoped, all configured live from the Settings UI; no
DB seeding required to use them. Adapter-specific configuration
lives in ``tenants.settings`` JSONB (no schema change), so adding
a new provider is a code-only change.

Revision ID: 1a4f7c9d8e10
Revises: bf7d2ad7838a
Create Date: 2026-04-24 16:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "1a4f7c9d8e10"
down_revision: Union[str, None] = "bf7d2ad7838a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Native enums. We let SQLAlchemy create them on first table use, then
# reuse the type with create_type=False on subsequent columns. Drop is
# manual in downgrade because Postgres won't drop a type still
# referenced by any column.

call_direction = postgresql.ENUM(
    "INBOUND", "OUTBOUND", "INTERNAL", name="calldirection"
)
call_status = postgresql.ENUM(
    "QUEUED", "INITIATED", "RINGING", "ANSWERED", "COMPLETED",
    "NO_ANSWER", "BUSY", "FAILED", "CANCELED", "VOICEMAIL",
    name="callstatus",
)
call_event_type = postgresql.ENUM(
    "DIAL_REQUESTED", "INBOUND_RECEIVED", "RINGING", "ANSWERED",
    "HOLD", "UNHOLD", "TRANSFER", "CONFERENCE", "DTMF", "HANGUP",
    "RECORDING_STARTED", "RECORDING_STOPPED", "DISPOSITION_SET",
    "NOTE_ADDED", "PROVIDER_ERROR",
    name="calleventtype",
)
phone_number_role = postgresql.ENUM(
    "INBOUND", "OUTBOUND_CALLER_ID", "SMS", "FAX",
    name="phonenumberrole",
)
printer_kind = postgresql.ENUM(
    "OFFICE", "THERMAL", "LABEL", "CHECK", "OTHER", name="printerkind"
)
printer_transport = postgresql.ENUM(
    "IPP", "ESCPOS_TCP", "ZPL_TCP", "USB",
    "ELECTRON_DEFAULT", "PDF_DOWNLOAD",
    name="printertransport",
)
print_target = postgresql.ENUM("BUREAU", "LOCAL", name="printtarget")
print_job_status = postgresql.ENUM(
    "QUEUED", "SUBMITTED", "RENDERING", "PRINTING", "PRINTED",
    "MAILED", "DELIVERED", "RETURNED", "FAILED", "CANCELED",
    name="printjobstatus",
)
scanner_kind = postgresql.ENUM(
    "DOCUMENT", "CHECK", "ID", "OTHER", name="scannerkind"
)
scanner_transport = postgresql.ENUM(
    "MFP_SFTP", "MFP_EMAIL", "MFP_HTTPS", "HOT_FOLDER",
    "ELECTRON_TWAIN", "ELECTRON_WIA", "ELECTRON_SANE",
    "DYNAMSOFT", "X937_CHECK_IMAGE", "OTHER",
    name="scannertransport",
)
scan_job_status = postgresql.ENUM(
    "PENDING", "UPLOADED", "OCR_RUNNING", "UNROUTED", "ROUTED",
    "REJECTED", "DEPOSITED", "FAILED",
    name="scanjobstatus",
)
check_status = postgresql.ENUM(
    "SCANNED", "PENDING_DEPOSIT", "DEPOSITED", "CLEARED",
    "RETURNED", "VOIDED",
    name="checkstatus",
)


_ALL_ENUMS = [
    call_direction, call_status, call_event_type, phone_number_role,
    printer_kind, printer_transport, print_target, print_job_status,
    scanner_kind, scanner_transport, scan_job_status, check_status,
]


def _ts_cols() -> list[sa.Column]:
    """Standard tenant_id + id + timestamps shared by every new table."""
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    for enum in _ALL_ENUMS:
        enum.create(bind, checkfirst=True)

    # ---- telephony -------------------------------------------------------

    op.create_table(
        "call_dispositions",
        *_ts_cols(),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_contact", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_rpc", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_note", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("triggers_followup_days", sa.Integer()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.UniqueConstraint("tenant_id", "code", name="uq_disposition_code"),
    )

    op.create_table(
        "calls",
        *_ts_cols(),
        sa.Column("adapter_id", sa.String(64), nullable=False),
        sa.Column("provider_call_sid", sa.String(255)),
        sa.Column(
            "direction",
            postgresql.ENUM(name="calldirection", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="callstatus", create_type=False),
            nullable=False,
            server_default="QUEUED",
        ),
        sa.Column("from_e164", sa.String(32)),
        sa.Column("to_e164", sa.String(32)),
        sa.Column(
            "consumer_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("consumers.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "account_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "agent_user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("queued_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("cost_micros", sa.Integer()),
        sa.Column(
            "disposition_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("call_dispositions.id", ondelete="SET NULL"),
        ),
        sa.Column("notes", sa.Text()),
        sa.Column("recording_url", sa.String(2048)),
        sa.Column("recording_consent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("recording_disclosed_at", sa.DateTime(timezone=True)),
        sa.Column("raw_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_call_account", "calls", ["account_id"])
    op.create_index("ix_call_consumer", "calls", ["consumer_id"])
    op.create_index("ix_call_agent", "calls", ["agent_user_id"])
    op.create_index("ix_call_started", "calls", ["started_at"])
    op.create_index("ix_call_provider_sid", "calls", ["adapter_id", "provider_call_sid"])

    op.create_table(
        "call_events",
        *_ts_cols(),
        sa.Column(
            "call_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            postgresql.ENUM(name="calleventtype", create_type=False),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "actor_user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_callevent_call", "call_events", ["call_id", "occurred_at"])

    op.create_table(
        "phone_numbers",
        *_ts_cols(),
        sa.Column("e164", sa.String(32), nullable=False),
        sa.Column("label", sa.String(255)),
        sa.Column("adapter_id", sa.String(64), nullable=False),
        sa.Column("roles", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("routing", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("tenant_id", "e164", "adapter_id", name="uq_phone_per_adapter"),
    )
    op.create_index("ix_phone_e164", "phone_numbers", ["e164"])

    # ---- printing --------------------------------------------------------

    op.create_table(
        "printers",
        *_ts_cols(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("location", sa.String(255)),
        sa.Column(
            "kind",
            postgresql.ENUM(name="printerkind", create_type=False),
            nullable=False,
            server_default="OFFICE",
        ),
        sa.Column(
            "transport",
            postgresql.ENUM(name="printertransport", create_type=False),
            nullable=False,
            server_default="PDF_DOWNLOAD",
        ),
        sa.Column("host", sa.String(255)),
        sa.Column("port", sa.Integer()),
        sa.Column("queue_name", sa.String(255)),
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_printer_name"),
    )

    op.create_table(
        "print_jobs",
        *_ts_cols(),
        sa.Column(
            "target",
            postgresql.ENUM(name="printtarget", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="printjobstatus", create_type=False),
            nullable=False,
            server_default="QUEUED",
        ),
        sa.Column(
            "document_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_generations.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "account_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "consumer_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("consumers.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "printer_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("printers.id", ondelete="SET NULL"),
        ),
        sa.Column("bureau_provider", sa.String(64)),
        sa.Column("provider_job_id", sa.String(255)),
        sa.Column("copies", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("recipient", postgresql.JSONB()),
        sa.Column("requires_certified_mail", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tracking_number", sa.String(255)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.Column(
            "requested_by_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("raw_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_printjob_status", "print_jobs", ["status"])
    op.create_index("ix_printjob_target", "print_jobs", ["target"])
    op.create_index("ix_printjob_document", "print_jobs", ["document_id"])

    # ---- scanning --------------------------------------------------------

    op.create_table(
        "scanners",
        *_ts_cols(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("location", sa.String(255)),
        sa.Column(
            "kind",
            postgresql.ENUM(name="scannerkind", create_type=False),
            nullable=False,
            server_default="DOCUMENT",
        ),
        sa.Column(
            "transport",
            postgresql.ENUM(name="scannertransport", create_type=False),
            nullable=False,
            server_default="MFP_SFTP",
        ),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("intake_token_hash", sa.String(255)),
        sa.Column("intake_inbox_email", sa.String(255)),
        sa.Column(
            "deposit_account_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trust_accounts.id", ondelete="SET NULL"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_scanner_name"),
    )

    op.create_table(
        "scan_jobs",
        *_ts_cols(),
        sa.Column(
            "scanner_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scanners.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="scanjobstatus", create_type=False),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("page_count", sa.Integer()),
        sa.Column("storage_uri", sa.String(2048)),
        sa.Column("mime_type", sa.String(128)),
        sa.Column("file_size_bytes", sa.Integer()),
        sa.Column("sha256", sa.String(64)),
        sa.Column(
            "document_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_generations.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "account_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "consumer_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("consumers.id", ondelete="SET NULL"),
        ),
        sa.Column("routing_confidence", sa.Integer()),
        sa.Column("ocr_text", sa.Text()),
        sa.Column("raw_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text()),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
        sa.Column("routed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "captured_by_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
    )
    op.create_index("ix_scanjob_status", "scan_jobs", ["status"])
    op.create_index("ix_scanjob_scanner", "scan_jobs", ["scanner_id"])

    op.create_table(
        "scanned_checks",
        *_ts_cols(),
        sa.Column(
            "scan_job_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scan_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("routing_number", sa.String(16)),
        sa.Column("bank_account_number_last4", sa.String(8)),
        sa.Column("check_number", sa.String(32)),
        sa.Column("amount_cents", sa.Integer()),
        sa.Column("payer_name", sa.String(255)),
        sa.Column("memo", sa.Text()),
        sa.Column("front_image_uri", sa.String(2048)),
        sa.Column("back_image_uri", sa.String(2048)),
        sa.Column(
            "account_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "consumer_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("consumers.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "deposit_account_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trust_accounts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="checkstatus", create_type=False),
            nullable=False,
            server_default="SCANNED",
        ),
        sa.Column("deposited_at", sa.DateTime(timezone=True)),
        sa.Column("cleared_at", sa.DateTime(timezone=True)),
        sa.Column("returned_at", sa.DateTime(timezone=True)),
        sa.Column("return_reason", sa.String(255)),
        sa.Column(
            "payment_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payments.id", ondelete="SET NULL"),
        ),
        sa.Column("raw_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_check_status", "scanned_checks", ["status"])
    op.create_index("ix_check_account", "scanned_checks", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_check_account", table_name="scanned_checks")
    op.drop_index("ix_check_status", table_name="scanned_checks")
    op.drop_table("scanned_checks")

    op.drop_index("ix_scanjob_scanner", table_name="scan_jobs")
    op.drop_index("ix_scanjob_status", table_name="scan_jobs")
    op.drop_table("scan_jobs")

    op.drop_table("scanners")

    op.drop_index("ix_printjob_document", table_name="print_jobs")
    op.drop_index("ix_printjob_target", table_name="print_jobs")
    op.drop_index("ix_printjob_status", table_name="print_jobs")
    op.drop_table("print_jobs")

    op.drop_table("printers")

    op.drop_index("ix_phone_e164", table_name="phone_numbers")
    op.drop_table("phone_numbers")

    op.drop_index("ix_callevent_call", table_name="call_events")
    op.drop_table("call_events")

    op.drop_index("ix_call_provider_sid", table_name="calls")
    op.drop_index("ix_call_started", table_name="calls")
    op.drop_index("ix_call_agent", table_name="calls")
    op.drop_index("ix_call_consumer", table_name="calls")
    op.drop_index("ix_call_account", table_name="calls")
    op.drop_table("calls")

    op.drop_table("call_dispositions")

    bind = op.get_bind()
    for enum in reversed(_ALL_ENUMS):
        enum.drop(bind, checkfirst=True)
