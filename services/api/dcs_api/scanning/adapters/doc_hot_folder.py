"""Hot-folder watcher — usually run inside Electron on the agent's PC."""

from __future__ import annotations

from dcs_api.scanning.adapter import ScanAdapterDescriptor, ScanCapabilities, register_document
from dcs_api.scanning.adapters._base import StubDoc


@register_document
class HotFolderAdapter(StubDoc):
    id = "hot_folder"
    label = "Hot Folder (Electron)"
    capabilities = ScanCapabilities(
        multi_page=True,
        auto_feeder=False,
        requires_electron=True,
        notes="Electron client watches a folder and uploads new files.",
    )
    descriptor = ScanAdapterDescriptor(
        id="hot_folder",
        label="Hot folder watcher (Electron)",
        family="desktop",
        kind="document",
        capabilities=capabilities,
        config_schema={
            "fields": [
                {"key": "folder_path", "label": "Folder Path (on agent PC)", "type": "text", "required": True},
                {"key": "match_glob", "label": "Filename glob", "type": "text", "default": "*.{pdf,tif,tiff}"},
                {"key": "delete_after_intake", "label": "Delete after upload", "type": "checkbox", "default": True},
            ]
        },
    )
