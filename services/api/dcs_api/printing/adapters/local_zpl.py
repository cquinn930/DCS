"""ZPL Zebra-label-printer adapter."""

from __future__ import annotations

from dcs_api.printing.adapter import PrintAdapterDescriptor, PrintCapabilities, register_local
from dcs_api.printing.adapters._base import StubLocal


@register_local
class ZplLocal(StubLocal):
    id = "zpl_tcp"
    label = "ZPL Label Printer"
    capabilities = PrintCapabilities(
        duplex=False,
        color=False,
        bulk=True,
        silent=True,
        paper_sizes=("label_4x6",),
        notes="Zebra/ZPL label printer. Used for batched mailing labels.",
    )
    descriptor = PrintAdapterDescriptor(
        id="zpl_tcp",
        label="ZPL labels (Zebra) — TCP",
        family="label",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "host", "label": "Printer Host", "type": "text", "required": True},
                {"key": "port", "label": "Port", "type": "number", "default": 9100},
                {"key": "label_width_dots", "label": "Label Width (dots)", "type": "number", "default": 812},
                {"key": "label_height_dots", "label": "Label Height (dots)", "type": "number", "default": 1218},
                {"key": "dpi", "label": "DPI", "type": "select", "options": ["203", "300"], "default": "203"},
            ]
        },
    )
