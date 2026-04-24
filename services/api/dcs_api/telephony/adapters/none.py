"""No-telephony adapter — used when a tenant explicitly disables phone integration."""

from __future__ import annotations

from dcs_api.telephony.adapter import AdapterDescriptor, TelephonyCapabilities, register_adapter
from dcs_api.telephony.adapters._base import StubAdapter


@register_adapter
class NoneAdapter(StubAdapter):
    id = "none"
    label = "Disabled"
    capabilities = TelephonyCapabilities()
    descriptor = AdapterDescriptor(
        id="none",
        label="Disabled",
        family="none",
        capabilities=capabilities,
        config_schema={},
    )
