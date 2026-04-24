"""Scanning schemas — config, capabilities, scanners, jobs, checks."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from dcs_api.models.scanning import (
    CheckStatus,
    ScannerKind,
    ScannerTransport,
    ScanJobStatus,
)
from dcs_api.schemas.common import TimestampSchema


# ---------------------------------------------------------------------------
# Tenant config (settings.scanning)
# ---------------------------------------------------------------------------


class ScanningTenantConfig(BaseModel):
    """Per-tenant scanning behavior — defaults plus check-handling options."""

    auto_route_by_barcode: bool = True
    auto_route_by_account_number: bool = True
    routing_min_confidence: int = Field(default=80, ge=0, le=100)
    unrouted_review_inbox: str | None = None

    # Check-specific (apply only when scanner.kind == CHECK)
    require_dual_review_above_cents: int | None = Field(default=100_000, ge=0)
    require_micr_match_for_auto_apply: bool = True
    auto_create_payment_on_clear: bool = True
    default_deposit_account_id: uuid.UUID | None = None


class ScanningTenantConfigUpdate(BaseModel):
    auto_route_by_barcode: bool | None = None
    auto_route_by_account_number: bool | None = None
    routing_min_confidence: int | None = Field(default=None, ge=0, le=100)
    unrouted_review_inbox: str | None = None
    require_dual_review_above_cents: int | None = Field(default=None, ge=0)
    require_micr_match_for_auto_apply: bool | None = None
    auto_create_payment_on_clear: bool | None = None
    default_deposit_account_id: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# Capabilities + adapter catalog
# ---------------------------------------------------------------------------


class ScanCapabilitiesOut(BaseModel):
    duplex: bool
    color: bool
    multi_page: bool
    auto_feeder: bool
    barcode_detect: bool = False
    blank_page_drop: bool = False
    ocr_inline: bool = False
    micr_parse: bool = False
    endorse: bool = False
    image_quality_assurance: bool = False
    requires_electron: bool
    notes: str = ""


class ScanAdapterDescriptorOut(BaseModel):
    id: str
    label: str
    family: Literal["mfp", "desktop", "check", "other"]
    kind: Literal["document", "check", "id", "other"]
    capabilities: ScanCapabilitiesOut
    config_schema: dict[str, Any]
    docs_url: str | None = None


# ---------------------------------------------------------------------------
# Scanner CRUD
# ---------------------------------------------------------------------------


class ScannerCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    location: str | None = None
    kind: ScannerKind = ScannerKind.DOCUMENT
    transport: ScannerTransport = ScannerTransport.MFP_SFTP
    config: dict[str, Any] = Field(default_factory=dict)
    intake_inbox_email: str | None = None
    deposit_account_id: uuid.UUID | None = None
    is_active: bool = True


class ScannerUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    location: str | None = None
    kind: ScannerKind | None = None
    transport: ScannerTransport | None = None
    config: dict[str, Any] | None = None
    intake_inbox_email: str | None = None
    deposit_account_id: uuid.UUID | None = None
    is_active: bool | None = None


class ScannerResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    location: str | None
    kind: ScannerKind
    transport: ScannerTransport
    config: dict[str, Any]
    intake_inbox_email: str | None
    deposit_account_id: uuid.UUID | None
    is_active: bool
    has_intake_token: bool = False


class ScannerWithIntakeToken(ScannerResponse):
    """Returned only on create / token-rotate; the plaintext token is shown once."""
    intake_token: str | None = None


# ---------------------------------------------------------------------------
# Scan jobs
# ---------------------------------------------------------------------------


class ScanIntakeRequest(BaseModel):
    """MFP-side intake payload."""

    intake_token: str
    page_count: int | None = None
    storage_uri: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None
    sha256: str | None = None
    captured_at: datetime | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class ScanJobResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    scanner_id: uuid.UUID | None
    status: ScanJobStatus
    page_count: int | None
    storage_uri: str | None
    mime_type: str | None
    file_size_bytes: int | None
    sha256: str | None
    document_id: uuid.UUID | None
    account_id: uuid.UUID | None
    consumer_id: uuid.UUID | None
    routing_confidence: int | None
    error_message: str | None
    captured_at: datetime | None
    routed_at: datetime | None


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


class CheckResponse(TimestampSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    scan_job_id: uuid.UUID
    routing_number: str | None
    bank_account_number_last4: str | None
    check_number: str | None
    amount_cents: int | None
    payer_name: str | None
    memo: str | None
    front_image_uri: str | None
    back_image_uri: str | None
    account_id: uuid.UUID | None
    consumer_id: uuid.UUID | None
    deposit_account_id: uuid.UUID | None
    status: CheckStatus
    deposited_at: datetime | None
    cleared_at: datetime | None
    returned_at: datetime | None
    return_reason: str | None
    payment_id: uuid.UUID | None


class CheckUpdate(BaseModel):
    """Owner/admin can correct OCR errors before deposit."""

    routing_number: str | None = Field(default=None, max_length=16)
    bank_account_number_last4: str | None = Field(default=None, max_length=8)
    check_number: str | None = None
    amount_cents: int | None = Field(default=None, ge=1)
    payer_name: str | None = None
    memo: str | None = None
    account_id: uuid.UUID | None = None
    consumer_id: uuid.UUID | None = None
    deposit_account_id: uuid.UUID | None = None
    status: CheckStatus | None = None
    return_reason: str | None = None
