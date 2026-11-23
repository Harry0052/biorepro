"""Command line entry point. JSON goes to stdout. Diagnostics go to stderr."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from biorepro import __version__
from biorepro.errors import EXIT_CODE, BioreproError
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

    args = parser.parse_args(argv)
    if args.command == "validate":
        return _validate_command(args.fixture)
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
