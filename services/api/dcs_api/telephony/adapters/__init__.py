"""Concrete telephony adapter implementations.

Each module here registers exactly one adapter via the
``@register_adapter`` decorator. Adding a new provider is a single
file: declare ``id``, ``label``, ``descriptor``, and a
``TelephonyCapabilities`` flag set, then implement the action methods
when credentials/SDK are available.

The current set ships as *stubs* — capabilities are accurate so the
UI behaves correctly, but the action methods raise
``NotImplementedError`` until provider SDKs are wired up. This keeps
the configuration UX usable today and lets each integration land
incrementally.
"""

from dcs_api.telephony.adapters import (  # noqa: F401
    asterisk_ari,
    cisco_ucm,
    generic_sip,
    none,
    teams_compliance,
    teams_direct_routing,
    teams_graph,
    teams_tellink,
    threecx,
    twilio,
    vonage,
)
