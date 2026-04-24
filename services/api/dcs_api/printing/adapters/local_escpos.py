"""ESC/POS thermal-receipt-printer adapter."""

from __future__ import annotations

from dcs_api.printing.adapter import PrintAdapterDescriptor, PrintCapabilities, register_local
from dcs_api.printing.adapters._base import StubLocal


@register_local
class EscPosLocal(StubLocal):
    id = "escpos_tcp"
    label = "ESC/POS Thermal Printer"
    capabilities = PrintCapabilities(
        duplex=False,
        color=False,
        bulk=False,
        silent=True,
        paper_sizes=("thermal_80mm", "thermal_58mm"),
        notes="Receipts only. PDF is rasterized to monochrome ESC/POS commands.",
    )
    descriptor = PrintAdapterDescriptor(
        id="escpos_tcp",
        label="ESC/POS thermal (TCP)",
        family="thermal",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "host", "label": "Printer Host", "type": "text", "required": True},
                {"key": "port", "label": "Port", "type": "number", "default": 9100},
                {"key": "paper_width_mm", "label": "Paper Width (mm)", "type": "select", "options": ["58", "80"], "default": "80"},
                {"key": "cut_after", "label": "Auto-cut after print", "type": "checkbox", "default": True},
            ]
        },
    )
