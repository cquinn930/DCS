"""Notice templates and renderer.

Templates are plain-text (intentionally — Reg F § 1006.34 emphasizes
clear, conspicuous disclosure and many state validation forms must be
delivered in writing). Each template lives under
`templates/<jurisdiction>/<name>.txt` and uses a small `${field}` merge
syntax (no Jinja runtime dependency).

Public entry points:
  - registry.list_templates(jurisdiction)
  - registry.load_template(jurisdiction, template_id)
  - renderer.render(template, context) -> rendered text + content_hash
"""

from dcs_api.notices.registry import (
    NoticeTemplate,
    list_templates,
    load_template,
)
from dcs_api.notices.renderer import RenderedNotice, render

__all__ = [
    "NoticeTemplate",
    "RenderedNotice",
    "list_templates",
    "load_template",
    "render",
]
