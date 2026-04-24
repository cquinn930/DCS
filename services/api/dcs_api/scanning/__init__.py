"""Scan & Capture subsystem.

Adapters split into two families:

* **DocumentScanAdapter** — generic page intake, used for letters,
  IDs, and any non-check paper.
* **CheckScanAdapter** — extends the doc-scan contract with MICR
  parsing and front+back image storage so scanned checks can flow
  into the trust-deposit pipeline.

Both register in the same ``adapters/`` directory and the active set
is selected per-``Scanner`` row, so a single tenant can have e.g. an
office MFP for documents and a Panini check scanner sitting beside
it on the same agent's desktop.
"""

from dcs_api.scanning.adapter import (
    CheckScanAdapter,
    DocumentScanAdapter,
    ScanAdapterDescriptor,
    ScanCapabilities,
    get_check_adapter,
    get_document_adapter,
    list_check_descriptors,
    list_document_descriptors,
)

__all__ = [
    "CheckScanAdapter",
    "DocumentScanAdapter",
    "ScanAdapterDescriptor",
    "ScanCapabilities",
    "get_check_adapter",
    "get_document_adapter",
    "list_check_descriptors",
    "list_document_descriptors",
]
