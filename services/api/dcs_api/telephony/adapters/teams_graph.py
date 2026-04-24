"""Microsoft Teams via Graph (callRecords + presence).

Adds *post-hoc* call records, presence, and (with the right Azure
app permissions) Graph change notifications for inbound call
ringing. Real-time screen-pop is best-effort — Graph notifications
have a delivery SLA measured in seconds, not milliseconds, and bot
APIs are required for sub-second feedback.
"""

from __future__ import annotations

from dcs_api.telephony.adapter import AdapterDescriptor, TelephonyCapabilities, register_adapter
from dcs_api.telephony.adapters._base import StubAdapter


@register_adapter
class TeamsGraphAdapter(StubAdapter):
    id = "teams_graph"
    label = "Microsoft Teams (Graph API)"
    capabilities = TelephonyCapabilities(
        click_to_call=True,
        inbound_screen_pop=True,
        server_recording=False,
        realtime_events=False,
        presence=True,
        softphone_in_app=False,
        sms=False,
        notes=(
            "Inbound screen-pops are delivered via Graph change notifications "
            "and may lag actual ring by 1-3 seconds. Recording is owned by "
            "the Teams admin (Compliance Recording policy), not by us."
        ),
    )
    descriptor = AdapterDescriptor(
        id="teams_graph",
        label="Microsoft Teams — Graph API (records + presence)",
        family="microsoft_teams",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "tenant_id", "label": "Azure AD Tenant ID", "type": "text", "required": True},
                {"key": "client_id", "label": "App Registration (Client) ID", "type": "text", "required": True},
                {"key": "client_secret", "label": "Client Secret", "type": "secret", "required": True},
                {"key": "default_from", "label": "Default Caller ID (E.164)", "type": "text", "required": False},
                {"key": "subscribe_call_records", "label": "Subscribe to /communications/callRecords", "type": "checkbox", "default": True},
                {"key": "subscribe_presence", "label": "Subscribe to user presence", "type": "checkbox", "default": True},
            ]
        },
        docs_url="https://learn.microsoft.com/en-us/graph/api/resources/callrecords-callrecord",
    )
