"""PostGrid print/mail bureau."""

from __future__ import annotations

from dcs_api.printing.adapter import PrintAdapterDescriptor, PrintCapabilities, register_bureau
from dcs_api.printing.adapters._base import StubBureau


@register_bureau
class PostGridBureau(StubBureau):
    id = "postgrid"
    label = "PostGrid"
    capabilities = PrintCapabilities(
        duplex=True,
        color=True,
        certified_mail=True,
        bulk=True,
        silent=True,
        address_validation=True,
        return_envelope=True,
        tracking=True,
        paper_sizes=("letter", "legal", "envelope_10"),
    )
    descriptor = PrintAdapterDescriptor(
        id="postgrid",
        label="PostGrid",
        family="bureau",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
                {"key": "live_mode", "label": "Use live API", "type": "checkbox", "default": False},
                {"key": "default_from_contact_id", "label": "Default From-Contact ID", "type": "text", "required": True},
                {"key": "default_color", "label": "Default to color", "type": "checkbox", "default": False},
                {"key": "default_double_sided", "label": "Default to duplex", "type": "checkbox", "default": True},
                {"key": "send_certified_default", "label": "Send certified mail by default", "type": "checkbox", "default": False},
            ]
        },
        docs_url="https://docs.postgrid.com/",
    )
