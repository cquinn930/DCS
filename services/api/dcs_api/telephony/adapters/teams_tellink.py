"""Microsoft Teams via tel: URI hand-off.

Cheapest, most universal Teams integration: anywhere a phone number
is rendered, we link to ``tel:+1...`` which the OS hands to whatever
app has registered the protocol — Teams when Teams Phone is enabled.
No webhooks, no Graph API, no real-time CTI; this is the "we
technically work with Teams" baseline.
"""

from __future__ import annotations

from dcs_api.telephony.adapter import AdapterDescriptor, TelephonyCapabilities, register_adapter
from dcs_api.telephony.adapters._base import StubAdapter


@register_adapter
class TeamsTelLinkAdapter(StubAdapter):
    id = "teams_tellink"
    label = "Microsoft Teams (tel: hand-off)"
    capabilities = TelephonyCapabilities(
        click_to_call=True,
        inbound_screen_pop=False,
        server_recording=False,
        realtime_events=False,
        presence=False,
        softphone_in_app=False,
        sms=False,
        notes=(
            "Click-to-call only. The browser/Electron emits a tel: URI which "
            "Teams handles when registered as the system phone app. No CTI, "
            "no inbound screen-pop, no recording integration — pick a deeper "
            "Teams adapter if you need those."
        ),
    )
    descriptor = AdapterDescriptor(
        id="teams_tellink",
        label="Microsoft Teams — tel: hand-off (no CTI)",
        family="microsoft_teams",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "default_from", "label": "Default Caller ID (E.164, info only)", "type": "text", "required": False},
            ]
        },
        docs_url="https://learn.microsoft.com/en-us/microsoftteams/teams-add-on-licensing/calling-plan-landing-page",
    )
