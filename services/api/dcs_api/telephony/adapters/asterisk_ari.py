"""Asterisk / FreePBX adapter via ARI (REST + WebSocket).

Covers Asterisk, FreePBX, AsteriskNow, and most derivatives. ARI
gives a clean REST surface for originating calls plus a WebSocket
push of stasis events that we forward into ``CallEvent``. AMI is
also supported as a fallback for older PBXs but ARI is preferred.
"""

from __future__ import annotations

from dcs_api.telephony.adapter import AdapterDescriptor, TelephonyCapabilities, register_adapter
from dcs_api.telephony.adapters._base import StubAdapter


@register_adapter
class AsteriskARIAdapter(StubAdapter):
    id = "asterisk_ari"
    label = "Asterisk / FreePBX (ARI)"
    capabilities = TelephonyCapabilities(
        click_to_call=True,
        inbound_screen_pop=True,
        server_recording=True,
        realtime_events=True,
        presence=True,
        softphone_in_app=False,
        sms=False,
        dialer="progressive",
        requires_lan_bridge=True,
        notes=(
            "On-prem PBX. For SaaS-hosted DCS, the Electron client or "
            "DCS PBX Bridge service must run on the LAN to relay ARI "
            "events to the cloud server."
        ),
    )
    descriptor = AdapterDescriptor(
        id="asterisk_ari",
        label="Asterisk / FreePBX — ARI",
        family="on_prem_pbx",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "ari_url", "label": "ARI Base URL", "type": "text", "required": True, "placeholder": "http://10.0.0.5:8088/ari"},
                {"key": "ari_user", "label": "ARI Username", "type": "text", "required": True},
                {"key": "ari_password", "label": "ARI Password", "type": "secret", "required": True},
                {"key": "stasis_app", "label": "Stasis Application Name", "type": "text", "required": True, "default": "dcs"},
                {"key": "context", "label": "Outbound Dialplan Context", "type": "text", "required": False, "default": "from-internal"},
                {"key": "via_bridge", "label": "Use DCS Bridge / Electron Forwarder", "type": "checkbox", "default": True},
            ]
        },
        docs_url="https://wiki.asterisk.org/wiki/display/AST/Asterisk+REST+Interface",
    )
