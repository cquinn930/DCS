"""MFP scan-to-SFTP — server polls a folder the MFP writes to."""

from __future__ import annotations

from dcs_api.scanning.adapter import ScanAdapterDescriptor, ScanCapabilities, register_document
from dcs_api.scanning.adapters._base import StubDoc


@register_document
class MfpSftpAdapter(StubDoc):
    id = "mfp_sftp"
    label = "MFP scan-to-SFTP"
    capabilities = ScanCapabilities(
        duplex=True,
        color=True,
        multi_page=True,
        auto_feeder=True,
        barcode_detect=True,
        blank_page_drop=True,
        notes="Server periodically lists the SFTP path and ingests new files.",
    )
    descriptor = ScanAdapterDescriptor(
        id="mfp_sftp",
        label="MFP scan-to-SFTP",
        family="mfp",
        kind="document",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "host", "label": "SFTP Host", "type": "text", "required": True},
                {"key": "port", "label": "Port", "type": "number", "default": 22},
                {"key": "username", "label": "Username", "type": "text", "required": True},
                {"key": "password", "label": "Password", "type": "secret", "required": False},
                {"key": "private_key", "label": "Private Key (PEM)", "type": "secret_textarea", "required": False},
                {"key": "remote_path", "label": "Remote Path", "type": "text", "required": True, "default": "/scans"},
                {"key": "poll_seconds", "label": "Poll Interval (seconds)", "type": "number", "default": 30},
                {"key": "delete_after_intake", "label": "Delete files after intake", "type": "checkbox", "default": True},
            ]
        },
    )
