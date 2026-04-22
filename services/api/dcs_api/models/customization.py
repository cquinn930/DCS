"""Customization models: reports, imports, exports, and scripting.

Provides the Collection-Master-style extensibility layer where tenants
can build custom reports, define import/export mappings per client or
jurisdiction, and write automation scripts.
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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dcs_api.models.base import BaseModel, TenantScopedModel


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

class ReportType(str, Enum):
    TABULAR = "tabular"
    SUMMARY = "summary"
    MATRIX = "matrix"
    CHART = "chart"


class ReportEntity(str, Enum):
    """Top-level entity a report targets."""
    ACCOUNTS = "accounts"
    CONSUMERS = "consumers"
    PAYMENTS = "payments"
    DISPUTES = "disputes"
    JUDGMENTS = "judgments"
    LITIGATION = "litigation"
    COMPLIANCE = "compliance"
    AUDIT_LOGS = "audit_logs"
    USERS = "users"


class OutputFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"
    PDF = "pdf"


class ReportTemplate(TenantScopedModel):
    """User-defined report template.

    Columns, filters, grouping and aggregations are stored as JSON so
    tenants can design reports without schema changes.

    Example columns JSON::

        [
            {"field": "account_reference", "label": "Acct #", "width": 120},
            {"field": "consumer.last_name", "label": "Last Name"},
            {"field": "total_balance", "label": "Balance", "format": "currency"},
            {"field": "status", "label": "Status"},
        ]

    Example filters JSON::

        [
            {"field": "status", "op": "in", "value": ["active", "payment_plan"]},
            {"field": "jurisdiction", "op": "eq", "value": "NJ"},
            {"field": "total_balance", "op": "gte", "value": 10000},
        ]
    """

    __tablename__ = "report_templates"
    __table_args__ = (
        Index("ix_report_templates_tenant_name", "tenant_id", "name", unique=True),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    report_type: Mapped[ReportType] = mapped_column(
        SQLEnum(ReportType), default=ReportType.TABULAR, nullable=False,
    )
    entity: Mapped[ReportEntity] = mapped_column(SQLEnum(ReportEntity), nullable=False)

    columns: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    filters: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    grouping: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    aggregations: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    sort_order: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    parameters: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    default_output_format: Mapped[OutputFormat] = mapped_column(
        SQLEnum(OutputFormat), default=OutputFormat.CSV, nullable=False,
    )
    allowed_output_formats: Mapped[list] = mapped_column(
        JSONB, default=lambda: ["csv", "xlsx", "json"], nullable=False,
    )

    jurisdiction: Mapped[str | None] = mapped_column(String(2))
    schedule_cron: Mapped[str | None] = mapped_column(String(100))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    executions: Mapped[list["ReportExecution"]] = relationship(
        "ReportExecution", back_populates="template",
    )


class ReportExecution(TenantScopedModel):
    """Single run of a report template."""

    __tablename__ = "report_executions"
    __table_args__ = (
        Index("ix_report_exec_tenant_template", "tenant_id", "template_id"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("report_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    output_format: Mapped[OutputFormat] = mapped_column(
        SQLEnum(OutputFormat), nullable=False,
    )

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer)
    output_path: Mapped[str | None] = mapped_column(String(500))
    error_message: Mapped[str | None] = mapped_column(Text)

    executed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    template: Mapped["ReportTemplate"] = relationship(
        "ReportTemplate", back_populates="executions",
    )


# ---------------------------------------------------------------------------
# Import engine
# ---------------------------------------------------------------------------

class ImportFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"
    FIXED_WIDTH = "fixed_width"
    XML = "xml"


class ImportEntity(str, Enum):
    ACCOUNTS = "accounts"
    CONSUMERS = "consumers"
    PAYMENTS = "payments"
    ADJUSTMENTS = "adjustments"
    CONTACTS = "contacts"


class DedupStrategy(str, Enum):
    SKIP = "skip"
    UPDATE = "update"
    ERROR = "error"
    CREATE_NEW = "create_new"


class ImportTemplate(TenantScopedModel):
    """Defines how to import external data into DCS.

    Each creditor / client can have its own template.  Field mappings
    translate source columns into DCS fields, with optional transforms
    and validation rules.

    Example field_mappings JSON::

        [
            {
                "source": "AcctNo",
                "target": "account_reference",
                "required": true,
            },
            {
                "source": "Balance",
                "target": "current_principal",
                "transform": "cents",
                "required": true,
            },
            {
                "source": "SSN",
                "target": "consumer.ssn_last_four",
                "transform": "last_four",
            },
        ]

    Example validation_rules JSON::

        [
            {"field": "current_principal", "rule": "positive"},
            {"field": "date_of_service", "rule": "date_format", "format": "%m/%d/%Y"},
            {"field": "jurisdiction", "rule": "one_of", "values": ["NJ", "NY", "PA"]},
        ]
    """

    __tablename__ = "import_templates"
    __table_args__ = (
        Index("ix_import_templates_tenant_name", "tenant_id", "name", unique=True),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_format: Mapped[ImportFormat] = mapped_column(
        SQLEnum(ImportFormat), nullable=False,
    )
    entity: Mapped[ImportEntity] = mapped_column(SQLEnum(ImportEntity), nullable=False)

    field_mappings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    validation_rules: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    transformations: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    default_values: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    delimiter: Mapped[str] = mapped_column(String(5), default=",", nullable=False)
    encoding: Mapped[str] = mapped_column(String(20), default="utf-8", nullable=False)
    skip_header_rows: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    fixed_width_spec: Mapped[list | None] = mapped_column(JSONB)

    dedup_strategy: Mapped[DedupStrategy] = mapped_column(
        SQLEnum(DedupStrategy), default=DedupStrategy.SKIP, nullable=False,
    )
    dedup_fields: Mapped[list] = mapped_column(
        JSONB, default=lambda: ["account_reference"], nullable=False,
    )

    client_name: Mapped[str | None] = mapped_column(String(255))
    jurisdiction: Mapped[str | None] = mapped_column(String(2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    jobs: Mapped[list["ImportJob"]] = relationship("ImportJob", back_populates="template")


class ImportJob(TenantScopedModel):
    """Tracks a single import execution."""

    __tablename__ = "import_jobs"
    __table_args__ = (
        Index("ix_import_jobs_tenant_status", "tenant_id", "status"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_templates.id", ondelete="SET NULL"),
        nullable=True,
    )

    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    template: Mapped["ImportTemplate | None"] = relationship(
        "ImportTemplate", back_populates="jobs",
    )


# ---------------------------------------------------------------------------
# Export engine
# ---------------------------------------------------------------------------

class ExportFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"
    FIXED_WIDTH = "fixed_width"
    XML = "xml"


class ExportEntity(str, Enum):
    ACCOUNTS = "accounts"
    CONSUMERS = "consumers"
    PAYMENTS = "payments"
    DISPUTES = "disputes"
    JUDGMENTS = "judgments"
    LITIGATION = "litigation"
    COMPLIANCE = "compliance"
    AUDIT_LOGS = "audit_logs"


class ExportTemplate(TenantScopedModel):
    """Defines an outbound export format.

    Used for creditor reporting, regulatory filings, or integration feeds.

    Example columns JSON::

        [
            {"field": "account_reference", "header": "ACCT_NO", "width": 20},
            {"field": "consumer.last_name", "header": "LNAME", "width": 30},
            {"field": "total_balance", "header": "BAL", "format": "dollars"},
        ]
    """

    __tablename__ = "export_templates"
    __table_args__ = (
        Index("ix_export_templates_tenant_name", "tenant_id", "name", unique=True),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    target_format: Mapped[ExportFormat] = mapped_column(
        SQLEnum(ExportFormat), nullable=False,
    )
    entity: Mapped[ExportEntity] = mapped_column(SQLEnum(ExportEntity), nullable=False)

    columns: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    filters: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    sort_order: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    transformations: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    delimiter: Mapped[str] = mapped_column(String(5), default=",", nullable=False)
    encoding: Mapped[str] = mapped_column(String(20), default="utf-8", nullable=False)
    include_header: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fixed_width_spec: Mapped[list | None] = mapped_column(JSONB)

    schedule_cron: Mapped[str | None] = mapped_column(String(100))
    recipient_email: Mapped[str | None] = mapped_column(String(320))

    client_name: Mapped[str | None] = mapped_column(String(255))
    jurisdiction: Mapped[str | None] = mapped_column(String(2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    jobs: Mapped[list["ExportJob"]] = relationship("ExportJob", back_populates="template")


class ExportJob(TenantScopedModel):
    """Tracks a single export execution."""

    __tablename__ = "export_jobs"
    __table_args__ = (
        Index("ix_export_jobs_tenant_status", "tenant_id", "status"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("export_templates.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(500))
    file_size: Mapped[int | None] = mapped_column(Integer)
    output_path: Mapped[str | None] = mapped_column(String(500))
    error_message: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    template: Mapped["ExportTemplate | None"] = relationship(
        "ExportTemplate", back_populates="jobs",
    )


# ---------------------------------------------------------------------------
# Scripting engine
# ---------------------------------------------------------------------------

class ScriptType(str, Enum):
    REPORT_TRANSFORM = "report_transform"
    VALIDATION = "validation"
    WORKFLOW = "workflow"
    CALCULATION = "calculation"
    TRIGGER = "trigger"
    IMPORT_TRANSFORM = "import_transform"
    EXPORT_TRANSFORM = "export_transform"
    COMPLIANCE_CHECK = "compliance_check"


class TriggerEvent(str, Enum):
    ON_IMPORT = "on_import"
    ON_EXPORT = "on_export"
    ON_PAYMENT = "on_payment"
    ON_DISPUTE = "on_dispute"
    ON_STATUS_CHANGE = "on_status_change"
    ON_CONTACT = "on_contact"
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class Script(TenantScopedModel):
    """User-authored automation script.

    Scripts are written in DCS Script (a safe, restricted DSL) and can
    be attached to triggers, reports, imports, or run manually.

    DCS Script example::

        # Flag accounts approaching statute of limitations
        PARAM jurisdiction STRING "NJ"
        PARAM warning_days INTEGER 90

        QUERY accounts
          WHERE jurisdiction = $jurisdiction
          AND status IN ["active", "payment_plan"]
          AND days_since(date_of_first_delinquency) > (sol_years($jurisdiction) * 365 - $warning_days)

        FOR EACH account:
          SET remaining = sol_years($jurisdiction) * 365 - days_since(account.date_of_first_delinquency)
          IF remaining < 30:
            SET account.flags += "sol_critical"
          ELIF remaining < $warning_days:
            SET account.flags += "sol_warning"
          END
        END

        RETURN results
    """

    __tablename__ = "scripts"
    __table_args__ = (
        Index("ix_scripts_tenant_name", "tenant_id", "name", unique=True),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    script_type: Mapped[ScriptType] = mapped_column(SQLEnum(ScriptType), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)

    trigger_event: Mapped[TriggerEvent | None] = mapped_column(SQLEnum(TriggerEvent))
    trigger_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    parameters: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    jurisdiction: Mapped[str | None] = mapped_column(String(2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_status: Mapped[str | None] = mapped_column(String(20))
    last_run_result: Mapped[dict | None] = mapped_column(JSONB)

    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    executions: Mapped[list["ScriptExecution"]] = relationship(
        "ScriptExecution", back_populates="script",
    )


class ScriptExecution(TenantScopedModel):
    """Tracks a single script run for audit."""

    __tablename__ = "script_executions"
    __table_args__ = (
        Index("ix_script_exec_tenant_script", "tenant_id", "script_id"),
    )

    script_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scripts.id", ondelete="CASCADE"),
        nullable=False,
    )
    script_version: Mapped[int] = mapped_column(Integer, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    rows_affected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    executed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    script: Mapped["Script"] = relationship("Script", back_populates="executions")
