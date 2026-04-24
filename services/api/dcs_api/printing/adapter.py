"""Print adapter Protocols and registries.

There are two distinct contracts because bureau printing and local
printing have different semantics:

* ``BureauAdapter`` is *server-to-cloud*: we POST a PDF + address and
  poll for status. Configured per-tenant in ``settings.print.bureau``.
* ``LocalPrintAdapter`` is *server-to-printer-or-client*: how a
  particular ``Printer`` row actually delivers bytes. Bound per
  printer via ``Printer.transport``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable


PaperSize = Literal["letter", "legal", "a4", "a5", "envelope_10", "label_4x6", "thermal_80mm", "thermal_58mm"]


@dataclass(frozen=True)
class PrintCapabilities:
    """What a print adapter can deliver."""

    duplex: bool = False
    color: bool = False
    certified_mail: bool = False
    bulk: bool = False
    silent: bool = False
    address_validation: bool = False
    return_envelope: bool = False
    tracking: bool = False
    paper_sizes: tuple[PaperSize, ...] = ("letter",)
    requires_electron: bool = False
    notes: str = ""


@dataclass(frozen=True)
class PrintAdapterDescriptor:
    id: str
    label: str
    family: Literal["bureau", "local", "thermal", "label", "check"]
    capabilities: PrintCapabilities
    config_schema: dict[str, Any] = field(default_factory=dict)
    docs_url: str | None = None


# ---------------------------------------------------------------------------
# Bureau adapters (Lob, PostGrid, Click2Mail, ...)
# ---------------------------------------------------------------------------


@runtime_checkable
class BureauAdapter(Protocol):
    id: ClassVar[str]
    label: ClassVar[str]
    capabilities: ClassVar[PrintCapabilities]
    descriptor: ClassVar[PrintAdapterDescriptor]

    def __init__(self, tenant_id: str, config: dict[str, Any]) -> None: ...

    async def submit(
        self,
        pdf_bytes: bytes,
        recipient: dict[str, Any],
        options: dict[str, Any],
    ) -> str:
        """Submit a print job to the bureau. Returns provider job ID."""

    async def status(self, provider_job_id: str) -> dict[str, Any]:
        """Return current status from the bureau."""

    async def healthcheck(self) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Local printer adapters (IPP, ESC/POS, ZPL, Electron, PDF download)
# ---------------------------------------------------------------------------


@runtime_checkable
class LocalPrintAdapter(Protocol):
    id: ClassVar[str]
    label: ClassVar[str]
    capabilities: ClassVar[PrintCapabilities]
    descriptor: ClassVar[PrintAdapterDescriptor]

    def __init__(self, tenant_id: str, printer_config: dict[str, Any]) -> None: ...

    async def submit(
        self,
        pdf_bytes: bytes,
        options: dict[str, Any],
    ) -> str:
        """Send the document to the printer. Returns local job reference."""

    async def healthcheck(self) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------

_BUREAU: dict[str, type[BureauAdapter]] = {}
_LOCAL: dict[str, type[LocalPrintAdapter]] = {}


def register_bureau(cls: type[BureauAdapter]) -> type[BureauAdapter]:
    _BUREAU[cls.id] = cls
    return cls


def register_local(cls: type[LocalPrintAdapter]) -> type[LocalPrintAdapter]:
    _LOCAL[cls.id] = cls
    return cls


def get_bureau_adapter(adapter_id: str, tenant_id: str, config: dict[str, Any]) -> BureauAdapter | None:
    cls = _BUREAU.get(adapter_id)
    return cls(tenant_id=tenant_id, config=config) if cls else None


def get_local_adapter(adapter_id: str, tenant_id: str, printer_config: dict[str, Any]) -> LocalPrintAdapter | None:
    cls = _LOCAL.get(adapter_id)
    return cls(tenant_id=tenant_id, printer_config=printer_config) if cls else None


def list_bureau_descriptors() -> list[PrintAdapterDescriptor]:
    return [getattr(cls, "descriptor") for cls in _BUREAU.values() if hasattr(cls, "descriptor")]


def list_local_descriptors() -> list[PrintAdapterDescriptor]:
    return [getattr(cls, "descriptor") for cls in _LOCAL.values() if hasattr(cls, "descriptor")]


# Trigger registration of bundled adapters.
from dcs_api.printing import adapters  # noqa: E402, F401
