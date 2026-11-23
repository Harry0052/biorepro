"""Command line entry point. JSON goes to stdout. Diagnostics go to stderr."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from biorepro import __version__
from biorepro.compare import compare_files
from biorepro.demo import run_demo
from biorepro.errors import EXIT_CODE, BioreproError
from biorepro.runner import exit_code_for, run_fixture
from biorepro.validate import validate_fixture


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="biorepro",
        description="Review a synthetic aggregate fixture and, in later commands, rerun and compare it.",
    )
    parser.add_argument("--version", action="version", version=f"biorepro {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Check a fixture manifest, hashes, isolation policy, and tables")
    validate.add_argument("fixture", type=Path, help="Directory that contains manifest.json")

    run = sub.add_parser("run", help="Review a fixture, rerun it in an isolated worker, and compare the table")
    run.add_argument("fixture", type=Path, help="Directory that contains manifest.json")
    run.add_argument("--output", type=Path, required=True, help="Directory outside the fixture for the table and evidence packet")
    run.add_argument(
        "--oracle",
        choices=("clean", "perturbed"),
        default="clean",
        help="Which declared oracle to compare against (default: clean)",
    )

    demo = sub.add_parser("demo", help="Validate, rerun, compare the perturbed oracle, and reject the invalid fixture")
    demo.add_argument("--fixture", type=Path, default=Path("fixtures/office-wellness"))
    demo.add_argument("--invalid", type=Path, default=Path("fixtures/invalid-missing-column"))
    demo.add_argument("--output", type=Path, required=True, help="Directory for the demo packet")

    compare = sub.add_parser("compare", help="Compare two endpoint tables without starting a worker")
    compare.add_argument("actual", type=Path, help="Table produced by a rerun")
    compare.add_argument("expected", type=Path, help="Oracle table")
    compare.add_argument("--manifest", type=Path, required=True, help="Fixture manifest that declares tolerances and limits")

    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return _validate_command(args.fixture)
        if args.command == "run":
            return _run_command(args.fixture, args.output, args.oracle)
        if args.command == "compare":
            return _compare_command(args.actual, args.expected, args.manifest)
        if args.command == "demo":
            return _demo_command(args.fixture, args.output, args.invalid)
    except BioreproError as exc:
        _emit_error(exc.category, exc.reason, exc.message)
        return exc.exit_code
    parser.error(f"unknown command {args.command}")
    return EXIT_CODE["internal_error"]


def _validate_command(fixture: Path) -> int:
    try:
        report = validate_fixture(fixture)
    except BioreproError as exc:
        payload = {
            "status": "rejected",
            "fixture_id": None,
            "category": exc.category,
            "reason": exc.reason,
            "message": exc.message,
            "fixture_root": str(fixture),
            "checks": [],
        }
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        print(f"rejected {exc.category}: {exc.message}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:  # noqa: BLE001 — the CLI must return a category for unexpected faults
        payload = {
            "status": "rejected",
            "fixture_id": None,
            "category": "internal_error",
            "reason": type(exc).__name__,
            "message": str(exc),
            "fixture_root": str(fixture),
            "checks": [],
        }
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        print(f"rejected internal_error: {exc}", file=sys.stderr)
        return EXIT_CODE["internal_error"]

    json.dump(report.to_dict(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if report.status == "valid":
        print(report.message, file=sys.stderr)
        return EXIT_CODE["valid"]
    print(f"rejected {report.category}: {report.message}", file=sys.stderr)
    assert report.category is not None
    return EXIT_CODE[report.category]


def _run_command(fixture: Path, output: Path, oracle: str) -> int:
    evidence = run_fixture(fixture, output, oracle=oracle)
    json.dump(evidence.to_dict(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    print(evidence.message, file=sys.stderr)
    return exit_code_for(evidence)


def _demo_command(fixture: Path, output: Path, invalid: Path) -> int:
    summary = run_demo(fixture, output, invalid if invalid.exists() else None)
    json.dump(summary, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    print(f"demo {summary['status']}: {output}", file=sys.stderr)
    return 0 if summary["status"] == "pass" else 1


def _compare_command(actual: Path, expected: Path, manifest_path: Path) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    comparison = compare_files(
        actual,
        expected,
        tolerances=manifest["tolerances"],
        max_bytes=manifest["limits"]["max_output_bytes"],
        max_rows=manifest["limits"]["max_rows"],
    )
    json.dump(comparison.to_dict(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    print(comparison.message, file=sys.stderr)
    return EXIT_CODE[comparison.category]


def _emit_error(category: str, reason: str | None, message: str) -> None:
    payload = {"status": "rejected", "category": category, "reason": reason, "message": message}
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    print(f"rejected {category}: {message}", file=sys.stderr)
