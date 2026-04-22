"""Import engine — maps, validates, and loads external data into DCS.

Supports:
- CSV, XLSX (via list-of-dicts), JSON, and fixed-width formats
- Field mapping from source columns to DCS entity fields
- Per-field transformations (cents conversion, last-four, date parsing, etc.)
- Validation rules (required, positive, date_format, regex, one_of, etc.)
- Dedup strategies (skip, update, error, create_new)
- Per-client and per-jurisdiction templates
"""

import re
import csv
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.models.account import Account
from dcs_api.models.consumer import Consumer


ENTITY_IMPORT_MAP: dict[str, type] = {
    "accounts": Account,
    "consumers": Consumer,
}

# Nested field targets: "consumer.ssn_last_four" → create/link a consumer record
NESTED_ENTITIES: dict[str, type] = {
    "consumer": Consumer,
}


# ---------------------------------------------------------------------------
# Transformations
# ---------------------------------------------------------------------------

TRANSFORMS: dict[str, Any] = {
    "trim": lambda v: v.strip() if isinstance(v, str) else v,
    "uppercase": lambda v: v.upper() if isinstance(v, str) else v,
    "lowercase": lambda v: v.lower() if isinstance(v, str) else v,
    "cents": lambda v: int(round(float(v) * 100)) if v else 0,
    "dollars": lambda v: float(v) / 100 if v else 0.0,
    "last_four": lambda v: str(v)[-4:] if v else None,
    "integer": lambda v: int(v) if v else None,
    "decimal": lambda v: float(v) if v else None,
    "boolean": lambda v: str(v).lower() in ("1", "true", "yes", "y"),
    "date": lambda v: _parse_date(v),
}


def _parse_date(v: Any, fmt: str | None = None) -> datetime | None:
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    for f in [fmt, "%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y%m%d", "%d/%m/%Y"]:
        if f:
            try:
                return datetime.strptime(str(v), f)
            except ValueError:
                continue
    return None


def apply_transform(value: Any, transform_name: str | None) -> Any:
    if not transform_name:
        return value
    fn = TRANSFORMS.get(transform_name)
    return fn(value) if fn else value


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

VALIDATORS: dict[str, Any] = {
    "required": lambda v, p: v is not None and str(v).strip() != "",
    "positive": lambda v, p: v is not None and float(v) > 0,
    "non_negative": lambda v, p: v is not None and float(v) >= 0,
    "max_length": lambda v, p: v is None or len(str(v)) <= p.get("max", 999),
    "min_length": lambda v, p: v is None or len(str(v)) >= p.get("min", 0),
    "one_of": lambda v, p: v in p.get("values", []),
    "regex": lambda v, p: v is None or bool(re.match(p.get("pattern", ""), str(v))),
    "date_format": lambda v, p: _parse_date(v, p.get("format")) is not None,
}


def validate_field(value: Any, rule: dict) -> str | None:
    """Return an error message or None if valid."""
    rule_name = rule.get("rule", "required")
    params = rule.get("params", {})
    fn = VALIDATORS.get(rule_name)
    if fn and not fn(value, params):
        return f"Validation failed: {rule_name} on value '{value}'"
    return None


# ---------------------------------------------------------------------------
# CSV / fixed-width parsing
# ---------------------------------------------------------------------------

def parse_csv(
    content: str,
    delimiter: str = ",",
    skip_header_rows: int = 1,
    encoding: str = "utf-8",
) -> list[dict[str, str]]:
    """Parse CSV content into list of dicts keyed by column index or header."""
    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return []

    if skip_header_rows > 0 and len(rows) > skip_header_rows:
        headers = rows[skip_header_rows - 1]
        data_rows = rows[skip_header_rows:]
    else:
        headers = [f"col_{i}" for i in range(len(rows[0]))]
        data_rows = rows

    result = []
    for row in data_rows:
        record = {}
        for i, h in enumerate(headers):
            record[h.strip()] = row[i].strip() if i < len(row) else ""
        result.append(record)
    return result


