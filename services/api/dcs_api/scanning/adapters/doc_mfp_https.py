"""MFP scan-to-cloud HTTPS — MFP POSTs to /api/v1/scan/intake."""

from __future__ import annotations

from dcs_api.scanning.adapter import ScanAdapterDescriptor, ScanCapabilities, register_document
from dcs_api.scanning.adapters._base import StubDoc


@register_document
class MfpHttpsAdapter(StubDoc):
    id = "mfp_https"
    label = "MFP scan-to-HTTPS"
    capabilities = ScanCapabilities(
        duplex=True,
        color=True,
        multi_page=True,
        auto_feeder=True,
        notes="MFP POSTs scans directly to the DCS intake endpoint; uses a per-scanner intake token.",
    )
    descriptor = ScanAdapterDescriptor(
        id="mfp_https",
        label="MFP scan-to-cloud (HTTPS POST)",
        family="mfp",
        kind="document",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "endpoint_path", "label": "Endpoint URL (read-only, generated)", "type": "readonly", "default": "/api/v1/scan/intake"},
                {"key": "rotate_token", "label": "Rotate intake token", "type": "button", "action": "rotate_intake_token"},
            ]
        },
    )
