"""Notice template renderer.

Uses ``string.Template``-style ``${field}`` substitution so every template
is plain text (no eval, no Jinja, no JS — keeps templates auditable and the
renderer free of arbitrary-code-execution surface area).

Every render produces a SHA-256 content hash that is stored on the Notice
row (`notice.content_hash`) so the exact text mailed/emailed can be
reconstructed and proven during a regulatory audit.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from string import Template
from typing import Any

from dcs_api.notices.registry import NoticeTemplate


@dataclass
class RenderedNotice:
    template_id: str
    template_version: str
    jurisdiction: str
    authority: str
    body: str
    content_hash: str        # sha256 hex of body
    missing_fields: list[str]  # required fields that were left at "(unknown)"


def _format_currency(cents: int | None) -> str:
    if cents is None:
        return "$0.00"
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    dollars, remainder = divmod(cents, 100)
    return f"{sign}${dollars:,}.{remainder:02d}"


def _format_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%B %-d, %Y") if hasattr(value, "strftime") else value.isoformat()
    return str(value)


def _coerce(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, Decimal, float)):
        return str(value)
    if isinstance(value, (date, datetime)):
        return _format_date(value)
    return str(value)


def _expand_currency_keys(context: dict[str, Any]) -> dict[str, Any]:
    """For every `*_cents` key add a `*_formatted` mirror ($1,234.56)."""
    expanded = dict(context)
    for k, v in list(context.items()):
        if k.endswith("_cents") and isinstance(v, (int, float, Decimal)):
            expanded[k.replace("_cents", "_formatted")] = _format_currency(int(v))
    # Date helpers
    for k in ("today_date", "judgment_date", "validation_period_start",
              "dispute_deadline_date", "dispute_received_date"):
        if k in expanded:
            expanded[k] = _format_date(expanded[k])
    return expanded


def render(template: NoticeTemplate, context: dict[str, Any]) -> RenderedNotice:
    """Render a template against `context`, capturing missing required fields."""
    expanded = _expand_currency_keys(context)
    coerced = {k: _coerce(v) for k, v in expanded.items()}

    missing = [f for f in template.required_fields if f not in coerced or coerced[f] == ""]
    # Always provide a placeholder so Template.safe_substitute does not leave
    # raw `${...}` markers in the output.
    safe = dict(coerced)
    for f in missing:
        # For currency fields render as $0.00 placeholder; for others leave blank.
        if f.endswith("_cents"):
            safe[f] = "$0.00"
            safe[f.replace("_cents", "_formatted")] = "$0.00"
        else:
            safe[f] = "(not provided)"

    body = Template(template.body).safe_substitute(safe)
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()

    return RenderedNotice(
        template_id=template.template_id,
        template_version=template.version,
        jurisdiction=template.jurisdiction,
        authority=template.authority,
        body=body,
        content_hash=content_hash,
        missing_fields=missing,
    )
