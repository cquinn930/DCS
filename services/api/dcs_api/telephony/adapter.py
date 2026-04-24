"""Provider-agnostic telephony adapter Protocol and registry.

Every concrete adapter (Vonage, Twilio, Teams in three flavors,
Asterisk/FreePBX/3CX, Cisco UCM, generic SIP) implements
``TelephonyAdapter`` and is registered via ``register_adapter``.
The router and UI never reach for a specific adapter — they look up
the active one through ``get_adapter(tenant)`` and feature-flag UI
controls off ``adapter.capabilities``.

The adapter implementations themselves live in ``adapters/`` and are
*deliberately stubbed* in this revision: they declare their
capabilities (so the UI works correctly today) and raise
``NotImplementedError`` from action methods. Wiring up the actual
provider SDKs is per-customer integration work and ships behind a
feature flag once credentials are in hand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any,
    AsyncIterator,
    ClassVar,
    Literal,
    Protocol,
    runtime_checkable,
)


DialerMode = Literal["none", "preview", "progressive", "predictive"]


@dataclass(frozen=True)
class TelephonyCapabilities:
    """What an adapter can and can't do.

    Drives both the UI (which controls to render — recording toggle,
    softphone, dialer campaign button) and the API (which endpoints
    return 501 vs do real work).
    """

    click_to_call: bool = False
    inbound_screen_pop: bool = False
    server_recording: bool = False
    realtime_events: bool = False
    presence: bool = False
    softphone_in_app: bool = False
    sms: bool = False
    fax: bool = False
    dialer: DialerMode = "none"

    requires_electron: bool = False
    requires_lan_bridge: bool = False
    notes: str = ""


@dataclass(frozen=True)
class AdapterDescriptor:
    """Metadata used by the Settings UI to render the provider picker.

    ``config_schema`` is a small JSON-schema-ish dict of the per-tenant
    fields the adapter needs (host, client_id, secret_ref, etc.). The
    UI walks it to render a generic form so we don't write a bespoke
    React form per provider.
    """

    id: str
    label: str
    family: Literal[
        "cloud",
        "microsoft_teams",
        "on_prem_pbx",
        "sip",
        "none",
    ]
    capabilities: TelephonyCapabilities
    config_schema: dict[str, Any] = field(default_factory=dict)
    docs_url: str | None = None


@dataclass
class CallContext:
    """Soft context passed when initiating an outbound call."""

    agent_user_id: str
    consumer_id: str | None = None
    account_id: str | None = None
    note: str | None = None


@dataclass
class InboundCallEvent:
    """Adapter-normalized inbound-call notification."""

    adapter_id: str
    provider_call_sid: str
    from_e164: str | None
    to_e164: str | None
    received_at: str
    raw: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class TelephonyAdapter(Protocol):
    """The contract every telephony provider implements.

    Adapters MUST set ``id`` and ``capabilities`` as class attributes.
    Action methods are async because most underlying SDKs are
    network-bound; pure-stub adapters can return immediately or raise
    ``NotImplementedError``.
    """

    id: ClassVar[str]
    label: ClassVar[str]
    capabilities: ClassVar[TelephonyCapabilities]

    def __init__(self, tenant_id: str, config: dict[str, Any]) -> None: ...

    async def click_to_call(
        self,
        to_e164: str,
        from_e164: str | None,
        ctx: CallContext,
    ) -> str:
        """Initiate an outbound call. Returns provider call SID."""

    async def hangup(self, provider_call_sid: str) -> None: ...

    async def fetch_recording(self, provider_call_sid: str) -> bytes | None:
        """Return the recording bytes if the adapter stores them server-side."""

    def parse_inbound_webhook(self, payload: dict[str, Any]) -> InboundCallEvent | None:
        """Translate a provider webhook into our canonical event shape."""

    async def healthcheck(self) -> dict[str, Any]:
        """Used by the 'Test connection' button in Settings."""

    async def stream_events(self) -> AsyncIterator[InboundCallEvent]:
        """For adapters that push (Asterisk AMI/ARI, SIP); cloud adapters use webhooks instead."""
        if False:  # pragma: no cover - stays a generator
            yield  # type: ignore[unreachable]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[TelephonyAdapter]] = {}


def register_adapter(cls: type[TelephonyAdapter]) -> type[TelephonyAdapter]:
    """Class decorator used by every concrete adapter at import time."""
    _REGISTRY[cls.id] = cls
    return cls


def get_adapter_class(adapter_id: str) -> type[TelephonyAdapter] | None:
    return _REGISTRY.get(adapter_id)


def get_adapter(adapter_id: str, tenant_id: str, config: dict[str, Any]) -> TelephonyAdapter | None:
    cls = _REGISTRY.get(adapter_id)
    if cls is None:
        return None
    return cls(tenant_id=tenant_id, config=config)


def list_adapter_descriptors() -> list[AdapterDescriptor]:
    """All registered adapters, for the Settings UI."""
    descriptors: list[AdapterDescriptor] = []
    for cls in _REGISTRY.values():
        desc = getattr(cls, "descriptor", None)
        if desc is None:
            continue
        descriptors.append(desc)
    return descriptors


# Importing the adapters package triggers @register_adapter on each
# stub. We do this at module import so callers of get_adapter /
# list_adapter_descriptors don't have to.
from dcs_api.telephony import adapters  # noqa: E402, F401
