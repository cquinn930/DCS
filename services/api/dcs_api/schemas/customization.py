"""Schemas for the customization layer: reports, imports, exports, scripting."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dcs_api.schemas.common import TimestampSchema


# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

class ColumnDef(BaseModel):
    """Column definition for reports and exports."""
    field: str
    label: str | None = None
    header: str | None = None
    width: int | None = None
    format: str | None = None
    visible: bool = True


class FilterDef(BaseModel):
    """Filter condition."""
    field: str
    op: str = Field(description="eq, neq, gt, gte, lt, lte, in, not_in, like, between, is_null, not_null")
    value: Any = None


class SortDef(BaseModel):
    field: str
    direction: str = "asc"


class AggregationDef(BaseModel):
    field: str
    function: str = Field(description="sum, count, avg, min, max")
    label: str | None = None


class ParameterDef(BaseModel):
    """User-supplied parameter for reports or scripts."""
    name: str
    param_type: str = Field(description="string, integer, decimal, date, boolean, choice")
    label: str | None = None
    default: Any = None
    required: bool = False
    choices: list[str] | None = None


# ---------------------------------------------------------------------------
# Report schemas
# ---------------------------------------------------------------------------

class ReportTemplateCreate(BaseModel):
    name: str = Field(max_length=255)
    description: str | None = None
    report_type: str = "tabular"
    entity: str
    columns: list[ColumnDef] = []
    filters: list[FilterDef] = []
    grouping: list[str] = []
    aggregations: list[AggregationDef] = []
    sort_order: list[SortDef] = []
    parameters: list[ParameterDef] = []
    default_output_format: str = "csv"
    allowed_output_formats: list[str] = Field(default=["csv", "xlsx", "json"])
    jurisdiction: str | None = Field(None, max_length=2)
    schedule_cron: str | None = None


class ReportTemplateUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    report_type: str | None = None
    columns: list[ColumnDef] | None = None
    filters: list[FilterDef] | None = None
    grouping: list[str] | None = None
    aggregations: list[AggregationDef] | None = None
    sort_order: list[SortDef] | None = None
    parameters: list[ParameterDef] | None = None
    default_output_format: str | None = None
    allowed_output_formats: list[str] | None = None
    jurisdiction: str | None = None
    schedule_cron: str | None = None
    is_active: bool | None = None


class ReportTemplateResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    report_type: str
    entity: str
    columns: list[dict] = []
    filters: list[dict] = []
    grouping: list[str] = []
    aggregations: list[dict] = []
    sort_order: list[dict] = []
    parameters: list[dict] = []
    default_output_format: str
    allowed_output_formats: list[str] = []
    jurisdiction: str | None = None
    schedule_cron: str | None = None
    is_system: bool = False
    is_active: bool = True
    created_by: uuid.UUID | None = None


class ReportRunRequest(BaseModel):
    """Execute a report with optional runtime parameters."""
    output_format: str = "csv"
    parameters: dict[str, Any] = {}
    limit: int | None = Field(None, ge=1, le=100000)


class ReportExecutionResponse(TimestampSchema):
    id: uuid.UUID
    template_id: uuid.UUID
    parameters: dict = {}
    output_format: str
    status: str
    row_count: int | None = None
    output_path: str | None = None
    error_message: str | None = None
    executed_by: uuid.UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


# ---------------------------------------------------------------------------
# Import schemas
# ---------------------------------------------------------------------------

class FieldMapping(BaseModel):
    source: str
    target: str
    required: bool = False
    transform: str | None = Field(None, description="cents, last_four, uppercase, lowercase, date, trim, default")
    default_value: Any = None


class ValidationRule(BaseModel):
    field: str
    rule: str = Field(description="required, positive, date_format, one_of, regex, max_length, min_length")
    params: dict[str, Any] = {}


class ImportTemplateCreate(BaseModel):
    name: str = Field(max_length=255)
    description: str | None = None
    source_format: str
    entity: str
    field_mappings: list[FieldMapping] = []
    validation_rules: list[ValidationRule] = []
    transformations: list[dict] = []
    default_values: dict[str, Any] = {}
    delimiter: str = ","
    encoding: str = "utf-8"
    skip_header_rows: int = 1
    fixed_width_spec: list[dict] | None = None
    dedup_strategy: str = "skip"
    dedup_fields: list[str] = Field(default=["account_reference"])
    client_name: str | None = Field(None, max_length=255)
    jurisdiction: str | None = Field(None, max_length=2)


class ImportTemplateUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    field_mappings: list[FieldMapping] | None = None
    validation_rules: list[ValidationRule] | None = None
    transformations: list[dict] | None = None
    default_values: dict[str, Any] | None = None
    delimiter: str | None = None
    encoding: str | None = None
    skip_header_rows: int | None = None
    dedup_strategy: str | None = None
    dedup_fields: list[str] | None = None
    client_name: str | None = None
    jurisdiction: str | None = None
    is_active: bool | None = None


class ImportTemplateResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    source_format: str
    entity: str
    field_mappings: list[dict] = []
    validation_rules: list[dict] = []
    transformations: list[dict] = []
    default_values: dict = {}
    delimiter: str
    encoding: str
    skip_header_rows: int
    fixed_width_spec: list[dict] | None = None
    dedup_strategy: str
    dedup_fields: list[str] = []
    client_name: str | None = None
    jurisdiction: str | None = None
    is_active: bool = True
    created_by: uuid.UUID | None = None


class ImportJobResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    template_id: uuid.UUID | None = None
    file_name: str
    file_size: int | None = None
    status: str
    total_rows: int = 0
    processed_rows: int = 0
    created_rows: int = 0
    updated_rows: int = 0
    skipped_rows: int = 0
    error_rows: int = 0
    errors: list[dict] = []
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_by: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# Export schemas
# ---------------------------------------------------------------------------

class ExportTemplateCreate(BaseModel):
    name: str = Field(max_length=255)
    description: str | None = None
    target_format: str
    entity: str
    columns: list[ColumnDef] = []
    filters: list[FilterDef] = []
    sort_order: list[SortDef] = []
    transformations: list[dict] = []
    delimiter: str = ","
    encoding: str = "utf-8"
    include_header: bool = True
    fixed_width_spec: list[dict] | None = None
    schedule_cron: str | None = None
    recipient_email: str | None = None
    client_name: str | None = Field(None, max_length=255)
    jurisdiction: str | None = Field(None, max_length=2)


class ExportTemplateUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    columns: list[ColumnDef] | None = None
    filters: list[FilterDef] | None = None
    sort_order: list[SortDef] | None = None
    transformations: list[dict] | None = None
    delimiter: str | None = None
    encoding: str | None = None
    include_header: bool | None = None
    schedule_cron: str | None = None
    recipient_email: str | None = None
    client_name: str | None = None
    jurisdiction: str | None = None
    is_active: bool | None = None


class ExportTemplateResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    target_format: str
    entity: str
    columns: list[dict] = []
    filters: list[dict] = []
    sort_order: list[dict] = []
    transformations: list[dict] = []
    delimiter: str
    encoding: str
    include_header: bool = True
    fixed_width_spec: list[dict] | None = None
    schedule_cron: str | None = None
    recipient_email: str | None = None
    client_name: str | None = None
    jurisdiction: str | None = None
    is_active: bool = True
    created_by: uuid.UUID | None = None


class ExportRunRequest(BaseModel):
    parameters: dict[str, Any] = {}


class ExportJobResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    template_id: uuid.UUID | None = None
    status: str
    row_count: int = 0
    file_name: str | None = None
    file_size: int | None = None
    output_path: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_by: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# Script schemas
# ---------------------------------------------------------------------------

class ScriptCreate(BaseModel):
    name: str = Field(max_length=255)
    description: str | None = None
    script_type: str
    code: str = Field(max_length=50000)
    trigger_event: str | None = None
    trigger_config: dict = {}
    parameters: list[ParameterDef] = []
    jurisdiction: str | None = Field(None, max_length=2)


class ScriptUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    code: str | None = Field(None, max_length=50000)
    trigger_event: str | None = None
    trigger_config: dict | None = None
    parameters: list[ParameterDef] | None = None
    jurisdiction: str | None = None
    is_active: bool | None = None


class ScriptResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    script_type: str
    code: str
    trigger_event: str | None = None
    trigger_config: dict = {}
    parameters: list[dict] = []
    jurisdiction: str | None = None
    is_active: bool = True
    is_system: bool = False
    version: int = 1
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    created_by: uuid.UUID | None = None


class ScriptRunRequest(BaseModel):
    parameters: dict[str, Any] = {}
    dry_run: bool = False


class ScriptValidateRequest(BaseModel):
    code: str = Field(max_length=50000)
    script_type: str = "workflow"


class ScriptExecutionResponse(TimestampSchema):
    id: uuid.UUID
    script_id: uuid.UUID
    script_version: int
    parameters: dict = {}
    status: str
    result: dict | None = None
    error_message: str | None = None
    rows_affected: int = 0
    duration_ms: int | None = None
    executed_by: uuid.UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
