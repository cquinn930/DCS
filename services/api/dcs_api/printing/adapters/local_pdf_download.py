"""PDF download fallback — no native print, just hand the user a PDF.

This is the safest default for a browser-only tenant. The "print" action
returns a signed download URL; the browser opens its own print dialog
when the user clicks Print on the PDF preview.
"""

from __future__ import annotations

from dcs_api.printing.adapter import PrintAdapterDescriptor, PrintCapabilities, register_local
from dcs_api.printing.adapters._base import StubLocal


@register_local
class PdfDownloadLocal(StubLocal):
    id = "pdf_download"
    label = "PDF Download"
    capabilities = PrintCapabilities(
        duplex=False,
        color=True,
        bulk=False,
        silent=False,
        paper_sizes=("letter", "legal", "a4"),
        notes="Browser fallback — user prints from the PDF viewer.",
    )
    descriptor = PrintAdapterDescriptor(
        id="pdf_download",
        label="PDF Download (browser fallback)",
        family="local",
        capabilities=capabilities,
        config_schema={"fields": []},
    )
