"""X9.37 (ICL / Check 21) image-cash-letter file ingest.

Generic adapter that accepts an X9.37 file from any vendor's check
scanner. Most desk scanners (Digital Check, Panini, Canon CR-series)
emit X9.37 if asked, so this is the safest "works with anything"
default. The Panini-specific adapter above adds direct device
control through the Vision API.
"""

from __future__ import annotations

from dcs_api.scanning.adapter import ScanAdapterDescriptor, ScanCapabilities, register_check
from dcs_api.scanning.adapters._base import StubCheck


@register_check
class X937CheckAdapter(StubCheck):
    id = "check_x937"
    label = "X9.37 (Check 21) ingest"
    capabilities = ScanCapabilities(
        duplex=True,
        color=False,
        multi_page=False,
        micr_parse=True,
        endorse=False,
        image_quality_assurance=True,
        notes="Accepts X9.37 ICL files from any vendor's check scanner.",
    )
    descriptor = ScanAdapterDescriptor(
        id="check_x937",
        label="X9.37 ICL file ingest",
        family="check",
        kind="check",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "iqa_min_score", "label": "Minimum IQA Score (0-100)", "type": "number", "default": 80},
                {"key": "auto_match_account_by_amount", "label": "Auto-match account by exact amount", "type": "checkbox", "default": False},
            ]
        },
        docs_url="https://www.frbservices.org/resources/financial-services/check/x9-standards.html",
    )