def parse_fixed_width(
    content: str,
    spec: list[dict],
    skip_header_rows: int = 0,
) -> list[dict[str, str]]:
    """Parse fixed-width content. spec: [{"name": "acct", "start": 0, "width": 10}, ...]"""
    lines = content.splitlines()
    data_lines = lines[skip_header_rows:]
    result = []
    for line in data_lines:
        if not line.strip():
            continue
        record = {}
        for field_spec in spec:
            start = field_spec["start"]
            width = field_spec["width"]
            name = field_spec["name"]
            record[name] = line[start:start + width].strip()
        result.append(record)
    return result


# ---------------------------------------------------------------------------
# Import processor
# ---------------------------------------------------------------------------

async def process_import(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    source_rows: list[dict[str, str]],
    field_mappings: list[dict],
    validation_rules: list[dict],
    default_values: dict[str, Any],
    entity: str,
    dedup_strategy: str = "skip",
    dedup_fields: list[str] | None = None,
    user_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Process parsed rows through mapping → transform → validate → persist.

    Returns a summary dict with counts and any row-level errors.
    """
    model = ENTITY_IMPORT_MAP.get(entity)
    if not model:
        raise ValueError(f"Unsupported import entity: {entity}")

    dedup_fields = dedup_fields or ["account_reference"]
    results = {
        "total_rows": len(source_rows),
        "processed_rows": 0,
        "created_rows": 0,
        "updated_rows": 0,
        "skipped_rows": 0,
        "error_rows": 0,
        "errors": [],
    }

    for row_idx, source_row in enumerate(source_rows):
        row_errors: list[str] = []
        mapped: dict[str, Any] = dict(default_values)

        # Map fields
        for fm in field_mappings:
            source_key = fm.get("source", "")
            target_key = fm.get("target", "")
            raw_value = source_row.get(source_key, "")
            transformed = apply_transform(raw_value, fm.get("transform"))
            if transformed is None and fm.get("default_value") is not None:
                transformed = fm["default_value"]
            if "." not in target_key:
                mapped[target_key] = transformed
            else:
                parts = target_key.split(".", 1)
                mapped.setdefault(f"_nested_{parts[0]}", {})[parts[1]] = transformed

        # Validate
        for rule in validation_rules:
            field = rule.get("field", "")
            val = mapped.get(field)
            err = validate_field(val, rule)
            if err:
                row_errors.append(f"Row {row_idx + 1}, field '{field}': {err}")

        if row_errors:
            results["error_rows"] += 1
            results["errors"].extend(row_errors)
            results["processed_rows"] += 1
            continue

        # Dedup check
        dedup_filters = [model.tenant_id == tenant_id]
        for df in dedup_fields:
            if df in mapped and hasattr(model, df):
                dedup_filters.append(getattr(model, df) == mapped[df])

        existing = None
        if len(dedup_filters) > 1:
            q = select(model).where(*dedup_filters)
            r = await session.execute(q)
            existing = r.scalar_one_or_none()

        if existing:
            if dedup_strategy == "skip":
                results["skipped_rows"] += 1
                results["processed_rows"] += 1
                continue
            elif dedup_strategy == "error":
                results["error_rows"] += 1
                results["errors"].append(
                    f"Row {row_idx + 1}: duplicate found for {dedup_fields}"
                )
                results["processed_rows"] += 1
                continue
            elif dedup_strategy == "update":
                clean = {k: v for k, v in mapped.items()
                         if not k.startswith("_nested_") and hasattr(model, k)}
                for k, v in clean.items():
                    setattr(existing, k, v)
                results["updated_rows"] += 1
                results["processed_rows"] += 1
                continue

        # Create
        clean = {k: v for k, v in mapped.items()
                 if not k.startswith("_nested_") and hasattr(model, k)}
        clean["tenant_id"] = tenant_id
        obj = model(**clean)
        session.add(obj)
        results["created_rows"] += 1
        results["processed_rows"] += 1

    await session.flush()
    return results
