"""One command that validates, reruns, compares, and records the malformed path."""

from __future__ import annotations

import json
from pathlib import Path

from biorepro.compare import compare_files
from biorepro.runner import render_markdown, run_fixture

SEEDED_ENDPOINT = "walk_challenge"
SEEDED_COLUMN = "mean_steps"


def run_demo(fixture: Path, output: Path, invalid: Path | None = None) -> dict:
    fixture = fixture.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    clean = run_fixture(fixture, output / "clean", oracle="clean")
    comparison = None
    if clean.output_csv:
        manifest = json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))
        comparison = compare_files(
            Path(clean.output_csv),
            fixture / "oracle" / "perturbed.csv",
            tolerances=manifest["tolerances"],
            max_bytes=manifest["limits"]["max_output_bytes"],
            max_rows=manifest["limits"]["max_rows"],
        )
        payload = comparison.to_dict()
        payload.update(
            {
                "fixture_id": clean.fixture_id,
                "input_sha256": clean.input_sha256,
                "entrypoint_sha256": clean.entrypoint_sha256,
                "image_digest": clean.image_digest,
                "oracle_role": "perturbed",
                "recovery": (
                    "This comparison uses oracle/perturbed.csv. "
                    "The only intended difference is walk_challenge mean_steps, +0.25."
                ),
                "limitation": clean.to_dict()["limitation"],
                "status": "match" if comparison.category == "match" else "rejected",
                "generation_seed": clean.generation_seed,
                "rng_seed": clean.rng_seed,
                "estimand": clean.estimand,
                "unit": clean.unit,
                "worker_created": False,
                "network": "none",
                "schema_ok": comparison.schema_ok,
                "output_csv": clean.output_csv,
                "runtime": clean.runtime,
                "r_version": clean.r_version,
                "reference_digest_match": clean.reference_digest_match,
                "worker_exit_code": None,
                "worker_stderr": None,
            }
        )
        (output / "perturbed-comparison.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output / "perturbed-comparison.md").write_text(render_markdown(payload), encoding="utf-8")

    invalid_evidence = None
    if invalid is not None and invalid.is_dir():
        invalid_evidence = run_fixture(invalid, output / "invalid")

    seeded_ok = _seeded_cell(comparison)
    invalid_ok = invalid_evidence is None or (
        invalid_evidence.worker_created is False and invalid_evidence.category == "schema_mismatch"
    )
    passed = clean.category == "match" and seeded_ok and invalid_ok
    summary = {
        "status": "pass" if passed else "fail",
        "clean_category": clean.category,
        "clean_evidence": str(output / "clean" / "evidence.json"),
        "clean_table": clean.output_csv,
        "perturbed_category": None if comparison is None else comparison.category,
        "perturbed_comparison": str(output / "perturbed-comparison.json") if comparison else None,
        "invalid_category": None if invalid_evidence is None else invalid_evidence.category,
        "invalid_worker_created": None if invalid_evidence is None else invalid_evidence.worker_created,
        "invalid_evidence": None if invalid_evidence is None else str(output / "invalid" / "evidence.json"),
        "trace": {
            "fixture": str(fixture),
            "input": str(fixture / "inputs" / "groups.csv"),
            "input_sha256": clean.input_sha256,
            "script": str(fixture / "script" / "analyze.R"),
            "script_sha256": clean.entrypoint_sha256,
            "hand_calculation": str(fixture / "ORACLE.md"),
            "clean_oracle": str(fixture / "oracle" / "expected.csv"),
            "perturbed_oracle": str(fixture / "oracle" / "perturbed.csv"),
            "seeded_endpoint": SEEDED_ENDPOINT,
            "seeded_column": SEEDED_COLUMN,
        },
    }
    (output / "demo.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "demo.md").write_text(_demo_markdown(summary, clean.message), encoding="utf-8")
    return summary


def _seeded_cell(comparison) -> bool:
    if comparison is None or comparison.category != "numeric_disagreement":
        return False
    if len(comparison.differences) != 1:
        return False
    cell = comparison.differences[0]
    return cell.endpoint_id == SEEDED_ENDPOINT and cell.column == SEEDED_COLUMN


def _demo_markdown(summary: dict, clean_message: str) -> str:
    trace = summary["trace"]
    lines = [
        "# BioRepro demo",
        "",
        f"Demo status: {summary['status']}.",
        "",
        "## 1. Load the sample",
        "",
        f"Fixture directory: `{trace['fixture']}`.",
        "The counts are synthetic group totals. The estimand is the pooled mean of daily steps, in steps per person per day.",
        f"Input SHA-256 `{trace['input_sha256']}` is `inputs/groups.csv`.",
        f"Script SHA-256 `{trace['script_sha256']}` is `script/analyze.R`.",
        f"Hand calculation: `{trace['hand_calculation']}`.",
        "",
        "## 2. Rerun",
        "",
        f"Clean comparison category: {summary['clean_category']}.",
        clean_message,
        f"Table: `{summary['clean_table']}`.",
        f"Evidence: `{summary['clean_evidence']}`.",
        "",
        "## 3. Inspect the seeded difference",
        "",
        "The perturbed oracle changes walk_challenge mean_steps from 6540.00 to 6540.25.",
        f"Comparison category: {summary['perturbed_category']}.",
        f"Report: `{summary['perturbed_comparison']}`.",
        "A match would mean the recomputed cell is within absolute tolerance 0.01. It would not be a clinical validation.",
        "",
        "## 4. Malformed input",
        "",
        f"Invalid fixture category: {summary['invalid_category']}.",
        f"Worker created: {summary['invalid_worker_created']}.",
        f"Evidence: `{summary['invalid_evidence']}`.",
        "Add the missing n_people column, update the manifest hash only after review, and validate again.",
        "",
    ]
    return "\n".join(lines)
