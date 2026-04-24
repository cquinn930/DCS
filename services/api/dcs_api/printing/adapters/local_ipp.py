"""IPP / IPPS network printer adapter."""

from __future__ import annotations

from dcs_api.printing.adapter import PrintAdapterDescriptor, PrintCapabilities, register_local
from dcs_api.printing.adapters._base import StubLocal


@register_local
class IPPLocal(StubLocal):
    id = "ipp"
    label = "IPP/IPPS Network Printer"
    capabilities = PrintCapabilities(
        duplex=True,
        color=True,
        bulk=True,
        silent=True,
        paper_sizes=("letter", "legal", "a4", "envelope_10"),
        notes="Direct IPP submission. Server must be able to reach the printer host:port.",
    )
    descriptor = PrintAdapterDescriptor(
        id="ipp",
        label="IPP / IPPS network printer",
        family="local",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "host", "label": "Printer Host", "type": "text", "required": True},
                {"key": "port", "label": "Port", "type": "number", "default": 631},
                {"key": "queue_name", "label": "Queue Name", "type": "text", "required": True},
                {"key": "use_tls", "label": "Use IPPS (TLS)", "type": "checkbox", "default": False},
                {"key": "auth_username", "label": "Username (optional)", "type": "text", "required": False},
                {"key": "auth_password", "label": "Password (optional)", "type": "secret", "required": False},
            ]
        },
    )
