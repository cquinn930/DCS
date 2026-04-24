"""Twilio Voice + SMS adapter (stub)."""

from __future__ import annotations

from dcs_api.telephony.adapter import AdapterDescriptor, TelephonyCapabilities, register_adapter
from dcs_api.telephony.adapters._base import StubAdapter


@register_adapter
class TwilioAdapter(StubAdapter):
    id = "twilio"
    label = "Twilio"
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
        id="twilio",
        label="Twilio (Cloud)",
        family="cloud",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "account_sid", "label": "Account SID", "type": "text", "required": True},
                {"key": "auth_token", "label": "Auth Token", "type": "secret", "required": True},
                {"key": "twiml_app_sid", "label": "TwiML App SID", "type": "text", "required": True},
                {"key": "default_from", "label": "Default Caller ID (E.164)", "type": "text", "required": False},
                {"key": "workspace_sid", "label": "TaskRouter Workspace SID", "type": "text", "required": False},
            ]
        },
        docs_url="https://www.twilio.com/docs/voice",
    )
