"""Join endpoint tables and compare cells under declared tolerances.

Missing cells stay missing. A numeric zero is a present value.
The report names the endpoint and column. It does not invent a cause.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from biorepro.errors import BioreproError
from biorepro.tables import load_csv, parse_decimal, parse_integer, reject_duplicate_keys, require_columns

OUTPUT_COLUMNS = ["endpoint_id", "estimand", "unit", "n_people", "n_groups", "mean_steps"]
PRIMARY_KEY = ["endpoint_id"]
EXACT_INTEGERS = {"n_people", "n_groups"}
STRING_COLUMNS = {"estimand", "unit"}
ASSUMPTION = (
    "mean_steps is the pooled mean of daily steps in steps per person per day; "
    "a cell matches when abs(actual-expected) <= abs_tolerance + rel_tolerance * abs(expected). "
    "n_people and n_groups are exact counts. An empty cell is missing and is not zero."
)


@dataclass
class CellDifference:
    endpoint_id: str
    column: str
    kind: str
    expected: str | None
    actual: str | None
    abs_difference: str | None
    abs_tolerance: str | None
    rel_tolerance: str | None
    assumption: str

    def to_dict(self) -> dict:
        return {
            "endpoint_id": self.endpoint_id,
            "column": self.column,
            "kind": self.kind,
            "expected": self.expected,
            "actual": self.actual,
            "abs_difference": self.abs_difference,
            "abs_tolerance": self.abs_tolerance,
            "rel_tolerance": self.rel_tolerance,
            "assumption": self.assumption,
        }


@dataclass
class Comparison:
    category: str
    message: str
    reason: str | None = None
    differences: list[CellDifference] = field(default_factory=list)
    endpoints: list[dict] = field(default_factory=list)
    schema_ok: bool = False

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "reason": self.reason,
            "message": self.message,
            "schema_ok": self.schema_ok,
            "endpoints": self.endpoints,
            "differences": [item.to_dict() for item in self.differences],
        }


def compare_files(
    actual_path: Path,
    expected_path: Path,
    *,
    tolerances: dict,
    max_bytes: int,
    max_rows: int,
) -> Comparison:
    actual_header, actual_rows = _load_side(actual_path, max_bytes=max_bytes, max_rows=max_rows, role="actual")
    expected_header, expected_rows = _load_side(
        expected_path, max_bytes=max_bytes, max_rows=max_rows, role="expected"
    )
    return compare_tables(
        actual_header,
        actual_rows,
        expected_header,
        expected_rows,
        tolerances=tolerances,
    )


def compare_tables(
    actual_header: list[str],
    actual_rows: list[dict[str, str]],
    expected_header: list[str],
    expected_rows: list[dict[str, str]],
    *,
    tolerances: dict,
) -> Comparison:
    if actual_header != OUTPUT_COLUMNS:
        return Comparison(
            category="schema_mismatch",
            reason="actual_columns",
            message=f"actual columns are {actual_header}; the declared output columns are {OUTPUT_COLUMNS}",
            schema_ok=False,
        )
    if expected_header != OUTPUT_COLUMNS:
        return Comparison(
            category="schema_mismatch",
            reason="expected_columns",
            message=f"expected columns are {expected_header}; the declared output columns are {OUTPUT_COLUMNS}",
            schema_ok=False,
        )
    try:
        reject_duplicate_keys(Path("actual"), actual_rows, PRIMARY_KEY)
        reject_duplicate_keys(Path("expected"), expected_rows, PRIMARY_KEY)
    except BioreproError as exc:
        return Comparison(category=exc.category, reason="endpoint_id", message=exc.message, schema_ok=True)

    mean_tol = tolerances.get("mean_steps")
    if not isinstance(mean_tol, dict):
        raise BioreproError("schema_mismatch", "tolerances.mean_steps is required")
    abs_tol = Decimal(mean_tol["abs"])
    rel_tol = Decimal(mean_tol["rel"])
    if abs_tol < 0 or rel_tol < 0:
        raise BioreproError("malformed_input", "tolerances must be non-negative")

    actual_by_key = {_key(row): row for row in actual_rows}
    expected_by_key = {_key(row): row for row in expected_rows}
    differences: list[CellDifference] = []
    for key in sorted(set(actual_by_key) | set(expected_by_key)):
        actual = actual_by_key.get(key)
        expected = expected_by_key.get(key)
        if actual is None or expected is None:
            differences.append(
                CellDifference(
                    endpoint_id=key,
                    column="endpoint_id",
                    kind="missing_endpoint" if expected is not None else "extra_endpoint",
                    expected=key if expected is not None else None,
                    actual=key if actual is not None else None,
                    abs_difference=None,
                    abs_tolerance=None,
                    rel_tolerance=None,
                    assumption="Rows join on the declared primary key endpoint_id.",
                )
            )
            continue
        differences.extend(_compare_row(key, actual, expected, abs_tol=abs_tol, rel_tol=rel_tol))

    endpoints = _endpoint_status(set(actual_by_key), set(expected_by_key), differences)
    return _summarize(differences, endpoints, abs_tol=abs_tol, rel_tol=rel_tol)


def _load_side(path: Path, *, max_bytes: int, max_rows: int, role: str) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        raise BioreproError("missing_output", f"{role} table is missing: {path}", path=str(path))
    header, rows = load_csv(path, max_bytes=max_bytes, max_rows=max_rows)
    require_columns(path, header, header)
    return header, rows


def _key(row: dict[str, str]) -> str:
    return row["endpoint_id"]


def _compare_row(
    key: str,
    actual: dict[str, str],
    expected: dict[str, str],
    *,
    abs_tol: Decimal,
    rel_tol: Decimal,
) -> list[CellDifference]:
    found: list[CellDifference] = []
    for column in OUTPUT_COLUMNS:
        if column == "endpoint_id":
            continue
        if column in STRING_COLUMNS:
            if actual[column] != expected[column]:
                found.append(
                    CellDifference(
                        endpoint_id=key,
                        column=column,
                        kind="value_disagreement",
                        expected=expected[column],
                        actual=actual[column],
                        abs_difference=None,
                        abs_tolerance=None,
                        rel_tolerance=None,
                        assumption="estimand and unit are declared labels and match only when the text is the same",
                    )
                )
            continue
        if column in EXACT_INTEGERS:
            found.extend(_compare_exact_integer(key, column, actual[column], expected[column]))
            continue
        found.extend(
            _compare_decimal(key, column, actual[column], expected[column], abs_tol=abs_tol, rel_tol=rel_tol)
        )
    return found


def _compare_exact_integer(key: str, column: str, actual_raw: str, expected_raw: str) -> list[CellDifference]:
    actual = _optional_int(actual_raw, column)
    expected = _optional_int(expected_raw, column)
    if actual is None and expected is None:
        return []
    if actual is None or expected is None:
        return [
            CellDifference(
                endpoint_id=key,
                column=column,
                kind="missing_value",
                expected=expected_raw or None,
                actual=actual_raw or None,
                abs_difference=None,
                abs_tolerance="0",
                rel_tolerance="0",
                assumption="An empty count is missing. Zero is a present count and is a different state.",
            )
        ]
    if actual == expected:
        return []
    return [
        CellDifference(
            endpoint_id=key,
            column=column,
            kind="numeric_disagreement",
            expected=str(expected),
            actual=str(actual),
            abs_difference=str(abs(actual - expected)),
            abs_tolerance="0",
            rel_tolerance="0",
            assumption="n_people and n_groups are exact integer counts",
        )
    ]


def _compare_decimal(
    key: str,
    column: str,
    actual_raw: str,
    expected_raw: str,
    *,
    abs_tol: Decimal,
    rel_tol: Decimal,
) -> list[CellDifference]:
    actual = _optional_decimal(actual_raw)
    expected = _optional_decimal(expected_raw)
    if actual is None and expected is None:
        return []
    if actual is None or expected is None:
        return [
            CellDifference(
                endpoint_id=key,
                column=column,
                kind="missing_value",
                expected=None if expected is None else format(expected, "f"),
                actual=None if actual is None else format(actual, "f"),
                abs_difference=None,
                abs_tolerance=format(abs_tol, "f"),
                rel_tolerance=format(rel_tol, "f"),
                assumption="An empty numeric cell is missing. Zero is a present value and is a different state.",
            )
        ]
    difference = abs(actual - expected)
    limit = abs_tol + (rel_tol * abs(expected))
    if difference <= limit:
        return []
    return [
        CellDifference(
            endpoint_id=key,
            column=column,
            kind="numeric_disagreement",
            expected=format(expected, "f"),
            actual=format(actual, "f"),
            abs_difference=format(difference, "f"),
            abs_tolerance=format(abs_tol, "f"),
            rel_tolerance=format(rel_tol, "f"),
            assumption=ASSUMPTION,
        )
    ]


def _optional_int(raw: str, column: str) -> int | None:
    if raw == "":
        return None
    if raw.strip() != raw:
        raise BioreproError("malformed_input", f"{column} value {raw!r} has surrounding whitespace")
    return parse_integer(Path(column), 0, column, raw, minimum=0)


def _optional_decimal(raw: str) -> Decimal | None:
    if raw == "":
        return None
    if raw.strip() != raw:
        raise BioreproError("malformed_input", f"decimal value {raw!r} has surrounding whitespace")
    return parse_decimal(raw)


def _endpoint_status(
    actual_keys: set[str],
    expected_keys: set[str],
    differences: list[CellDifference],
) -> list[dict]:
    grouped: dict[str, list[CellDifference]] = {}
    for item in differences:
        grouped.setdefault(item.endpoint_id, []).append(item)
    order = ("missing_endpoint", "extra_endpoint", "missing_value", "value_disagreement", "numeric_disagreement")
    rows = []
    for key in sorted(actual_keys | expected_keys):
        items = grouped.get(key, [])
        status = "match"
        for kind in order:
            if any(item.kind == kind for item in items):
                status = kind
                break
        rows.append(
            {
                "endpoint_id": key,
                "status": status,
                "columns": [item.column for item in items],
            }
        )
    return rows


def _summarize(
    differences: list[CellDifference],
    endpoints: list[dict],
    *,
    abs_tol: Decimal,
    rel_tol: Decimal,
) -> Comparison:
    if not differences:
        return Comparison(
            category="match",
            message=(
                f"no cell differences within absolute tolerance {format(abs_tol, 'f')} "
                f"and relative tolerance {format(rel_tol, 'f')}"
            ),
            schema_ok=True,
            endpoints=endpoints,
        )
    kinds = {item.kind for item in differences}
    if "missing_endpoint" in kinds or "extra_endpoint" in kinds:
        category = "missing_endpoint"
    elif "missing_value" in kinds:
        category = "missing_value"
    elif "value_disagreement" in kinds and "numeric_disagreement" not in kinds:
        category = "schema_mismatch"
    else:
        category = "numeric_disagreement"
    named = ", ".join(f"{item.endpoint_id}.{item.column}" for item in differences)
    return Comparison(
        category=category,
        message=f"{len(differences)} cell difference(s): {named}",
        schema_ok=True,
        differences=differences,
        endpoints=endpoints,
    )
