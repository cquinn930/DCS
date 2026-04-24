"""Scan adapter Protocols and registries.

Adapters describe how a scanner *delivers* pages to the server (TWAIN
in Electron, MFP scan-to-SFTP, MFP scan-to-email, X9.37 check image
file, etc.) plus what they can extract on the way.

We keep two separate Protocols — ``DocumentScanAdapter`` and
``CheckScanAdapter`` — because check scanners do extra work
(MICR parse, front+back image, X9.37 metadata) and have a separate
permission gate (``HANDLE_CHECKS``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class ScanCapabilities:
    """What a scan adapter can deliver."""

    duplex: bool = False
    color: bool = False
    multi_page: bool = False
    auto_feeder: bool = False
    barcode_detect: bool = False
    blank_page_drop: bool = False
    ocr_inline: bool = False

    micr_parse: bool = False
    endorse: bool = False
    image_quality_assurance: bool = False

    requires_electron: bool = False
    notes: str = ""


@dataclass(frozen=True)
class ScanAdapterDescriptor:
    id: str
    label: str
    family: Literal["mfp", "desktop", "check", "other"]
    kind: Literal["document", "check", "id", "other"]
    capabilities: ScanCapabilities
    config_schema: dict[str, Any] = field(default_factory=dict)
    docs_url: str | None = None


# ---------------------------------------------------------------------------
# Document / ID scanning
# ---------------------------------------------------------------------------


@runtime_checkable
class DocumentScanAdapter(Protocol):
    id: ClassVar[str]
    label: ClassVar[str]
    capabilities: ClassVar[ScanCapabilities]
    descriptor: ClassVar[ScanAdapterDescriptor]

    def __init__(self, tenant_id: str, scanner_config: dict[str, Any]) -> None: ...

    async def receive(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Process an inbound batch (file path, base64 PDF, etc.)."""

    async def healthcheck(self) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Check scanning
# ---------------------------------------------------------------------------


@dataclass
class ParsedCheck:
    """Normalized output of a check-scan adapter."""

    routing_number: str | None
    bank_account_last4: str | None
    check_number: str | None
    amount_cents: int | None
    payer_name: str | None
    front_image_uri: str | None
    back_image_uri: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class CheckScanAdapter(Protocol):
    id: ClassVar[str]
    label: ClassVar[str]
    capabilities: ClassVar[ScanCapabilities]
    descriptor: ClassVar[ScanAdapterDescriptor]

    def __init__(self, tenant_id: str, scanner_config: dict[str, Any]) -> None: ...

    async def parse(self, payload: dict[str, Any]) -> ParsedCheck:
        """Parse a single check capture (one front+back pair)."""

    async def healthcheck(self) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------

_DOC: dict[str, type[DocumentScanAdapter]] = {}
_CHECK: dict[str, type[CheckScanAdapter]] = {}


def register_document(cls: type[DocumentScanAdapter]) -> type[DocumentScanAdapter]:
    _DOC[cls.id] = cls
    return cls


def register_check(cls: type[CheckScanAdapter]) -> type[CheckScanAdapter]:
    _CHECK[cls.id] = cls
    return cls


def get_document_adapter(adapter_id: str, tenant_id: str, scanner_config: dict[str, Any]) -> DocumentScanAdapter | None:
    cls = _DOC.get(adapter_id)
    return cls(tenant_id=tenant_id, scanner_config=scanner_config) if cls else None


def get_check_adapter(adapter_id: str, tenant_id: str, scanner_config: dict[str, Any]) -> CheckScanAdapter | None:
    cls = _CHECK.get(adapter_id)
    return cls(tenant_id=tenant_id, scanner_config=scanner_config) if cls else None


def list_document_descriptors() -> list[ScanAdapterDescriptor]:
    return [getattr(cls, "descriptor") for cls in _DOC.values() if hasattr(cls, "descriptor")]


def list_check_descriptors() -> list[ScanAdapterDescriptor]:
    return [getattr(cls, "descriptor") for cls in _CHECK.values() if hasattr(cls, "descriptor")]


# Trigger registration of bundled adapters.
from dcs_api.scanning import adapters  # noqa: E402, F401
