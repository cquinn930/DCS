"""Telephony subsystem.

Public surface:

* ``TelephonyAdapter`` — the Protocol every provider implements.
* ``TelephonyCapabilities`` — what the active adapter can/can't do.
* ``get_adapter`` — resolves the active adapter for a tenant.
* ``list_adapter_descriptors`` — for the Settings UI's provider picker.
"""

from dcs_api.telephony.adapter import (
    CallContext,
    InboundCallEvent,
    TelephonyAdapter,
    TelephonyCapabilities,
    get_adapter,
    get_adapter_class,
    list_adapter_descriptors,
)

__all__ = [
    "CallContext",
    "InboundCallEvent",
    "TelephonyAdapter",
    "TelephonyCapabilities",
    "get_adapter",
    "get_adapter_class",
    "list_adapter_descriptors",
]
