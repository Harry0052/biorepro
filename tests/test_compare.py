from decimal import Decimal

from biorepro.compare import OUTPUT_COLUMNS, compare_tables

TOLERANCES = {"mean_steps": {"abs": "0.01", "rel": "0"}}


def _row(endpoint: str, mean: str, *, n_people: str = "20", n_groups: str = "2") -> dict[str, str]:
    return {
        "endpoint_id": endpoint,
        "estimand": "pooled_mean_daily_steps",
        "unit": "steps_per_person_per_day",
        "n_people": n_people,
        "n_groups": n_groups,
        "mean_steps": mean,
    }


def _compare(actual, expected, tolerances=None):
    rows_a = actual if isinstance(actual, list) else [actual]
    rows_e = expected if isinstance(expected, list) else [expected]
    return compare_tables(OUTPUT_COLUMNS, rows_a, OUTPUT_COLUMNS, rows_e, tolerances=tolerances or TOLERANCES)


def test_clean_rows_match():
    row = _row("walk_challenge", "6540.00")
    result = _compare(row, row)
    assert result.category == "match"
    assert result.differences == []


def test_tolerance_boundary_is_inclusive():
    base = _row("walk_challenge", "6540.00")
    inside = _compare(base, _row("walk_challenge", "6540.01"))
    outside = _compare(base, _row("walk_challenge", "6540.02"))
    assert inside.category == "match"
    assert outside.category == "numeric_disagreement"
    assert outside.differences[0].endpoint_id == "walk_challenge"
    assert outside.differences[0].column == "mean_steps"
    assert Decimal(outside.differences[0].abs_difference) == Decimal("0.02")


def test_seeded_quarter_step_is_named():
    actual = _row("walk_challenge", "6540.00")
    expected = _row("walk_challenge", "6540.25")
    result = _compare(actual, expected)
    assert result.category == "numeric_disagreement"
    assert len(result.differences) == 1
    cell = result.differences[0]
    assert (cell.endpoint_id, cell.column, cell.kind) == ("walk_challenge", "mean_steps", "numeric_disagreement")
    assert result.endpoints == [
        {"endpoint_id": "walk_challenge", "status": "numeric_disagreement", "columns": ["mean_steps"]}
    ]
    assert "clinical" not in result.message.lower()


def test_missing_value_is_distinct_from_zero():
    missing = _compare(_row("control", ""), _row("control", "0"))
    zero = _compare(_row("control", "0"), _row("control", "0"))
    both_missing = _compare(_row("control", ""), _row("control", ""))
    assert missing.category == "missing_value"
    assert missing.differences[0].kind == "missing_value"
    assert zero.category == "match"
    assert both_missing.category == "match"


def test_missing_and_extra_endpoints_have_their_own_category():
    actual = [_row("control", "5988.25")]
    expected = [_row("control", "5988.25"), _row("walk_challenge", "6540.00")]
    missing = _compare(actual, expected)
    extra = _compare(expected, actual)
    assert missing.category == "missing_endpoint"
    assert missing.differences[0].kind == "missing_endpoint"
    assert missing.differences[0].endpoint_id == "walk_challenge"
    assert extra.category == "missing_endpoint"
    assert extra.differences[0].kind == "extra_endpoint"


def test_duplicate_endpoint_key():
    duplicated = [_row("control", "1.00"), _row("control", "2.00")]
    result = _compare(duplicated, [_row("control", "1.00")])
    assert result.category == "duplicate_key"
    assert result.differences == []


def test_schema_change():
    result = compare_tables(
        ["endpoint_id", "mean_steps"],
        [{"endpoint_id": "control", "mean_steps": "1"}],
        OUTPUT_COLUMNS,
        [_row("control", "1")],
        tolerances=TOLERANCES,
    )
    assert result.category == "schema_mismatch"
    assert result.reason == "actual_columns"


def test_relative_tolerance_uses_the_declared_formula():
    tolerances = {"mean_steps": {"abs": "0", "rel": "0.01"}}
    expected = _row("walk_challenge", "100")
    inside = _compare(_row("walk_challenge", "101"), expected, tolerances)
    outside = _compare(_row("walk_challenge", "101.01"), expected, tolerances)
    assert inside.category == "match"
    assert outside.category == "numeric_disagreement"
