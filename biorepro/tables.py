"""CSV adapters for fixture inputs and endpoint tables.

Missing output cells are None. A numeric zero is 0 or Decimal('0').
Input tables do not accept empty numeric cells; those are malformed.
"""

from __future__ import annotations

import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from biorepro.errors import BioreproError

_INTEGER = re.compile(r"^(0|[1-9][0-9]*)$")


def read_text(path: Path, *, max_bytes: int) -> str:
    size = path.stat().st_size
    if size > max_bytes:
        raise BioreproError(
            "oversized_input",
            f"{path.name} is {size} bytes; the fixture limit is {max_bytes} bytes",
            path=str(path),
        )
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise BioreproError(
            "malformed_input",
            f"{path.name} is not valid UTF-8",
            path=str(path),
        ) from exc


def load_csv(path: Path, *, max_bytes: int, max_rows: int) -> tuple[list[str], list[dict[str, str]]]:
    text = read_text(path, max_bytes=max_bytes)
    if "\x00" in text:
        raise BioreproError("malformed_input", f"{path.name} contains a NUL byte", path=str(path))
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        raise BioreproError("malformed_input", f"{path.name} is empty", path=str(path))
    header = rows[0]
    if any(name == "" for name in header):
        raise BioreproError("schema_mismatch", f"{path.name} has an empty column name", path=str(path))
    if len(set(header)) != len(header):
        raise BioreproError("schema_mismatch", f"{path.name} repeats a column name", path=str(path))
    body = rows[1:]
    if len(body) > max_rows:
        raise BioreproError(
            "oversized_input",
            f"{path.name} has {len(body)} data rows; the fixture limit is {max_rows}",
            path=str(path),
        )
    parsed: list[dict[str, str]] = []
    for index, raw in enumerate(body, start=2):
        if len(raw) != len(header):
            raise BioreproError(
                "malformed_input",
                f"{path.name} line {index} has {len(raw)} fields; the header has {len(header)}",
                path=str(path),
            )
        parsed.append(dict(zip(header, raw)))
    return header, parsed


def require_columns(path: Path, header: list[str], expected: list[str]) -> None:
    if header != expected:
        missing = [name for name in expected if name not in header]
        extra = [name for name in header if name not in expected]
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("unexpected " + ", ".join(extra))
        if not detail and header != expected:
            detail.append(f"column order is {header}; expected {expected}")
        raise BioreproError(
            "schema_mismatch",
            f"{path.name} schema: " + "; ".join(detail),
            path=str(path),
        )


def parse_integer(path: Path, row_number: int, column: str, raw: str, *, minimum: int) -> int:
    if raw == "":
        raise BioreproError(
            "malformed_input",
            f"{path.name} line {row_number} column {column} is empty; input counts must be present",
            path=str(path),
        )
    if not _INTEGER.fullmatch(raw):
        raise BioreproError(
            "malformed_input",
            f"{path.name} line {row_number} column {column} is {raw!r}; expected a non-negative integer",
            path=str(path),
        )
    value = int(raw)
    if value < minimum:
        raise BioreproError(
            "malformed_input",
            f"{path.name} line {row_number} column {column} is {value}; the minimum is {minimum}",
            path=str(path),
        )
    return value


def parse_decimal(raw: str) -> Decimal | None:
    if raw == "":
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise BioreproError("malformed_input", f"value {raw!r} is not a decimal number") from exc
    if not value.is_finite():
        raise BioreproError("malformed_input", f"value {raw!r} is not a finite decimal")
    return value


def require_pattern(path: Path, row_number: int, column: str, raw: str, pattern: re.Pattern[str]) -> str:
    if pattern.fullmatch(raw) is None:
        raise BioreproError(
            "malformed_input",
            f"{path.name} line {row_number} column {column} is {raw!r}; it must match {pattern.pattern}",
            path=str(path),
        )
    return raw


def reject_duplicate_keys(path: Path, rows: list[dict[str, str]], key_columns: list[str]) -> None:
    seen: dict[tuple[str, ...], int] = {}
    for index, row in enumerate(rows, start=2):
        key = tuple(row[column] for column in key_columns)
        if key in seen:
            label = ", ".join(f"{column}={value}" for column, value in zip(key_columns, key))
            raise BioreproError(
                "duplicate_key",
                f"{path.name} line {index} repeats {label}, first used on line {seen[key]}",
                path=str(path),
            )
        seen[key] = index
