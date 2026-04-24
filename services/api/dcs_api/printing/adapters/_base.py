"""Shared base classes for stub print adapters."""

from __future__ import annotations

from typing import Any, ClassVar

from dcs_api.printing.adapter import PrintAdapterDescriptor, PrintCapabilities


class StubBureau:
    id: ClassVar[str] = "stub_bureau"
    label: ClassVar[str] = "Stub Bureau"
    capabilities: ClassVar[PrintCapabilities] = PrintCapabilities()
    descriptor: ClassVar[PrintAdapterDescriptor]

    def __init__(self, tenant_id: str, config: dict[str, Any]) -> None:
        self.tenant_id = tenant_id
        self.config = config or {}

    async def submit(
        self,
        pdf_bytes: bytes,
        recipient: dict[str, Any],
        options: dict[str, Any],
    ) -> str:
        raise NotImplementedError(f"{self.id}: bureau submit not yet implemented")

    async def status(self, provider_job_id: str) -> dict[str, Any]:
        return {"status": "unknown", "adapter": self.id}

    async def healthcheck(self) -> dict[str, Any]:
        return {"ok": True, "adapter": self.id, "configured": bool(self.config), "note": "stub"}


class StubLocal:
    id: ClassVar[str] = "stub_local"
    label: ClassVar[str] = "Stub Local"
    capabilities: ClassVar[PrintCapabilities] = PrintCapabilities()
    descriptor: ClassVar[PrintAdapterDescriptor]

    def __init__(self, tenant_id: str, printer_config: dict[str, Any]) -> None:
        self.tenant_id = tenant_id
        self.printer_config = printer_config or {}

    async def submit(self, pdf_bytes: bytes, options: dict[str, Any]) -> str:
        raise NotImplementedError(f"{self.id}: local submit not yet implemented")

    async def healthcheck(self) -> dict[str, Any]:
        return {"ok": True, "adapter": self.id, "note": "stub"}
