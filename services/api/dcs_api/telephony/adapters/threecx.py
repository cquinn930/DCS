"""3CX adapter via Call Control API."""

from __future__ import annotations

from dcs_api.telephony.adapter import AdapterDescriptor, TelephonyCapabilities, register_adapter
from dcs_api.telephony.adapters._base import StubAdapter


@register_adapter
class ThreeCXAdapter(StubAdapter):
    id = "threecx"
    label = "3CX"
    capabilities = TelephonyCapabilities(
        click_to_call=True,
        inbound_screen_pop=True,
        server_recording=True,
        realtime_events=True,
        presence=True,
        softphone_in_app=False,
        sms=False,
        dialer="preview",
        requires_lan_bridge=True,
    )
    descriptor = AdapterDescriptor(
        id="threecx",
        label="3CX (REST + WebSocket)",
        family="on_prem_pbx",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "base_url", "label": "3CX Server URL", "type": "text", "required": True, "placeholder": "https://pbx.example.com:5001"},
                {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
                {"key": "extension_field", "label": "DCS user attribute → 3CX extension", "type": "text", "required": False, "default": "preferred_username"},
                {"key": "via_bridge", "label": "Use DCS Bridge / Electron Forwarder", "type": "checkbox", "default": False},
            ]
        },
        docs_url="https://www.3cx.com/docs/manual/call-control-api/",
    )
