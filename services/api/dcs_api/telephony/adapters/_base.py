"""Shared scaffolding for stub adapters.

Real adapters override the action methods. The stubs here keep the
UI configurable (capabilities are real) without needing live SDKs.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, ClassVar

from dcs_api.telephony.adapter import (
    AdapterDescriptor,
    CallContext,
    InboundCallEvent,
    TelephonyCapabilities,
)


class StubAdapter:
    """Common base — adapters extend and set class attributes."""

    id: ClassVar[str] = "stub"
    label: ClassVar[str] = "Stub"
    capabilities: ClassVar[TelephonyCapabilities] = TelephonyCapabilities()
    descriptor: ClassVar[AdapterDescriptor]

    def __init__(self, tenant_id: str, config: dict[str, Any]) -> None:
        self.tenant_id = tenant_id
        self.config = config or {}

    async def click_to_call(
        self,
        to_e164: str,
        from_e164: str | None,
        ctx: CallContext,
    ) -> str:
        raise NotImplementedError(
            f"{self.id}: click_to_call is not yet implemented for this adapter"
        )

    async def hangup(self, provider_call_sid: str) -> None:
        raise NotImplementedError(f"{self.id}: hangup is not yet implemented")

    async def fetch_recording(self, provider_call_sid: str) -> bytes | None:
        return None

    def parse_inbound_webhook(self, payload: dict[str, Any]) -> InboundCallEvent | None:
        return None

    async def healthcheck(self) -> dict[str, Any]:
        return {
            "ok": True,
            "adapter": self.id,
            "configured": bool(self.config),
            "note": "stub adapter — provider SDK not yet wired",
        }

    async def stream_events(self) -> AsyncIterator[InboundCallEvent]:
        if False:
            yield  # type: ignore[unreachable]
