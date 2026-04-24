"""Microsoft Teams Compliance Recording bot adapter.

Heavyweight option: register a Teams Compliance Recording bot
through Microsoft 365 admin so all Teams calls for tagged users
mirror to your bot, where you receive media + lifecycle in real
time. This is what NICE/Verint/ASC do; it's the only way to get
*real* CTI in a pure Teams-cloud (no SBC) deployment.
"""

from __future__ import annotations

from dcs_api.telephony.adapter import AdapterDescriptor, TelephonyCapabilities, register_adapter
from dcs_api.telephony.adapters._base import StubAdapter


@register_adapter
class TeamsComplianceRecordingAdapter(StubAdapter):
    id = "teams_compliance"
    label = "Teams Compliance Recording"
    capabilities = TelephonyCapabilities(
        click_to_call=True,
        inbound_screen_pop=True,
        server_recording=True,
        realtime_events=True,
        presence=True,
        softphone_in_app=False,
        sms=False,
        dialer="none",
        notes=(
            "Requires a registered Microsoft Teams Compliance Recording "
            "policy and a bot deployment. Heaviest of the three Teams "
            "options; used when an SBC isn't available."
        ),
    )
    descriptor = AdapterDescriptor(
        id="teams_compliance",
        label="Microsoft Teams — Compliance Recording bot",
        family="microsoft_teams",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "tenant_id", "label": "Azure AD Tenant ID", "type": "text", "required": True},
                {"key": "bot_app_id", "label": "Bot App ID", "type": "text", "required": True},
                {"key": "bot_app_secret", "label": "Bot Client Secret", "type": "secret", "required": True},
                {"key": "policy_name", "label": "Compliance Recording Policy Name", "type": "text", "required": True},
                {"key": "bot_endpoint", "label": "Bot Public Endpoint URL", "type": "text", "required": True},
            ]
        },
        docs_url="https://learn.microsoft.com/en-us/microsoftteams/teams-recording-policy",
    )
