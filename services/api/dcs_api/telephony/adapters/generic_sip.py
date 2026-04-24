"""Generic SIP adapter — bring-your-own-PBX softphone in Electron.

Last-resort coverage for any SIP-compliant PBX. Capabilities are
deliberately minimal: dial out, presence via REGISTER, no central
event stream and no recording. Better than nothing for tenants
whose PBX has no programmable API.
"""

from __future__ import annotations

from dcs_api.telephony.adapter import AdapterDescriptor, TelephonyCapabilities, register_adapter
from dcs_api.telephony.adapters._base import StubAdapter


@register_adapter
class GenericSIPAdapter(StubAdapter):
    id = "generic_sip"
    label = "Generic SIP"
    capabilities = TelephonyCapabilities(
        click_to_call=True,
        inbound_screen_pop=False,
        server_recording=False,
        realtime_events=False,
        presence=True,
        softphone_in_app=True,
        sms=False,
        dialer="none",
        requires_electron=True,
        notes=(
            "Runs sip.js inside the Electron client and registers as a "
            "SIP endpoint against the tenant's PBX. No central CTI — "
            "calls happen entirely on the agent's machine."
        ),
    )
    descriptor = AdapterDescriptor(
        id="generic_sip",
        label="Generic SIP (Electron softphone)",
        family="sip",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "registrar", "label": "SIP Registrar Host", "type": "text", "required": True},
                {"key": "realm", "label": "SIP Realm", "type": "text", "required": False},
                {"key": "transport", "label": "Transport", "type": "select", "options": ["udp", "tcp", "tls", "wss"], "default": "tls"},
                {"key": "port", "label": "Port", "type": "number", "default": 5061},
                {"key": "per_user_credentials", "label": "Each user provides their own SIP credentials", "type": "checkbox", "default": True},
                {"key": "outbound_proxy", "label": "Outbound Proxy (optional)", "type": "text", "required": False},
            ]
        },
    )
