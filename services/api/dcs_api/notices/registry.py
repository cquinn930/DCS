"""Notice template registry.

Each registered template carries the citation that drives its required
fields. The registry is keyed by (jurisdiction, template_id) so multiple
state packs can share template_ids (e.g. "validation_notice").
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@dataclass(frozen=True)
class NoticeTemplate:
    jurisdiction: str
    template_id: str
    version: str
    name: str
    authority: str
    required_fields: tuple[str, ...]
    body: str
    relative_path: str


# Required merge fields per template, derived from the controlling rule.
# Reg F validation-information items per § 1006.34(c).
_VALIDATION_REQUIRED_FIELDS = (
    "tenant_legal_name",
    "consumer_full_name",
    "consumer_address",
    "today_date",
    "validation_period_start",       # § 1006.34(c)(2)(iv) — itemization date
    "current_creditor_name",          # (c)(2)(i)
    "original_creditor_name",         # (c)(2)(ii)
    "account_reference",
    "account_number_last_four",       # (c)(2)(iii)
    "itemization_principal_cents",    # (c)(2)(v)
    "itemization_interest_cents",
    "itemization_fees_cents",
    "itemization_payments_cents",
    "itemization_credits_cents",
    "current_balance_cents",          # (c)(3)
    "dispute_deadline_date",          # (c)(3)(iii) — 30 days from receipt
    "tenant_phone",
    "tenant_address",
    "tenant_email",
    "state_disclosure",                # state-specific overlay text (NJ/NY)
)

_INITIAL_REQUIRED_FIELDS = (
    "tenant_legal_name",
    "consumer_full_name",
    "current_creditor_name",
    "current_balance_cents",
    "tenant_phone",
    "tenant_address",
    "miniranda_disclosure",            # § 1006.18(e) "this is a debt collector" disclosure
)

_DISPUTE_REQUIRED_FIELDS = (
    "tenant_legal_name",
    "consumer_full_name",
    "consumer_address",
    "today_date",
    "dispute_received_date",
    "dispute_summary",
    "verification_window_days",        # 30 typical
    "next_steps",
)

_POST_JUDGMENT_REQUIRED_FIELDS = (
    "tenant_legal_name",
    "consumer_full_name",
    "court_name",
    "docket_number",
    "judgment_date",
    "judgment_amount_cents",
    "current_principal_cents",
    "post_judgment_interest_cents",
    "current_balance_cents",
    "rate_year",
    "annual_rate",
    "is_above_threshold",
    "rate_source_citation",
)


def _load_body(relative_path: str) -> str:
    path = _TEMPLATES_DIR / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Template missing: {relative_path}")
    return path.read_text(encoding="utf-8")


def _build_registry() -> dict[tuple[str, str], NoticeTemplate]:
    specs = [
        # ----- New Jersey -----
        dict(
            jurisdiction="NJ",
            template_id="nj.initial_communication",
            version="2026.1",
            name="Initial communication notice (NJ)",
            authority=(
                "15 U.S.C. § 1692e(11); 12 C.F.R. § 1006.18(e); "
                "FDCPA / Reg F miniranda overlay"
            ),
            required_fields=_INITIAL_REQUIRED_FIELDS,
            relative_path="nj/initial_communication.txt",
        ),
        dict(
            jurisdiction="NJ",
            template_id="nj.validation_notice",
            version="2026.1",
            name="Debt validation notice (NJ)",
            authority=(
                "15 U.S.C. § 1692g(a); 12 C.F.R. § 1006.34 + Appendix B "
                "Model Form B-3"
            ),
            required_fields=_VALIDATION_REQUIRED_FIELDS,
            relative_path="nj/validation_notice.txt",
        ),
        dict(
            jurisdiction="NJ",
            template_id="nj.dispute_acknowledgement",
            version="2026.1",
            name="Dispute acknowledgement (NJ)",
            authority="15 U.S.C. § 1692g(b); 12 C.F.R. § 1006.38(d)",
            required_fields=_DISPUTE_REQUIRED_FIELDS,
            relative_path="nj/dispute_acknowledgement.txt",
        ),
        dict(
            jurisdiction="NJ",
            template_id="nj.post_judgment_disclosure",
            version="2026.1",
            name="Post-judgment interest disclosure (NJ)",
            authority="N.J. Court Rules, R. 4:42-11(a) (AOC annual notice)",
            required_fields=_POST_JUDGMENT_REQUIRED_FIELDS,
            relative_path="nj/post_judgment_disclosure.txt",
        ),
        # ----- New York -----
        dict(
            jurisdiction="NY",
            template_id="ny.initial_communication",
            version="2026.1",
            name="Initial communication notice (NY)",
            authority=(
                "15 U.S.C. § 1692e(11); 12 C.F.R. § 1006.18(e); "
                "N.Y. C.P.L.R. § 214-i overlay"
            ),
            required_fields=_INITIAL_REQUIRED_FIELDS,
            relative_path="ny/initial_communication.txt",
        ),
        dict(
            jurisdiction="NY",
            template_id="ny.validation_notice",
            version="2026.1",
            name="Debt validation notice (NY)",
            authority=(
                "15 U.S.C. § 1692g(a); 12 C.F.R. § 1006.34 + Appendix B "
                "Model Form B-3; N.Y. C.P.L.R. § 214-i SOL disclosure"
            ),
            required_fields=_VALIDATION_REQUIRED_FIELDS,
            relative_path="ny/validation_notice.txt",
        ),
        dict(
            jurisdiction="NY",
            template_id="ny.dispute_acknowledgement",
            version="2026.1",
            name="Dispute acknowledgement (NY)",
            authority="15 U.S.C. § 1692g(b); 12 C.F.R. § 1006.38(d)",
            required_fields=_DISPUTE_REQUIRED_FIELDS,
            relative_path="ny/dispute_acknowledgement.txt",
        ),
        dict(
            jurisdiction="NY",
            template_id="ny.post_judgment_disclosure",
            version="2026.1",
            name="Post-judgment interest disclosure (NY)",
            authority="N.Y. C.P.L.R. § 5004(a)-(b)",
            required_fields=_POST_JUDGMENT_REQUIRED_FIELDS,
            relative_path="ny/post_judgment_disclosure.txt",
        ),
    ]
    out: dict[tuple[str, str], NoticeTemplate] = {}
    for spec in specs:
        out[(spec["jurisdiction"], spec["template_id"])] = NoticeTemplate(
            jurisdiction=spec["jurisdiction"],
            template_id=spec["template_id"],
            version=spec["version"],
            name=spec["name"],
            authority=spec["authority"],
            required_fields=spec["required_fields"],
            relative_path=spec["relative_path"],
            body=_load_body(spec["relative_path"]),
        )
    return out


_REGISTRY = _build_registry()


def list_templates(jurisdiction: str | None = None) -> list[NoticeTemplate]:
    if jurisdiction is None:
        return list(_REGISTRY.values())
    juris = jurisdiction.upper()[:2]
    return [t for (j, _), t in _REGISTRY.items() if j == juris]


def load_template(jurisdiction: str, template_id: str) -> NoticeTemplate:
    juris = jurisdiction.upper()[:2]
    key = (juris, template_id)
    if key not in _REGISTRY:
        raise KeyError(f"No template {template_id!r} for jurisdiction {juris}")
    return _REGISTRY[key]


def template_ids(jurisdiction: str) -> Iterable[str]:
    juris = jurisdiction.upper()[:2]
    return [tid for (j, tid) in _REGISTRY if j == juris]
