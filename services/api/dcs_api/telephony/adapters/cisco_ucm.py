"""Cisco Unified Communications Manager (CUCM) adapter via JTAPI/AXL."""

from __future__ import annotations

from dcs_api.telephony.adapter import AdapterDescriptor, TelephonyCapabilities, register_adapter
from dcs_api.telephony.adapters._base import StubAdapter


@register_adapter
class CiscoUCMAdapter(StubAdapter):
    id = "cisco_ucm"
    label = "Cisco UCM"
    capabilities = TelephonyCapabilities(
        click_to_call=True,
        inbound_screen_pop=True,
        server_recording=False,
        realtime_events=True,
        presence=True,
        softphone_in_app=False,
        sms=False,
        dialer="preview",
        requires_lan_bridge=True,
        notes=(
            "JTAPI is JVM-only; we run a small Java sidecar that talks "
            "to UCM and exposes a REST surface this adapter consumes. "
            "AXL is used for read-only directory lookups."
        ),
    )
    descriptor = AdapterDescriptor(
        id="cisco_ucm",
        label="Cisco UCM (JTAPI sidecar + AXL)",
        family="on_prem_pbx",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "ucm_host", "label": "UCM Host", "type": "text", "required": True},
                {"key": "ucm_app_user", "label": "Application User", "type": "text", "required": True},
                {"key": "ucm_app_password", "label": "Application Password", "type": "secret", "required": True},
                {"key": "axl_user", "label": "AXL Username", "type": "text", "required": False},
                {"key": "axl_password", "label": "AXL Password", "type": "secret", "required": False},
                {"key": "sidecar_url", "label": "JTAPI Sidecar URL", "type": "text", "required": True},
            ]
        },
        docs_url="https://developer.cisco.com/docs/jtapi/",
    )
