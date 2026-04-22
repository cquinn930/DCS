"""DCS Script engine — safe, sandboxed DSL for custom automation.

Provides a restricted scripting language that lets tenants write custom:
- Compliance checks (per jurisdiction)
- Account flagging / workflow rules
- Report transformations
- Import/export hooks
- Scheduled automations

The DSL is intentionally limited: no file I/O, no network, no exec/eval,
no imports.  Scripts operate on entity data through a controlled context.

Syntax overview::

    # Comments start with #
    PARAM name TYPE default_value

    SET variable = expression
    QUERY entity WHERE field op value [AND ...]
    FOR EACH item IN results: ... END
    IF condition: ... ELIF condition: ... ELSE: ... END
    FLAG entity AS "label" WITH key = value
    LOG "message"
    RETURN expression

Built-in functions:
    days_since(date)      - days between date and today
    days_until(date)      - days between today and date
    sol_years(jurisdiction) - statute of limitations years
    abs(number)           - absolute value
    round(number, places) - rounding
    upper(string)         - uppercase
    lower(string)         - lowercase
    len(collection)       - length
    now()                 - current UTC datetime
    today()               - current UTC date
    format_currency(cents) - format as dollar string
"""

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

# Maximum iterations to prevent infinite loops
MAX_ITERATIONS = 10000
MAX_RESULTS = 50000


class ScriptError(Exception):
    """Raised when a script has a syntax or runtime error."""

    def __init__(self, message: str, line: int | None = None):
        self.line = line
        super().__init__(f"Line {line}: {message}" if line else message)


class ScriptContext:
    """Runtime context for script execution.

    Holds variables, parameters, results, flags, and logs.
    A fresh context is created for each execution.
    """

    def __init__(
        self,
        tenant_id: uuid.UUID,
        parameters: dict[str, Any] | None = None,
        data: dict[str, list[dict]] | None = None,
        jurisdiction: str | None = None,
        dry_run: bool = False,
    ):
        self.tenant_id = tenant_id
        self.variables: dict[str, Any] = dict(parameters or {})
        self.data = data or {}
        self.jurisdiction = jurisdiction
        self.dry_run = dry_run
        self.results: list[dict] = []
        self.flags: list[dict] = []
        self.logs: list[str] = []
        self.rows_affected = 0
        self.iteration_count = 0

    def get(self, name: str) -> Any:
        return self.variables.get(name)

    def set(self, name: str, value: Any) -> None:
        self.variables[name] = value


# ---------------------------------------------------------------------------
# Built-in functions
# ---------------------------------------------------------------------------

SOL_YEARS_MAP: dict[str, int] = {
    "NJ": 6, "NY": 6, "PA": 4, "CA": 4, "TX": 4, "FL": 5,
    "IL": 5, "OH": 6, "GA": 6, "NC": 3, "VA": 5, "MA": 6,
    "MD": 3, "CT": 6, "SC": 3, "DE": 3, "DC": 3,
}

BUILTINS: dict[str, Any] = {
    "days_since": lambda d: (date.today() - _to_date(d)).days if d else 0,
    "days_until": lambda d: (_to_date(d) - date.today()).days if d else 0,
    "sol_years": lambda j: SOL_YEARS_MAP.get(str(j).upper(), 6),
    "abs": lambda v: abs(v),
    "round": lambda v, p=2: round(v, p),
    "upper": lambda v: str(v).upper(),
    "lower": lambda v: str(v).lower(),
    "len": lambda v: len(v) if v else 0,
    "now": lambda: datetime.now(timezone.utc),
    "today": lambda: date.today(),
    "format_currency": lambda cents: f"${cents / 100:,.2f}" if cents else "$0.00",
    "min": lambda a, b: min(a, b),
    "max": lambda a, b: max(a, b),
    "str": lambda v: str(v),
    "int": lambda v: int(v) if v else 0,
    "float": lambda v: float(v) if v else 0.0,
}


