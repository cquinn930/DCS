"""Report engine — builds and executes dynamic queries from report templates.

Supports tabular, summary, and matrix reports with:
- Dynamic column selection (including dot-notation joins)
- Filter conditions (eq, neq, gt, gte, lt, lte, in, not_in, like, between, is_null)
- Grouping with aggregations (sum, count, avg, min, max)
- Multi-format output: CSV, XLSX, JSON, PDF-ready dicts
- Parameterised runtime values
"""

import csv
import io
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, String, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from dcs_api.models.account import Account, Dispute, Payment
from dcs_api.models.consumer import Consumer
from dcs_api.models.litigation import Judgment, LitigationCase
from dcs_api.models.tenant import AuditLog, User

ENTITY_MODEL_MAP: dict[str, type] = {
    "accounts": Account,
    "consumers": Consumer,
    "payments": Payment,
    "disputes": Dispute,
    "judgments": Judgment,
    "litigation": LitigationCase,
    "audit_logs": AuditLog,
    "users": User,
}

# Relationships that can be joined via dot-notation (entity.relation)
JOIN_MAP: dict[str, dict[str, tuple]] = {
    "accounts": {
        "consumer": (Consumer, Account.consumer_id == Consumer.id),
    },
    "payments": {
        "account": (Account, Payment.account_id == Account.id),
    },
    "disputes": {
        "account": (Account, Dispute.account_id == Account.id),
    },
}

FILTER_OPS = {
    "eq": lambda col, val: col == val,
    "neq": lambda col, val: col != val,
    "gt": lambda col, val: col > val,
    "gte": lambda col, val: col >= val,
    "lt": lambda col, val: col < val,
    "lte": lambda col, val: col <= val,
    "in": lambda col, val: col.in_(val),
    "not_in": lambda col, val: col.notin_(val),
    "like": lambda col, val: col.ilike(f"%{val}%"),
    "is_null": lambda col, val: col.is_(None),
    "not_null": lambda col, val: col.isnot(None),
    "between": lambda col, val: col.between(val[0], val[1]),
}

AGG_FUNCS = {
    "sum": func.sum,
    "count": func.count,
    "avg": func.avg,
    "min": func.min,
    "max": func.max,
}


def _resolve_column(model: type, field: str, entity: str, joined: dict):
    """Resolve a field name (possibly dot-separated) to a SQLAlchemy column."""
    if "." in field:
        relation, attr = field.split(".", 1)
        join_info = JOIN_MAP.get(entity, {}).get(relation)
        if join_info:
            rel_model, condition = join_info
            joined[relation] = join_info
            return getattr(rel_model, attr, None)
    return getattr(model, field, None)


def _substitute_params(value: Any, parameters: dict[str, Any]) -> Any:
    """Replace $param_name references with runtime values."""
    if isinstance(value, str) and value.startswith("$"):
        return parameters.get(value[1:], value)
    return value


def build_query(
    entity: str,
    tenant_id: uuid.UUID,
    columns: list[dict],
    filters: list[dict],
    grouping: list[str],
    aggregations: list[dict],
    sort_order: list[dict],
    parameters: dict[str, Any],
    limit: int | None = None,
) -> tuple[Select, dict]:
    """Build a SQLAlchemy query from a report template definition."""
    model = ENTITY_MODEL_MAP.get(entity)
    if not model:
        raise ValueError(f"Unknown entity: {entity}")

    joined: dict = {}

    # Column selection
    if grouping:
        select_cols = []
        for g in grouping:
            col = _resolve_column(model, g, entity, joined)
            if col is not None:
                select_cols.append(col.label(g))
        for agg in aggregations:
            agg_func = AGG_FUNCS.get(agg.get("function", "count"))
            col = _resolve_column(model, agg["field"], entity, joined)
            if agg_func and col is not None:
                label = agg.get("label", f"{agg['function']}_{agg['field']}")
                select_cols.append(agg_func(col).label(label))
        query = select(*select_cols)
    elif columns:
        select_cols = []
        for c in columns:
            col = _resolve_column(model, c["field"], entity, joined)
            if col is not None:
                label = c.get("label") or c.get("header") or c["field"]
                select_cols.append(col.label(label))
        query = select(*select_cols) if select_cols else select(model)
    else:
        query = select(model)

    # Tenant isolation
    if hasattr(model, "tenant_id"):
        query = query.where(model.tenant_id == tenant_id)

    # Joins
    for rel_name, (rel_model, condition) in joined.items():
        query = query.join(rel_model, condition, isouter=True)

    # Filters
    for f in filters:
        col = _resolve_column(model, f["field"], entity, joined)
        op_fn = FILTER_OPS.get(f.get("op", "eq"))
        if col is not None and op_fn:
            val = _substitute_params(f.get("value"), parameters)
            query = query.where(op_fn(col, val))

    # Group by
    if grouping:
        for g in grouping:
            col = _resolve_column(model, g, entity, joined)
            if col is not None:
                query = query.group_by(col)

    # Sort
    for s in sort_order:
        col = _resolve_column(model, s["field"], entity, joined)
        if col is not None:
            query = query.order_by(col.desc() if s.get("direction") == "desc" else col.asc())

    if limit:
        query = query.limit(limit)

    return query, joined


async def execute_report(
    session: AsyncSession,
    entity: str,
    tenant_id: uuid.UUID,
    columns: list[dict],
    filters: list[dict],
    grouping: list[str],
    aggregations: list[dict],
    sort_order: list[dict],
    parameters: dict[str, Any],
    output_format: str = "json",
    limit: int | None = None,
) -> dict[str, Any]:
    """Run a report and return results in the requested format."""
    query, joined = build_query(
        entity, tenant_id, columns, filters,
        grouping, aggregations, sort_order, parameters, limit,
    )

    result = await session.execute(query)

    if grouping or columns:
        rows_raw = result.all()
        col_names = [c.get("label") or c.get("header") or c["field"] for c in columns] if columns else []
        if grouping:
            col_names = list(grouping)
            for agg in aggregations:
                col_names.append(agg.get("label", f"{agg['function']}_{agg['field']}"))
        rows = [_row_to_dict(row, col_names) for row in rows_raw]
    else:
        orm_rows = result.scalars().all()
        rows = [_model_to_dict(r) for r in orm_rows]
        col_names = list(rows[0].keys()) if rows else []

    output = format_output(rows, col_names, output_format)
    return {
        "rows": rows,
        "row_count": len(rows),
        "columns": col_names,
        "output_format": output_format,
        "output": output,
    }


def _row_to_dict(row: Any, col_names: list[str]) -> dict:
    """Convert a keyed result row to a dict."""
    if hasattr(row, "_asdict"):
        return {k: _serialise(v) for k, v in row._asdict().items()}
    return {col_names[i]: _serialise(row[i]) for i in range(len(col_names))}


def _model_to_dict(obj: Any) -> dict:
    if hasattr(obj, "to_dict"):
        return {k: _serialise(v) for k, v in obj.to_dict().items()}
    return {c.name: _serialise(getattr(obj, c.name)) for c in obj.__table__.columns}


def _serialise(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, uuid.UUID):
        return str(v)
    return v


def format_output(rows: list[dict], col_names: list[str], fmt: str) -> str | list:
    """Convert rows into the desired format string."""
    if fmt == "json":
        return rows

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=col_names, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()

    if fmt == "xlsx":
        # Return a list-of-lists representation; actual XLSX generation
        # would use openpyxl in production.
        header = col_names
        data = [[row.get(c) for c in col_names] for row in rows]
        return [header] + data

    return rows
