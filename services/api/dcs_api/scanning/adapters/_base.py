"""Shared base classes for stub scan adapters."""

from __future__ import annotations

from typing import Any, ClassVar

from dcs_api.scanning.adapter import (
    ParsedCheck,
    ScanAdapterDescriptor,
    ScanCapabilities,
)


class StubDoc:
    id: ClassVar[str] = "stub_doc"
    label: ClassVar[str] = "Stub Document Scanner"
    capabilities: ClassVar[ScanCapabilities] = ScanCapabilities()
    descriptor: ClassVar[ScanAdapterDescriptor]

    def __init__(self, tenant_id: str, scanner_config: dict[str, Any]) -> None:
        self.tenant_id = tenant_id
        self.scanner_config = scanner_config or {}

    async def receive(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "adapter": self.id,
            "note": "stub adapter — would persist scanned pages and route to documents pipeline",
            "page_count": payload.get("page_count"),
        }

    async def healthcheck(self) -> dict[str, Any]:
        return {"ok": True, "adapter": self.id, "note": "stub"}


class StubCheck:
    id: ClassVar[str] = "stub_check"
    label: ClassVar[str] = "Stub Check Scanner"
    capabilities: ClassVar[ScanCapabilities] = ScanCapabilities(micr_parse=True)
    descriptor: ClassVar[ScanAdapterDescriptor]

    def __init__(self, tenant_id: str, scanner_config: dict[str, Any]) -> None:
        self.tenant_id = tenant_id
        self.scanner_config = scanner_config or {}

    async def parse(self, payload: dict[str, Any]) -> ParsedCheck:
        return ParsedCheck(
            routing_number=payload.get("routing_number"),
            bank_account_last4=payload.get("bank_account_last4"),
            check_number=payload.get("check_number"),
            amount_cents=payload.get("amount_cents"),
            payer_name=payload.get("payer_name"),
            front_image_uri=payload.get("front_image_uri"),
            back_image_uri=payload.get("back_image_uri"),
            raw=payload,
        )

    async def healthcheck(self) -> dict[str, Any]:
        return {"ok": True, "adapter": self.id, "note": "stub"}
