"""Print & Mail subsystem.

Two adapter families:

* **Bureau adapters** (Lob, PostGrid, Click2Mail) — server-side; turn
  a rendered PDF + address into stuffed-and-mailed certified mail.
* **Local adapters** (IPP, ESC/POS, ZPL, Electron silent print, PDF
  download fallback) — bound to a ``Printer`` row, used for in-office
  printing of receipts, labels, and one-off letters.
"""

from dcs_api.printing.adapter import (
    BureauAdapter,
    LocalPrintAdapter,
    PrintAdapterDescriptor,
    PrintCapabilities,
    get_bureau_adapter,
    get_local_adapter,
    list_bureau_descriptors,
    list_local_descriptors,
)

__all__ = [
    "BureauAdapter",
    "LocalPrintAdapter",
    "PrintAdapterDescriptor",
    "PrintCapabilities",
    "get_bureau_adapter",
    "get_local_adapter",
    "list_bureau_descriptors",
    "list_local_descriptors",
]
