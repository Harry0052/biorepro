import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from biorepro.cli import main
from biorepro.errors import EXIT_CODE
from biorepro.hashutil import sha256_file
from biorepro.tables import load_csv
from biorepro.validate import validate_fixture

ROOT = Path(__file__).resolve().parents[1]
VALID = ROOT / "fixtures" / "office-wellness"
INVALID = ROOT / "fixtures" / "invalid-missing-column"


def test_valid_fixture_is_accepted():
    report = validate_fixture(VALID)
    assert report.status == "valid"
    assert report.category is None
    assert report.fixture_id == "office-wellness"
    names = [item.name for item in report.checks]
    assert "hash:inputs/groups.csv" in names
    assert "hash:script/analyze.R" in names
    assert "isolation" in names


def test_valid_fixture_cli_exit_code(capsys):
    code = main(["validate", str(VALID)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 0
    assert payload["status"] == "valid"
    assert "fixture office-wellness accepted" in captured.err
    again = main(["validate", str(VALID)])
    captured_again = capsys.readouterr()
    assert again == 0
    assert captured_again.out == captured.out


def test_missing_column_fixture_is_rejected():
    report = validate_fixture(INVALID)
    assert report.status == "rejected"
    assert report.category == "schema_mismatch"
    assert "n_people" in report.message


def test_missing_column_cli_exit_code(capsys):
    code = main(["validate", str(INVALID)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == EXIT_CODE["schema_mismatch"]
    assert payload["category"] == "schema_mismatch"
    assert "n_people" in payload["message"]
    assert "rejected schema_mismatch" in captured.err


def test_clean_oracle_matches_hand_calculation():
    _header, rows = load_csv(VALID / "inputs" / "groups.csv", max_bytes=10**6, max_rows=100)
    totals: dict[str, list[int]] = {}
    for row in rows:
        people, steps = totals.setdefault(row["arm"], [0, 0])
        totals[row["arm"]] = [people + int(row["n_people"]), steps + int(row["steps_sum"])]
    expected = {
        arm: (Decimal(steps) / Decimal(people)).quantize(Decimal("0.01"))
        for arm, (people, steps) in totals.items()
    }
    assert expected == {
        "walk_challenge": Decimal("6540.00"),
        "standing_break": Decimal("6120.50"),
        "control": Decimal("5988.25"),
    }
    _header, oracle = load_csv(VALID / "oracle" / "expected.csv", max_bytes=10**6, max_rows=100)
    observed = {row["endpoint_id"]: Decimal(row["mean_steps"]) for row in oracle}
    assert observed == expected


def test_perturbed_oracle_changes_one_cell():
    _header, clean = load_csv(VALID / "oracle" / "expected.csv", max_bytes=10**6, max_rows=100)
    _header, perturbed = load_csv(VALID / "oracle" / "perturbed.csv", max_bytes=10**6, max_rows=100)
    clean_map = {row["endpoint_id"]: row for row in clean}
    perturbed_map = {row["endpoint_id"]: row for row in perturbed}
    assert set(clean_map) == set(perturbed_map)
    for key, row in clean_map.items():
        other = perturbed_map[key]
        for column, value in row.items():
            if key == "walk_challenge" and column == "mean_steps":
                assert Decimal(other[column]) - Decimal(value) == Decimal("0.25")
            else:
                assert other[column] == value


def _copy_valid(tmp_path: Path) -> Path:
    destination = tmp_path / "fixture"
    shutil.copytree(VALID, destination)
    return destination


def _rewrite_manifest(root: Path, mutate) -> None:
    path = root / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    mutate(manifest)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def test_hash_mismatch_rejects_before_any_other_story(tmp_path):
    root = _copy_valid(tmp_path)

    def mutate(manifest):
        manifest["entrypoint"]["sha256"] = "0" * 64

    _rewrite_manifest(root, mutate)
    report = validate_fixture(root)
    assert report.category == "review_rejected"
    assert report.reason == "entrypoint_hash"
    assert "No worker was created" in report.message


def test_duplicate_group_id(tmp_path):
    root = _copy_valid(tmp_path)
    groups = root / "inputs" / "groups.csv"
    text = groups.read_text(encoding="utf-8")
    first = text.splitlines()[1]
    groups.write_text(text + first + "\n", encoding="utf-8")

    def mutate(manifest):
        manifest["inputs"][0]["sha256"] = sha256_file(groups)

    _rewrite_manifest(root, mutate)
    report = validate_fixture(root)
    assert report.category == "duplicate_key"
    assert "group_id=g1" in report.message


def test_oversized_input(tmp_path):
    root = _copy_valid(tmp_path)

    def mutate(manifest):
        manifest["limits"]["max_input_bytes"] = 32

    _rewrite_manifest(root, mutate)
    report = validate_fixture(root)
    assert report.category == "oversized_input"
    assert "32" in report.message


def test_zero_people_is_malformed(tmp_path):
    root = _copy_valid(tmp_path)
    groups = root / "inputs" / "groups.csv"
    groups.write_text(
        "group_id,arm,n_people,steps_sum\ng9,control,0,10\n",
        encoding="utf-8",
    )

    def mutate(manifest):
        manifest["inputs"][0]["sha256"] = sha256_file(groups)

    _rewrite_manifest(root, mutate)
    report = validate_fixture(root)
    assert report.category == "malformed_input"
    assert "minimum is 1" in report.message


def test_path_escape_is_rejected(tmp_path):
    root = _copy_valid(tmp_path)

    def mutate(manifest):
        manifest["inputs"][0]["path"] = "../groups.csv"

    _rewrite_manifest(root, mutate)
    report = validate_fixture(root)
    assert report.category == "review_rejected"
    assert report.reason == "path_escape"


def test_symlink_is_rejected(tmp_path):
    root = _copy_valid(tmp_path)
    groups = root / "inputs" / "groups.csv"
    target = groups.read_bytes()
    groups.unlink()
    outside = tmp_path / "outside.csv"
    outside.write_bytes(target)
    groups.symlink_to(outside)
    report = validate_fixture(root)
    assert report.category == "review_rejected"
    assert report.reason == "symlink"


def test_network_enabled_manifest_is_rejected(tmp_path):
    root = _copy_valid(tmp_path)

    def mutate(manifest):
        manifest["isolation"]["network"] = "bridge"

    _rewrite_manifest(root, mutate)
    report = validate_fixture(root)
    assert report.category == "review_rejected"
    assert report.reason == "network_enabled"
    assert "No worker was created" in report.message


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0
    captured = capsys.readouterr()
    assert "validate" in captured.out