def _to_date(v: Any) -> date:
    if isinstance(v, date):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        return datetime.fromisoformat(v).date()
    return date.today()


# ---------------------------------------------------------------------------
# Tokeniser / parser
# ---------------------------------------------------------------------------

# Allowed operators
COMPARISON_OPS = {"==", "!=", ">", ">=", "<", "<=", "IN", "NOT_IN", "LIKE"}
MATH_OPS = {"+", "-", "*", "/", "%"}

# Dangerous patterns (blocked)
BLOCKED_PATTERNS = [
    r"__\w+__",          # dunder access
    r"\bimport\b",       # imports
    r"\bexec\b",         # exec
    r"\beval\b",         # eval
    r"\bopen\b",         # file I/O
    r"\bos\.",           # os module
    r"\bsys\.",          # sys module
    r"\bsubprocess\b",   # subprocess
    r"\bglobals\b",
    r"\blocals\b",
    r"\bcompile\b",
    r"\bgetattr\b",
    r"\bsetattr\b",
    r"\bdelattr\b",
]


def validate_script(code: str) -> list[str]:
    """Static validation — returns list of error messages (empty = valid)."""
    errors: list[str] = []

    for pattern in BLOCKED_PATTERNS:
        matches = re.finditer(pattern, code, re.IGNORECASE)
        for m in matches:
            line_no = code[:m.start()].count("\n") + 1
            errors.append(f"Line {line_no}: Forbidden pattern '{m.group()}'")

    lines = code.strip().splitlines()
    block_stack: list[str] = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        keyword = stripped.split()[0].upper() if stripped.split() else ""

        if keyword in ("FOR", "IF"):
            block_stack.append(keyword)
        elif keyword == "END":
            if not block_stack:
                errors.append(f"Line {i}: Unexpected END without matching block")
            else:
                block_stack.pop()
        elif keyword == "ELIF" or keyword == "ELSE":
            if not block_stack or block_stack[-1] != "IF":
                errors.append(f"Line {i}: {keyword} outside of IF block")

    for remaining in block_stack:
        errors.append(f"Unclosed {remaining} block")

    return errors


# ---------------------------------------------------------------------------
# Interpreter
# ---------------------------------------------------------------------------

