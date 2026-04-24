"""Electron silent print — uses webContents.print on the desktop client."""

from __future__ import annotations

from dcs_api.printing.adapter import PrintAdapterDescriptor, PrintCapabilities, register_local
from dcs_api.printing.adapters._base import StubLocal


@register_local
class ElectronDefaultLocal(StubLocal):
    id = "electron_default"
    label = "Electron Silent Print"
    capabilities = PrintCapabilities(
        duplex=True,
        color=True,
        bulk=True,
        silent=True,
        paper_sizes=("letter", "legal", "a4", "envelope_10"),
        requires_electron=True,
        notes="Requires the DCS desktop client; uses Electron webContents.print.",
    )
    descriptor = PrintAdapterDescriptor(
        id="electron_default",
        label="Electron — silent print to OS default",
        family="local",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "device_name", "label": "OS Printer Name (blank = default)", "type": "text", "required": False},
                {"key": "duplex", "label": "Duplex", "type": "checkbox", "default": False},
                {"key": "color", "label": "Color", "type": "checkbox", "default": False},
                {"key": "copies", "label": "Default Copies", "type": "number", "default": 1},
            ]
        },
    )
