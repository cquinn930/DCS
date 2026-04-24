"""TWAIN/WIA in-app scanning via the Electron client (uses node-twain)."""

from __future__ import annotations

from dcs_api.scanning.adapter import ScanAdapterDescriptor, ScanCapabilities, register_document
from dcs_api.scanning.adapters._base import StubDoc


@register_document
class ElectronTwainAdapter(StubDoc):
    id = "electron_twain"
    label = "Electron TWAIN/WIA"
    capabilities = ScanCapabilities(
        duplex=True,
        color=True,
        multi_page=True,
        auto_feeder=True,
        barcode_detect=False,
        blank_page_drop=True,
        requires_electron=True,
        notes="Triggers the local TWAIN/WIA driver from inside the desktop client.",
    )
    descriptor = ScanAdapterDescriptor(
        id="electron_twain",
        label="Electron — TWAIN / WIA",
        family="desktop",
        kind="document",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "device_name", "label": "Driver Name (blank = prompt user)", "type": "text", "required": False},
                {"key": "default_dpi", "label": "Default DPI", "type": "select", "options": ["200", "300", "600"], "default": "300"},
                {"key": "default_color", "label": "Default Color Mode", "type": "select", "options": ["bw", "gray", "color"], "default": "gray"},
                {"key": "default_duplex", "label": "Default Duplex", "type": "checkbox", "default": True},
            ]
        },
    )
