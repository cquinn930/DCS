"""Dynamsoft DWT — commercial cross-platform scanning SDK in the browser."""

from __future__ import annotations

from dcs_api.scanning.adapter import ScanAdapterDescriptor, ScanCapabilities, register_document
from dcs_api.scanning.adapters._base import StubDoc


@register_document
class DynamsoftAdapter(StubDoc):
    id = "dynamsoft"
    label = "Dynamsoft DWT"
    capabilities = ScanCapabilities(
        duplex=True,
        color=True,
        multi_page=True,
        auto_feeder=True,
        barcode_detect=True,
        blank_page_drop=True,
        ocr_inline=True,
        notes="Browser-side scanning via the Dynamsoft Web TWAIN service. License key required.",
    )
    descriptor = ScanAdapterDescriptor(
        id="dynamsoft",
        label="Dynamsoft Web TWAIN",
        family="desktop",
        kind="document",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "license_key", "label": "Product Key", "type": "secret", "required": True},
                {"key": "service_port", "label": "DWT Service Port", "type": "number", "default": 18622},
                {"key": "ocr_language", "label": "OCR Language", "type": "select", "options": ["eng", "spa", "fra", "deu"], "default": "eng"},
            ]
        },
        docs_url="https://www.dynamsoft.com/web-twain/docs/",
    )
