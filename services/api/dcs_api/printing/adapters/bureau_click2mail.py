"""Click2Mail bureau."""

from __future__ import annotations

from dcs_api.printing.adapter import PrintAdapterDescriptor, PrintCapabilities, register_bureau
from dcs_api.printing.adapters._base import StubBureau


@register_bureau
class Click2MailBureau(StubBureau):
    id = "click2mail"
    label = "Click2Mail"
    capabilities = PrintCapabilities(
        duplex=True,
        color=True,
        certified_mail=True,
        bulk=True,
        silent=True,
        address_validation=True,
        return_envelope=False,
        tracking=True,
        paper_sizes=("letter", "legal", "envelope_10"),
    )
    descriptor = PrintAdapterDescriptor(
        id="click2mail",
        label="Click2Mail",
        family="bureau",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "username", "label": "Username", "type": "text", "required": True},
                {"key": "password", "label": "Password", "type": "secret", "required": True},
                {"key": "default_product_id", "label": "Default Product ID", "type": "text", "required": False},
            ]
        },
        docs_url="https://api.click2mail.com/docs",
    )
