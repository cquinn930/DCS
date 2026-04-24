"""Panini Vision desktop check scanner.

Direct device-control path via Panini's Vision API (or the OPOS
driver shim). Most common point-of-payment scanner in U.S.
collections shops; runs in Electron because it needs the local USB
device.
"""

from __future__ import annotations

from dcs_api.scanning.adapter import ScanAdapterDescriptor, ScanCapabilities, register_check
from dcs_api.scanning.adapters._base import StubCheck


@register_check
class PaniniCheckAdapter(StubCheck):
    id = "check_panini"
    label = "Panini (Vision API)"
    capabilities = ScanCapabilities(
        duplex=True,
        color=False,
        multi_page=False,
        micr_parse=True,
        endorse=True,
        image_quality_assurance=True,
        requires_electron=True,
        notes="USB-attached Panini desk scanner; driver runs in the Electron client.",
    )
    descriptor = ScanAdapterDescriptor(
        id="check_panini",
        label="Panini Vision (Electron, USB)",
        family="check",
        kind="check",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "device_index", "label": "Device Index", "type": "number", "default": 0},
                {"key": "endorsement_text", "label": "Endorsement Print Text", "type": "text", "required": False},
                {"key": "iqa_min_score", "label": "Minimum IQA Score", "type": "number", "default": 80},
            ]
        },
    )
