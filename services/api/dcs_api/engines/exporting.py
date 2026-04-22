"""Export engine — generates outbound files from DCS data.

Supports:
- CSV, XLSX (list-of-lists), JSON, fixed-width formats
- Column selection, renaming, ordering, and width specification
- Filters and sort (reuses report engine query builder)
- Per-field transformations for outbound formatting
- Per-client and per-jurisdiction templates
"""

import csv
import io
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.engines.reporting import (
    ENTITY_MODEL_MAP,
    FILTER_OPS,
    _resolve_column,
    _serialise,
    build_query,
)


# ---------------------------------------------------------------------------
# Outbound transformations
# ---------------------------------------------------------------------------

EXPORT_TRANSFORMS: dict[str, Any] = {
    "dollars": lambda v: f"{v / 100:.2f}" if isinstance(v, (int, float)) and v else "0.00",
    "cents": lambda v: str(int(v * 100)) if isinstance(v, (int, float)) else "0",
    "date_mdy": lambda v: _fmt_date(v, "%m/%d/%Y"),
    "date_ymd": lambda v: _fmt_date(v, "%Y-%m-%d"),
    "date_iso": lambda v: _fmt_date(v, "%Y-%m-%dT%H:%M:%S"),
    "uppercase": lambda v: str(v).upper() if v else "",
    "lowercase": lambda v: str(v).lower() if v else "",
    "pad_left": lambda v, w=10: str(v or "").rjust(w),
    "pad_right": lambda v, w=10: str(v or "").ljust(w),
    "truncate": lambda v, w=50: str(v or "")[:w],
    "boolean_yn": lambda v: "Y" if v else "N",
    "boolean_10": lambda v: "1" if v else "0",
    "blank_if_null": lambda v: "" if v is None else str(v),
}


def _fmt_date(v: Any, fmt: str) -> str:
    if isinstance(v, datetime):
        return v.strftime(fmt)
    if isinstance(v, date):
        return v.strftime(fmt)
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v).strftime(fmt)
        except ValueError:
            return v
    return ""


def apply_export_transform(value: Any, transform_name: str | None, width: int | None = None) -> Any:
    if not transform_name:
        return _serialise(value)
    fn = EXPORT_TRANSFORMS.get(transform_name)
    if not fn:
        return _serialise(value)
    # Some transforms accept a width parameter
    import inspect
    params = inspect.signature(fn).parameters
    if len(params) > 1 and width is not None:
        return fn(value, width)
    return fn(value)


# ---------------------------------------------------------------------------
# Export processor
# ---------------------------------------------------------------------------

async def execute_export(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity: str,
    columns: list[dict],
    filters: list[dict],
    sort_order: list[dict],
    transformations: list[dict],
    target_format: str = "csv",
    delimiter: str = ",",
    include_header: bool = True,
    fixed_width_spec: list[dict] | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run an export and return results.

    Returns::

        {
            "row_count": 150,
            "output": "<csv string or list>",
            "target_format": "csv",
        }
    """
    parameters = parameters or {}

    # Build the data query reusing the report engine
    query, joined = build_query(
        entity=entity,
        tenant_id=tenant_id,
        columns=columns,
        filters=filters,
        grouping=[],
        aggregations=[],
        sort_order=sort_order,
        parameters=parameters,
    )

    result = await session.execute(query)

    # Build transform lookup
    transform_map: dict[str, dict] = {}
    for t in transformations:
        transform_map[t.get("field", "")] = t

    if columns:
        raw_rows = result.all()
        col_defs = columns
        col_names = [c.get("header") or c.get("label") or c["field"] for c in col_defs]

        rows: list[dict[str, Any]] = []
        for raw in raw_rows:
            row_dict: dict[str, Any] = {}
            for i, c in enumerate(col_defs):
                field = c["field"]
                header = c.get("header") or c.get("label") or field
                val = raw[i] if i < len(raw) else None
                # Apply transforms
                t = transform_map.get(field, {})
                val = apply_export_transform(val, t.get("transform"), c.get("width"))
                row_dict[header] = val
            rows.append(row_dict)
    else:
        orm_rows = result.scalars().all()
        rows = []
        for obj in orm_rows:
            d = {c.name: _serialise(getattr(obj, c.name))
                 for c in obj.__table__.columns}
            rows.append(d)
        col_names = list(rows[0].keys()) if rows else []
        col_defs = [{"field": c, "header": c} for c in col_names]

    # Format output
    output = _format_export(rows, col_names, col_defs, target_format,
                            delimiter, include_header, fixed_width_spec)

    return {
        "row_count": len(rows),
        "output": output,
        "target_format": target_format,
        "columns": col_names,
    }


def _format_export(
    rows: list[dict],
    col_names: list[str],
    col_defs: list[dict],
    fmt: str,
    delimiter: str,
    include_header: bool,
    fixed_width_spec: list[dict] | None,
) -> str | list:
    if fmt == "json":
        return rows

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=col_names, delimiter=delimiter,
                                extrasaction="ignore")
        if include_header:
            writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()

    if fmt == "fixed_width" and fixed_width_spec:
        lines: list[str] = []
        if include_header:
            header_line = ""
            for spec in fixed_width_spec:
                header_line += str(spec.get("header", spec["name"])).ljust(spec["width"])
            lines.append(header_line)
        for row in rows:
            line = ""
            for spec in fixed_width_spec:
                name = spec.get("header", spec["name"])
                val = str(row.get(name, ""))
                width = spec["width"]
                align = spec.get("align", "left")
                if align == "right":
                    line += val.rjust(width)[:width]
                else:
                    line += val.ljust(width)[:width]
            lines.append(line)
        return "\n".join(lines)

    if fmt == "xlsx":
        header = col_names if include_header else []
        data = [[row.get(c) for c in col_names] for row in rows]
        return ([header] if header else []) + data

    return rows