class ScriptInterpreter:
    """Interprets and executes DCS Script code."""

    def __init__(self, ctx: ScriptContext):
        self.ctx = ctx

    def execute(self, code: str) -> dict[str, Any]:
        """Parse and execute the script, return results."""
        errors = validate_script(code)
        if errors:
            raise ScriptError("; ".join(errors))

        lines = code.strip().splitlines()
        self._execute_block(lines, 0, len(lines))

        return {
            "status": "completed",
            "results": self.ctx.results[:MAX_RESULTS],
            "flags": self.ctx.flags,
            "logs": self.ctx.logs,
            "rows_affected": self.ctx.rows_affected,
            "variables": {k: _safe_serialise(v) for k, v in self.ctx.variables.items()},
        }

    def _execute_block(self, lines: list[str], start: int, end: int) -> Any:
        i = start
        while i < end:
            self.ctx.iteration_count += 1
            if self.ctx.iteration_count > MAX_ITERATIONS:
                raise ScriptError("Maximum iteration count exceeded", i + 1)

            line = lines[i].strip()
            if not line or line.startswith("#"):
                i += 1
                continue

            parts = line.split(None, 1)
            keyword = parts[0].upper()
            rest = parts[1] if len(parts) > 1 else ""

            if keyword == "PARAM":
                self._handle_param(rest, i + 1)
            elif keyword == "SET":
                self._handle_set(rest, i + 1)
            elif keyword == "QUERY":
                self._handle_query(rest, lines, i)
            elif keyword == "FOR":
                block_end = self._find_block_end(lines, i, end)
                self._handle_for(rest, lines, i + 1, block_end)
                i = block_end + 1
                continue
            elif keyword == "IF":
                block_end = self._find_block_end(lines, i, end)
                self._handle_if(rest, lines, i + 1, block_end)
                i = block_end + 1
                continue
            elif keyword == "FLAG":
                self._handle_flag(rest, i + 1)
            elif keyword == "LOG":
                self._handle_log(rest, i + 1)
            elif keyword == "RETURN":
                return self._eval_expr(rest)

            i += 1
        return None

    def _handle_param(self, rest: str, line: int) -> None:
        """PARAM name TYPE default"""
        parts = rest.split()
        if len(parts) < 2:
            raise ScriptError("PARAM requires name and type", line)
        name = parts[0]
        if name not in self.ctx.variables:
            if len(parts) >= 3:
                self.ctx.variables[name] = self._coerce(parts[2], parts[1])
            else:
                self.ctx.variables[name] = None

    def _handle_set(self, rest: str, line: int) -> None:
        """SET var = expression"""
        if "=" not in rest:
            raise ScriptError("SET requires = assignment", line)
        name, expr = rest.split("=", 1)
        name = name.strip()
        value = self._eval_expr(expr.strip())
        self.ctx.set(name, value)

    def _handle_query(self, rest: str, lines: list[str], line_idx: int) -> None:
        """QUERY entity WHERE conditions — filters ctx.data[entity]."""
        parts = rest.split("WHERE", 1)
        entity = parts[0].strip().lower()
        data = self.ctx.data.get(entity, [])

        if len(parts) > 1:
            conditions = self._parse_conditions(parts[1].strip())
            filtered = [row for row in data if self._match_conditions(row, conditions)]
        else:
            filtered = list(data)

        self.ctx.variables["results"] = filtered
        self.ctx.results = filtered

    def _handle_for(self, rest: str, lines: list[str], body_start: int, block_end: int) -> None:
        """FOR EACH item IN collection: ... END"""
        match = re.match(r"EACH\s+(\w+)\s+IN\s+(.+?):", rest, re.IGNORECASE)
        if not match:
            match = re.match(r"EACH\s+(\w+)\s+IN\s+(.+)", rest, re.IGNORECASE)
        if not match:
            raise ScriptError("Invalid FOR syntax", body_start)

        var_name = match.group(1)
        collection_expr = match.group(2).strip()
        collection = self._eval_expr(collection_expr)

        if not isinstance(collection, (list, tuple)):
            raise ScriptError(f"FOR target must be a list, got {type(collection)}", body_start)

        for item in collection:
            self.ctx.iteration_count += 1
            if self.ctx.iteration_count > MAX_ITERATIONS:
                raise ScriptError("Maximum iteration count exceeded")
            self.ctx.set(var_name, item)
            self._execute_block(lines, body_start, block_end)

    def _handle_if(self, rest: str, lines: list[str], body_start: int, block_end: int) -> None:
        """IF condition: ... ELIF: ... ELSE: ... END"""
        condition_str = rest.rstrip(":")
        if self._eval_condition(condition_str):
            elif_or_else = self._find_elif_else(lines, body_start, block_end)
            self._execute_block(lines, body_start, elif_or_else)
            return

        # Check ELIF / ELSE
        i = body_start
        while i < block_end:
            line = lines[i].strip()
            keyword = line.split()[0].upper() if line.split() else ""
            if keyword == "ELIF":
                cond = line.split(None, 1)[1].rstrip(":") if len(line.split(None, 1)) > 1 else ""
                if self._eval_condition(cond):
                    next_branch = self._find_elif_else(lines, i + 1, block_end)
                    self._execute_block(lines, i + 1, next_branch)
                    return
            elif keyword == "ELSE":
                self._execute_block(lines, i + 1, block_end)
                return
            i += 1

    def _handle_flag(self, rest: str, line: int) -> None:
        """FLAG entity AS 'label' WITH key = value"""
        match = re.match(r'(\w+)\s+AS\s+"([^"]+)"(?:\s+WITH\s+(.+))?', rest)
        if not match:
            raise ScriptError("Invalid FLAG syntax", line)
        target_name = match.group(1)
        label = match.group(2)
        target = self.ctx.get(target_name)
        flag = {"target": target_name, "label": label}
        if match.group(3):
            for kv in match.group(3).split(","):
                k, v = kv.split("=", 1)
                flag[k.strip()] = v.strip().strip('"')
        if isinstance(target, dict):
            flag["target_id"] = target.get("id")
        self.ctx.flags.append(flag)
        self.ctx.rows_affected += 1

    def _handle_log(self, rest: str, line: int) -> None:
        msg = rest.strip().strip('"').strip("'")
        # Substitute variables
        for var, val in self.ctx.variables.items():
            msg = msg.replace(f"${var}", str(val))
        self.ctx.logs.append(msg)

    # --- Expression evaluator (safe, no eval) ---

    def _eval_expr(self, expr: str) -> Any:
        expr = expr.strip()
        if not expr:
            return None

        # String literal
        if (expr.startswith('"') and expr.endswith('"')) or \
           (expr.startswith("'") and expr.endswith("'")):
            return expr[1:-1]

        # List literal
        if expr.startswith("[") and expr.endswith("]"):
            inner = expr[1:-1].strip()
            if not inner:
                return []
            items = [self._eval_expr(x.strip()) for x in self._split_list(inner)]
            return items

        # Boolean
        if expr.upper() == "TRUE":
            return True
        if expr.upper() == "FALSE":
            return False
        if expr.upper() == "NONE" or expr.upper() == "NULL":
            return None

        # Number
        try:
            if "." in expr:
                return float(expr)
            return int(expr)
        except ValueError:
            pass

        # Variable reference ($var or plain name)
        if expr.startswith("$"):
            return self.ctx.get(expr[1:])

        # Function call
        func_match = re.match(r"(\w+)\((.*)?\)$", expr)
        if func_match:
            func_name = func_match.group(1)
            args_str = func_match.group(2) or ""
            args = [self._eval_expr(a.strip()) for a in self._split_list(args_str)] if args_str else []
            if func_name in BUILTINS:
                return BUILTINS[func_name](*args)
            raise ScriptError(f"Unknown function: {func_name}")

        # Dot access (obj.field)
        if "." in expr and not expr[0].isdigit():
            parts = expr.split(".", 1)
            obj = self.ctx.get(parts[0])
            if isinstance(obj, dict):
                return obj.get(parts[1])
            return None

        # Simple arithmetic
        for op in ["+", "-", "*", "/"]:
            if op in expr:
                left, right = expr.rsplit(op, 1)
                left_val = self._eval_expr(left.strip())
                right_val = self._eval_expr(right.strip())
                if isinstance(left_val, (int, float)) and isinstance(right_val, (int, float)):
                    if op == "+":
                        return left_val + right_val
                    if op == "-":
                        return left_val - right_val
                    if op == "*":
                        return left_val * right_val
                    if op == "/" and right_val != 0:
                        return left_val / right_val
                if op == "+" and isinstance(left_val, str):
                    return str(left_val) + str(right_val)

        # Parenthesised expression
        if expr.startswith("(") and expr.endswith(")"):
            return self._eval_expr(expr[1:-1])

        # Variable name
        return self.ctx.get(expr)

    def _eval_condition(self, cond: str) -> bool:
        cond = cond.strip()
        for op_str, op_sym in [(">=", ">="), ("<=", "<="), ("!=", "!="),
                                ("==", "=="), (">", ">"), ("<", "<"),
                                (" IN ", " IN "), (" NOT_IN ", " NOT_IN ")]:
            if op_str in cond:
                left, right = cond.split(op_str, 1)
                l_val = self._eval_expr(left.strip())
                r_val = self._eval_expr(right.strip())
                if op_sym == "==":
                    return l_val == r_val
                if op_sym == "!=":
                    return l_val != r_val
                if op_sym == ">":
                    return l_val > r_val
                if op_sym == ">=":
                    return l_val >= r_val
                if op_sym == "<":
                    return l_val < r_val
                if op_sym == "<=":
                    return l_val <= r_val
                if op_sym == " IN ":
                    return l_val in r_val if isinstance(r_val, (list, tuple)) else False
                if op_sym == " NOT_IN ":
                    return l_val not in r_val if isinstance(r_val, (list, tuple)) else True
        # Truthy check
        val = self._eval_expr(cond)
        return bool(val)

    def _parse_conditions(self, cond_str: str) -> list[tuple[str, str, Any]]:
        """Parse WHERE conditions into (field, op, value) tuples."""
        conditions = []
        parts = re.split(r"\s+AND\s+", cond_str, flags=re.IGNORECASE)
        for part in parts:
            for op in [">=", "<=", "!=", "==", "=", ">", "<", " IN ", " LIKE "]:
                if op in part:
                    field, value = part.split(op, 1)
                    op_clean = op.strip().replace("=", "==") if op.strip() == "=" else op.strip()
                    conditions.append((field.strip(), op_clean, self._eval_expr(value.strip())))
                    break
        return conditions

    def _match_conditions(self, row: dict, conditions: list[tuple]) -> bool:
        for field, op, value in conditions:
            row_val = row.get(field)
            if op == "==" and row_val != value:
                return False
            if op == "!=" and row_val == value:
                return False
            if op == ">" and not (row_val is not None and row_val > value):
                return False
            if op == ">=" and not (row_val is not None and row_val >= value):
                return False
            if op == "<" and not (row_val is not None and row_val < value):
                return False
            if op == "<=" and not (row_val is not None and row_val <= value):
                return False
            if op == "IN" and row_val not in (value or []):
                return False
        return True

    def _find_block_end(self, lines: list[str], start: int, limit: int) -> int:
        depth = 0
        for i in range(start, limit):
            keyword = lines[i].strip().split()[0].upper() if lines[i].strip().split() else ""
            if keyword in ("FOR", "IF"):
                depth += 1
            elif keyword == "END":
                depth -= 1
                if depth == 0:
                    return i
        raise ScriptError("Unterminated block", start + 1)

    def _find_elif_else(self, lines: list[str], start: int, limit: int) -> int:
        depth = 0
        for i in range(start, limit):
            keyword = lines[i].strip().split()[0].upper() if lines[i].strip().split() else ""
            if keyword in ("FOR", "IF"):
                depth += 1
            elif keyword == "END":
                if depth > 0:
                    depth -= 1
                else:
                    return i
            elif keyword in ("ELIF", "ELSE") and depth == 0:
                return i
        return limit

    @staticmethod
    def _split_list(s: str) -> list[str]:
        """Split comma-separated values respecting nesting."""
        result = []
        depth = 0
        current = ""
        for ch in s:
            if ch in ("(", "["):
                depth += 1
            elif ch in (")", "]"):
                depth -= 1
            elif ch == "," and depth == 0:
                result.append(current)
                current = ""
                continue
            current += ch
        if current.strip():
            result.append(current)
        return result

    @staticmethod
    def _coerce(value: str, type_name: str) -> Any:
        t = type_name.upper()
        if t == "INTEGER":
            return int(value)
        if t == "DECIMAL":
            return float(value)
        if t == "BOOLEAN":
            return value.lower() in ("true", "1", "yes")
        return value


def _safe_serialise(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, (list, tuple)):
        return [_safe_serialise(x) for x in v[:100]]
    if isinstance(v, dict):
        return {k: _safe_serialise(val) for k, val in v.items()}
    return v
