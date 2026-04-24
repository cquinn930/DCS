"""Printing schemas — config, capabilities, printers, jobs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from dcs_api.models.printing import (
    PrinterKind,
    PrinterTransport,
    PrintJobStatus,
    PrintTarget,
)
from dcs_api.schemas.common import TimestampSchema


# ---------------------------------------------------------------------------
# Tenant config (settings.printing)
# ---------------------------------------------------------------------------


class PrintingTenantConfig(BaseModel):
    """Per-tenant printing config — bureau provider plus defaults."""

    bureau_adapter_id: str | None = None
    bureau_config: dict[str, Any] = Field(default_factory=dict)

    default_local_printer_id: uuid.UUID | None = None

    require_certified_for_initial_letter: bool = True
    track_certified_returns: bool = True

    daily_print_cap: int | None = None


class PrintingTenantConfigUpdate(BaseModel):
    bureau_adapter_id: str | None = None
    bureau_config: dict[str, Any] | None = None
    default_local_printer_id: uuid.UUID | None = None
    require_certified_for_initial_letter: bool | None = None
    track_certified_returns: bool | None = None
    daily_print_cap: int | None = None


# ---------------------------------------------------------------------------
# Capabilities + adapter catalog
# ---------------------------------------------------------------------------


class PrintCapabilitiesOut(BaseModel):
    duplex: bool
    color: bool
    certified_mail: bool = False
    bulk: bool
    silent: bool
    address_validation: bool = False
    return_envelope: bool = False
    tracking: bool = False
    paper_sizes: list[str]
    requires_electron: bool
    notes: str = ""


class PrintAdapterDescriptorOut(BaseModel):
    id: str
    label: str
    family: Literal["bureau", "local", "thermal", "label", "check"]
    capabilities: PrintCapabilitiesOut
    config_schema: dict[str, Any]
    docs_url: str | None = None


class PrintMeResponse(BaseModel):
    bureau_adapter_id: str | None
    bureau_configured: bool
    local_default_printer_id: uuid.UUID | None
    bureau_capabilities: PrintCapabilitiesOut | None


# ---------------------------------------------------------------------------
# Printer CRUD
# ---------------------------------------------------------------------------


class PrinterCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    location: str | None = None
    kind: PrinterKind = PrinterKind.OFFICE
    transport: PrinterTransport = PrinterTransport.PDF_DOWNLOAD
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    queue_name: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False
    is_active: bool = True


class PrinterUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    location: str | None = None
    kind: PrinterKind | None = None
    transport: PrinterTransport | None = None
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    queue_name: str | None = None
    options: dict[str, Any] | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class PrinterResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    location: str | None
    kind: PrinterKind
    transport: PrinterTransport
    host: str | None
    port: int | None
    queue_name: str | None
    options: dict[str, Any]
    is_default: bool
    is_active: bool


# ---------------------------------------------------------------------------
# Print jobs
# ---------------------------------------------------------------------------


class PrintJobCreate(BaseModel):
    target: PrintTarget
    document_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    consumer_id: uuid.UUID | None = None
    printer_id: uuid.UUID | None = None
    bureau_provider: str | None = None
    copies: int = Field(default=1, ge=1, le=999)
    options: dict[str, Any] = Field(default_factory=dict)
    recipient: dict[str, Any] | None = None
    requires_certified_mail: bool = False


class PrintJobResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    target: PrintTarget
    status: PrintJobStatus
    document_id: uuid.UUID | None
    account_id: uuid.UUID | None
    consumer_id: uuid.UUID | None
    printer_id: uuid.UUID | None
    bureau_provider: str | None
    provider_job_id: str | None
    copies: int
    options: dict[str, Any]
    recipient: dict[str, Any] | None
    requires_certified_mail: bool
    tracking_number: str | None
    submitted_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
