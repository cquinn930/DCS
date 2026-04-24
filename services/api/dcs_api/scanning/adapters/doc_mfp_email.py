"""MFP scan-to-email — IMAP polling of a dedicated inbox."""

from __future__ import annotations

from dcs_api.scanning.adapter import ScanAdapterDescriptor, ScanCapabilities, register_document
from dcs_api.scanning.adapters._base import StubDoc


@register_document
class MfpEmailAdapter(StubDoc):
    id = "mfp_email"
    label = "MFP scan-to-email"
    capabilities = ScanCapabilities(
        duplex=True,
        color=True,
        multi_page=True,
        auto_feeder=True,
        notes="Polls an IMAP inbox; PDF/TIFF attachments become scan jobs.",
    )
    descriptor = ScanAdapterDescriptor(
        id="mfp_email",
        label="MFP scan-to-email (IMAP)",
        family="mfp",
        kind="document",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "imap_host", "label": "IMAP Host", "type": "text", "required": True},
                {"key": "imap_port", "label": "Port", "type": "number", "default": 993},
                {"key": "username", "label": "Inbox Address", "type": "text", "required": True},
                {"key": "password", "label": "Password / App Password", "type": "secret", "required": True},
                {"key": "folder", "label": "Folder", "type": "text", "default": "INBOX"},
                {"key": "allowed_senders", "label": "Allowed Sender Addresses (comma-sep, blank = any)", "type": "text", "required": False},
                {"key": "use_tls", "label": "Use TLS", "type": "checkbox", "default": True},
                {"key": "poll_seconds", "label": "Poll Interval (seconds)", "type": "number", "default": 60},
            ]
        },
    )
