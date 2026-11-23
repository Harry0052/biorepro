"""Fixture review that runs before any worker is created."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from biorepro.errors import BioreproError
from biorepro.hashutil import sha256_file
from biorepro.tables import (
    load_csv,
    parse_decimal,
    parse_integer,
    reject_duplicate_keys,
    require_columns,
    require_pattern,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GROUP_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ARM = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_FIXTURE_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_INPUT_COLUMNS = ["group_id", "arm", "n_people", "steps_sum"]
_OUTPUT_COLUMNS = ["endpoint_id", "estimand", "unit", "n_people", "n_groups", "mean_steps"]
_MANIFEST_NAME = "manifest.json"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class ValidationReport:
    status: str
    fixture_id: str | None
    category: str | None
    reason: str | None
    message: str
    fixture_root: str
    checks: list[Check] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "fixture_id": self.fixture_id,
            "category": self.category,
            "reason": self.reason,
            "message": self.message,
            "fixture_root": self.fixture_root,
            "checks": [{"name": item.name, "ok": item.ok, "detail": item.detail} for item in self.checks],
        }


def validate_fixture(root: Path) -> ValidationReport:
    root = root.resolve()
    checks: list[Check] = []
    fixture_id: str | None = None
    try:
        manifest = _load_manifest(root, checks)
        fixture_id = manifest["fixture_id"]
        declared = _declared_paths(manifest)
        _reject_unexpected_files(root, declared, checks)
        _check_hashes(root, manifest, checks)
        _check_isolation(manifest, checks)
        _check_contract_fields(manifest, checks)
        _check_groups_table(root, manifest, checks)
        _check_oracle_shapes(root, manifest, checks)
    except BioreproError as exc:
        checks.append(Check(exc.category, False, exc.message))
        return ValidationReport(
            status="rejected",
            fixture_id=fixture_id,
            category=exc.category,
            reason=exc.reason,
            message=exc.message,
            fixture_root=str(root),
            checks=checks,
        )
    digest = manifest["image"]["digest"]
    if digest is None:
        checks.append(Check("image_digest", True, "unpinned; run remains blocked until P03 records a digest"))
    else:
        checks.append(Check("image_digest", True, digest))
    return ValidationReport(
        status="valid",
        fixture_id=fixture_id,
        category=None,
        reason=None,
        message=f"fixture {fixture_id} accepted",
        fixture_root=str(root),
        checks=checks,
    )


def _load_manifest(root: Path, checks: list[Check]) -> dict:
    if not root.is_dir():
        raise BioreproError("malformed_input", f"{root} is not a directory", path=str(root))
    path = root / _MANIFEST_NAME
    _require_regular_file(path)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BioreproError(
            "malformed_input",
            f"manifest.json is not JSON: {exc.msg} at line {exc.lineno}",
            path=str(path),
        ) from exc
    if not isinstance(manifest, dict):
        raise BioreproError("malformed_input", "manifest.json must be a JSON object", path=str(path))
    if manifest.get("manifest_version") != 1:
        raise BioreproError(
            "schema_mismatch",
            "manifest_version must be 1",
            path=str(path),
        )
    fixture_id = manifest.get("fixture_id")
    if not isinstance(fixture_id, str) or _FIXTURE_ID.fullmatch(fixture_id) is None:
        raise BioreproError(
            "malformed_input",
            "fixture_id must be a lowercase identifier",
            path=str(path),
        )
    checks.append(Check("manifest", True, f"version 1, fixture_id {fixture_id}"))
    return manifest


def _require_regular_file(path: Path) -> None:
    if path.is_symlink():
        raise BioreproError(
            "review_rejected",
            f"{path.name} is a symlink; fixture files must be regular files inside the fixture directory",
            reason="symlink",
            path=str(path),
        )
    if not path.is_file():
        raise BioreproError("malformed_input", f"required file is missing: {path.name}", path=str(path))


def _relative_posix(root: Path, raw: object, *, label: str) -> str:
    if not isinstance(raw, str) or raw == "":
        raise BioreproError("malformed_input", f"{label} must be a relative path")
    if raw.startswith("/") or "\\" in raw:
        raise BioreproError("review_rejected", f"{label} must stay inside the fixture directory", reason="path_escape")
    parts = Path(raw).parts
    if any(part in {"..", ""} for part in parts):
        raise BioreproError("review_rejected", f"{label} must stay inside the fixture directory", reason="path_escape")
    candidate = root.joinpath(*parts)
    if candidate.is_symlink():
        raise BioreproError(
            "review_rejected",
            f"{raw} is a symlink; fixture files must be regular files inside the fixture directory",
            reason="symlink",
            path=str(candidate),
        )
    if candidate.exists():
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise BioreproError(
                "review_rejected",
                f"{label} resolves outside the fixture directory",
                reason="path_escape",
            ) from exc
    return raw


def _declared_paths(manifest: dict) -> set[str]:
    paths = {_MANIFEST_NAME}
    for label, key in (("inputs", "inputs"), ("oracles", "oracles"), ("notes", "notes")):
        entries = manifest.get(key)
        if not isinstance(entries, list):
            raise BioreproError("schema_mismatch", f"{label} must be a list")
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict) or "path" not in entry:
                raise BioreproError("schema_mismatch", f"{label}[{index}] needs a path")
            paths.add(entry["path"])
    entrypoint = manifest.get("entrypoint")
    if not isinstance(entrypoint, dict) or "path" not in entrypoint:
        raise BioreproError("schema_mismatch", "entrypoint.path is required")
    paths.add(entrypoint["path"])
    return paths


def _reject_unexpected_files(root: Path, declared: set[str], checks: list[Check]) -> None:
    for raw in declared:
        _relative_posix(root, raw, label=raw)
    found: set[str] = set()
    found_dirs: set[str] = set()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise BioreproError(
                "review_rejected",
                f"{rel} is a symlink; fixture files must be regular files",
                reason="symlink",
                path=str(path),
            )
        if path.is_file():
            found.add(rel)
        elif path.is_dir():
            found_dirs.add(rel)
        else:
            raise BioreproError("malformed_input", f"{rel} is not a regular file", path=str(path))
    extra = sorted(found - declared)
    missing = sorted(declared - found)
    if extra:
        raise BioreproError(
            "review_rejected",
            "fixture contains undeclared files: " + ", ".join(extra),
            reason="undeclared_file",
        )
    if missing:
        raise BioreproError("malformed_input", "manifest names missing files: " + ", ".join(missing))
    allowed_dirs = {str(Path(item).parent.as_posix()) for item in declared}
    allowed_dirs.discard(".")
    extra_dirs = sorted(found_dirs - allowed_dirs)
    if extra_dirs:
        raise BioreproError(
            "review_rejected",
            "fixture contains undeclared directories: " + ", ".join(extra_dirs),
            reason="undeclared_file",
        )
    checks.append(Check("fixture_tree", True, f"{len(found)} declared files"))


def _check_hashes(root: Path, manifest: dict, checks: list[Check]) -> None:
    entries: list[tuple[str, dict]] = []
    for key in ("inputs", "oracles", "notes"):
        for entry in manifest[key]:
            entries.append((key, entry))
    entries.append(("entrypoint", manifest["entrypoint"]))
    for label, entry in entries:
        rel = _relative_posix(root, entry.get("path"), label=f"{label}.path")
        expected = entry.get("sha256")
        if not isinstance(expected, str) or _SHA256.fullmatch(expected) is None:
            raise BioreproError(
                "malformed_input",
                f"{rel} sha256 must be 64 lowercase hex characters",
                path=rel,
            )
        path = root / rel
        _require_regular_file(path)
        actual = sha256_file(path)
        if actual != expected:
            raise BioreproError(
                "review_rejected",
                f"{rel} sha256 is {actual}; the manifest allowlist has {expected}. No worker was created.",
                reason=f"{label}_hash",
                path=rel,
            )
        checks.append(Check(f"hash:{rel}", True, actual))


def _check_isolation(manifest: dict, checks: list[Check]) -> None:
    isolation = manifest.get("isolation")
    if not isinstance(isolation, dict):
        raise BioreproError("schema_mismatch", "isolation must be an object")
    network = isolation.get("network")
    if network != "none":
        raise BioreproError(
            "review_rejected",
            f"isolation.network is {network!r}; the only accepted value is 'none'. No worker was created.",
            reason="network_enabled",
        )
    if isolation.get("run_as_root") is not False:
        raise BioreproError(
            "review_rejected",
            "isolation.run_as_root must be false. No worker was created.",
            reason="runs_as_root",
        )
    if isolation.get("read_only_inputs") is not True:
        raise BioreproError(
            "review_rejected",
            "isolation.read_only_inputs must be true. No worker was created.",
            reason="inputs_not_read_only",
        )
    checks.append(Check("isolation", True, "network none, non-root, read-only inputs"))


def _check_contract_fields(manifest: dict, checks: list[Check]) -> None:
    if "doi" not in manifest or manifest["doi"] is not None:
        raise BioreproError(
            "malformed_input",
            "doi must be present and null; this fixture is original synthetic data and is not a published dataset",
        )
    seed = manifest.get("generation_seed")
    if not isinstance(seed, int):
        raise BioreproError("malformed_input", "generation_seed must be an integer")
    if manifest.get("rng_seed") is not None:
        raise BioreproError(
            "malformed_input",
            "rng_seed must be null; the pooled-mean estimand does not use randomness",
        )
    estimand = manifest.get("estimand")
    if not isinstance(estimand, dict) or estimand.get("name") != "pooled_mean_daily_steps":
        raise BioreproError("schema_mismatch", "estimand.name must be pooled_mean_daily_steps")
    if estimand.get("unit") != "steps_per_person_per_day":
        raise BioreproError("schema_mismatch", "estimand.unit must be steps_per_person_per_day")
    output = manifest.get("output_schema")
    if not isinstance(output, dict):
        raise BioreproError("schema_mismatch", "output_schema must be an object")
    columns = output.get("columns")
    if columns != _OUTPUT_COLUMNS:
        raise BioreproError(
            "schema_mismatch",
            f"output_schema.columns must be {_OUTPUT_COLUMNS}",
        )
    if output.get("primary_key") != ["endpoint_id"]:
        raise BioreproError("schema_mismatch", "output_schema.primary_key must be ['endpoint_id']")
    tolerances = manifest.get("tolerances")
    if not isinstance(tolerances, dict) or set(tolerances) != {"mean_steps"}:
        raise BioreproError("schema_mismatch", "tolerances must declare mean_steps and no other column")
    mean_tol = tolerances["mean_steps"]
    if not isinstance(mean_tol, dict) or mean_tol.get("abs") != "0.01" or mean_tol.get("rel") != "0":
        raise BioreproError(
            "schema_mismatch",
            "mean_steps tolerance must be abs 0.01 and rel 0, written as decimal strings",
        )
    limits = manifest.get("limits")
    if not isinstance(limits, dict):
        raise BioreproError("schema_mismatch", "limits must be an object")
    for key, minimum in (
        ("max_input_bytes", 1),
        ("max_rows", 1),
        ("max_output_bytes", 1),
        ("timeout_seconds", 1),
        ("memory_mb", 1),
    ):
        value = limits.get(key)
        if not isinstance(value, int) or value < minimum:
            raise BioreproError("malformed_input", f"limits.{key} must be an integer >= {minimum}")
    image = manifest.get("image")
    if not isinstance(image, dict) or not isinstance(image.get("name"), str) or image["name"] == "":
        raise BioreproError("schema_mismatch", "image.name is required")
    digest = image.get("digest")
    if digest is not None and (not isinstance(digest, str) or not digest.startswith("sha256:") or _SHA256.fullmatch(digest[7:]) is None):
        raise BioreproError(
            "malformed_input",
            "image.digest must be null or sha256: followed by 64 lowercase hex characters",
        )
    entry = manifest["entrypoint"]
    if entry.get("interpreter") != "Rscript" or entry.get("args") != ["--vanilla"]:
        raise BioreproError(
            "review_rejected",
            "entrypoint interpreter must be Rscript with args ['--vanilla']",
            reason="entrypoint_allowlist",
        )
    if Path(entry["path"]).name != "analyze.R":
        raise BioreproError(
            "review_rejected",
            "the only allowlisted analysis file name is analyze.R",
            reason="entrypoint_allowlist",
        )
    checks.append(Check("contract", True, f"seed {seed}, estimand {estimand['name']}"))


def _limits(manifest: dict) -> tuple[int, int]:
    limits = manifest["limits"]
    return limits["max_input_bytes"], limits["max_rows"]


def _check_groups_table(root: Path, manifest: dict, checks: list[Check]) -> None:
    inputs = manifest["inputs"]
    if len(inputs) != 1 or inputs[0]["path"] != "inputs/groups.csv":
        raise BioreproError("schema_mismatch", "the fixture must declare exactly inputs/groups.csv")
    path = root / "inputs" / "groups.csv"
    max_bytes, max_rows = _limits(manifest)
    header, rows = load_csv(path, max_bytes=max_bytes, max_rows=max_rows)
    require_columns(path, header, _INPUT_COLUMNS)
    if not rows:
        raise BioreproError("malformed_input", "inputs/groups.csv has no data rows", path=str(path))
    reject_duplicate_keys(path, rows, ["group_id"])
    for index, row in enumerate(rows, start=2):
        require_pattern(path, index, "group_id", row["group_id"], _GROUP_ID)
        require_pattern(path, index, "arm", row["arm"], _ARM)
        parse_integer(path, index, "n_people", row["n_people"], minimum=1)
        parse_integer(path, index, "steps_sum", row["steps_sum"], minimum=0)
    checks.append(Check("groups_table", True, f"{len(rows)} groups"))


def _check_oracle_shapes(root: Path, manifest: dict, checks: list[Check]) -> None:
    oracles = manifest["oracles"]
    roles = {entry.get("role"): entry.get("path") for entry in oracles}
    if roles.get("clean") != "oracle/expected.csv" or roles.get("perturbed") != "oracle/perturbed.csv":
        raise BioreproError(
            "schema_mismatch",
            "oracles must be oracle/expected.csv (clean) and oracle/perturbed.csv (perturbed)",
        )
    max_bytes, max_rows = _limits(manifest)
    for rel in ("oracle/expected.csv", "oracle/perturbed.csv"):
        path = root / rel
        header, rows = load_csv(path, max_bytes=max_bytes, max_rows=max_rows)
        require_columns(path, header, _OUTPUT_COLUMNS)
        if not rows:
            raise BioreproError("malformed_input", f"{rel} has no data rows", path=str(path))
        reject_duplicate_keys(path, rows, ["endpoint_id"])
        for index, row in enumerate(rows, start=2):
            require_pattern(path, index, "endpoint_id", row["endpoint_id"], _ARM)
            if row["estimand"] != "pooled_mean_daily_steps" or row["unit"] != "steps_per_person_per_day":
                raise BioreproError(
                    "schema_mismatch",
                    f"{rel} line {index} must use estimand pooled_mean_daily_steps and unit steps_per_person_per_day",
                    path=str(path),
                )
            parse_integer(path, index, "n_people", row["n_people"], minimum=1)
            parse_integer(path, index, "n_groups", row["n_groups"], minimum=1)
            parsed = parse_decimal(row["mean_steps"])
            if parsed is None:
                raise BioreproError(
                    "malformed_input",
                    f"{rel} line {index} mean_steps is empty; shipped oracles must be complete",
                    path=str(path),
                )
    checks.append(Check("oracle_schema", True, "clean and perturbed tables match the output schema"))
