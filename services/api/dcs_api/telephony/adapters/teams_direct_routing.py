"""Microsoft Teams with Direct Routing — listen on the SBC.

When the tenant uses Teams Direct Routing, every call traverses an
SBC (AudioCodes, Ribbon, AnyNode) the customer controls. The
adapter taps the SBC's REST/SNMP feed for real-time call events
and bypasses Microsoft entirely from a CTI standpoint. Teams
becomes "just the audio endpoint." This is the right answer for
mid-market Teams + collections shops.
"""

from __future__ import annotations

from dcs_api.telephony.adapter import AdapterDescriptor, TelephonyCapabilities, register_adapter
from dcs_api.telephony.adapters._base import StubAdapter


@register_adapter
class TeamsDirectRoutingAdapter(StubAdapter):
    id = "teams_direct_routing"
    label = "Teams Direct Routing (SBC)"
    capabilities = TelephonyCapabilities(
        click_to_call=True,
        inbound_screen_pop=True,
        server_recording=True,
        realtime_events=True,
        presence=False,
        softphone_in_app=False,
        sms=False,
        dialer="preview",
        requires_lan_bridge=True,
        notes=(
            "Requires that DCS can reach the SBC's management API "
            "(usually on the customer LAN). For SaaS-hosted DCS, the "
            "Electron client or the DCS PBX Bridge service forwards "
            "events from the SBC up to this adapter."
        ),
    )
    descriptor = AdapterDescriptor(
        id="teams_direct_routing",
        label="Microsoft Teams — Direct Routing via SBC",
        family="microsoft_teams",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "sbc_vendor", "label": "SBC Vendor", "type": "select", "options": ["audiocodes", "ribbon", "anynode", "oracle", "other"], "required": True},
                {"key": "sbc_host", "label": "SBC Management Host", "type": "text", "required": True},
                {"key": "sbc_username", "label": "Username", "type": "text", "required": True},
                {"key": "sbc_password", "label": "Password", "type": "secret", "required": True},
                {"key": "trunk_name", "label": "Teams Trunk Name", "type": "text", "required": False},
                {"key": "via_bridge", "label": "Use DCS Bridge / Electron Forwarder", "type": "checkbox", "default": True},
            ]
        },
        docs_url="https://learn.microsoft.com/en-us/microsoftteams/direct-routing-landing-page",
    )
