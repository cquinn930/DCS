"""Vonage Voice + Messages.

Cloud telephony provider already named in ``docs/07_integrations.md``.
Capabilities: full CTI in browser via the Vonage Client SDK (WebRTC),
plus Messages API for SMS. Recording is server-side; we keep only
the URL/SID, not the audio.
"""

from __future__ import annotations

from dcs_api.telephony.adapter import AdapterDescriptor, TelephonyCapabilities, register_adapter
from dcs_api.telephony.adapters._base import StubAdapter


@register_adapter
class VonageAdapter(StubAdapter):
    id = "vonage"
    label = "Vonage"
    capabilities = TelephonyCapabilities(
        click_to_call=True,
        inbound_screen_pop=True,
        server_recording=True,
        realtime_events=True,
        presence=True,
        softphone_in_app=True,
        sms=True,
        fax=False,
        dialer="preview",
    )
    descriptor = AdapterDescriptor(
        id="vonage",
        label="Vonage (Cloud)",
        family="cloud",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "application_id", "label": "Application ID", "type": "text", "required": True},
                {"key": "api_key", "label": "API Key", "type": "text", "required": True},
                {"key": "api_secret", "label": "API Secret", "type": "secret", "required": True},
                {"key": "private_key", "label": "Private Key (PEM)", "type": "secret_textarea", "required": True},
                {"key": "default_from", "label": "Default Caller ID (E.164)", "type": "text", "required": False},
                {"key": "webhook_token", "label": "Webhook Verification Token", "type": "secret", "required": False},
            ]
        },
        docs_url="https://developer.vonage.com/en/voice/voice-api/overview",
    )
