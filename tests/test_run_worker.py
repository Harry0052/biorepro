import json
import shutil
from decimal import Decimal
from pathlib import Path

from biorepro.cli import main
from biorepro.hashutil import sha256_file
from biorepro.runner import run_fixture
from tests.test_validate import VALID

SLEEP = """#!/usr/bin/env Rscript
Sys.sleep(30)
cat("should have been stopped\\n")
"""

NO_OUTPUT = """#!/usr/bin/env Rscript
cat("reviewed script that writes no table\\n")
quit(status = 0)
"""

ALLOCATE = """#!/usr/bin/env Rscript
raw <- raw(128 * 1024 * 1024)
cat(length(raw), "\\n")
"""


def _with_script(tmp_path: Path, script: str, **limits) -> Path:
    root = tmp_path / "fixture"
    shutil.copytree(VALID, root)
    path = root / "script" / "analyze.R"
    path.write_text(script, encoding="utf-8")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["entrypoint"]["sha256"] = sha256_file(path)
    manifest["limits"].update(limits)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return root


def test_clean_rerun_is_deterministic(tmp_path):
    first = run_fixture(VALID, tmp_path / "first")
    second = run_fixture(VALID, tmp_path / "second")
    assert first.category == "match"
    assert second.category == "match"
    assert first.worker_created is True
    assert first.differences == []
    assert second.differences == []
    assert (tmp_path / "first" / "endpoints.csv").read_bytes() == (tmp_path / "second" / "endpoints.csv").read_bytes()
    assert first.input_sha256 == second.input_sha256
    assert first.entrypoint_sha256 == second.entrypoint_sha256
    assert first.image_digest == second.image_digest
    assert first.generation_seed == 20261123


def test_perturbed_oracle_names_the_seeded_cell(tmp_path):
    evidence = run_fixture(VALID, tmp_path / "perturbed", oracle="perturbed")
    assert evidence.category == "numeric_disagreement"
    assert evidence.worker_created is True
    assert len(evidence.differences) == 1
    cell = evidence.differences[0]
    assert cell["endpoint_id"] == "walk_challenge"
    assert cell["column"] == "mean_steps"
    assert cell["kind"] == "numeric_disagreement"
    assert Decimal(cell["abs_difference"]) == Decimal("0.25")
    text = (tmp_path / "perturbed" / "evidence.md").read_text(encoding="utf-8")
    assert "walk_challenge" in text
    assert "mean_steps" in text
    assert "not a clinical validation" in text


def test_compare_cli_does_not_need_a_worker(tmp_path, capsys):
    run_fixture(VALID, tmp_path / "clean")
    code = main(
        [
            "compare",
            str(tmp_path / "clean" / "endpoints.csv"),
            str(VALID / "oracle" / "perturbed.csv"),
            "--manifest",
            str(VALID / "manifest.json"),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["differences"][0]["endpoint_id"] == "walk_challenge"
    assert payload["differences"][0]["column"] == "mean_steps"


def test_timeout_is_not_a_numeric_disagreement(tmp_path):
    root = _with_script(tmp_path, SLEEP, timeout_seconds=2)
    evidence = run_fixture(root, tmp_path / "out")
    assert evidence.category == "timeout"
    assert evidence.worker_created is True
    assert evidence.differences == []


def test_missing_output_is_not_a_numeric_disagreement(tmp_path):
    root = _with_script(tmp_path, NO_OUTPUT)
    evidence = run_fixture(root, tmp_path / "out")
    assert evidence.category == "missing_output"
    assert evidence.worker_created is True
    assert evidence.category != "numeric_disagreement"


def test_memory_limit_is_not_a_numeric_disagreement(tmp_path):
    root = _with_script(tmp_path, ALLOCATE, memory_mb=32)
    evidence = run_fixture(root, tmp_path / "out")
    assert evidence.category == "resource_limit"
    assert evidence.reason == "memory"
    assert evidence.worker_created is True
    assert evidence.differences == []
