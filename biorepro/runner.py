"""Run the allowlisted script only after review, then compare the table.

Worker creation is the podman invocation. Hash, isolation, and digest failures
return before that call.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from biorepro.compare import Comparison, compare_files
from biorepro.errors import EXIT_CODE, BioreproError
from biorepro.hashutil import sha256_file
from biorepro.validate import ValidationReport, validate_fixture


@dataclass
class WorkerResult:
    exit_code: int
    stdout: str
    stderr: str
    elapsed_seconds: float = 0.0


class PodmanLauncher:
    """Rootless podman. The process inside the container is the host user, not root."""

    def image_id(self, name: str) -> str | None:
        completed = subprocess.run(
            ["podman", "image", "inspect", name, "--format", "{{.Digest}}"],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            return None
        value = completed.stdout.strip()
        return value or None

    def image_labels(self, name: str) -> dict:
        completed = subprocess.run(
            ["podman", "image", "inspect", name, "--format", "{{json .Config.Labels}}"],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            return {}
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def image_base_layer(self, name: str) -> str | None:
        completed = subprocess.run(
            ["podman", "image", "inspect", name, "--format", "{{index .RootFS.Layers 0}}"],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            return None
        value = completed.stdout.strip()
        return value or None

    def runtime_version(self) -> str:
        completed = subprocess.run(["podman", "--version"], check=False, capture_output=True, text=True)
        return completed.stdout.strip() or completed.stderr.strip()

    def run(self, spec: "WorkerSpec") -> WorkerResult:
        argv = podman_argv(spec)
        started = time.monotonic()
        completed = subprocess.run(argv, check=False, capture_output=True, text=True)
        return WorkerResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            elapsed_seconds=time.monotonic() - started,
        )


@dataclass
class WorkerSpec:
    image: str
    user: str
    memory_mb: int
    timeout_seconds: int
    output_byte_limit: int
    input_dir: Path
    script_dir: Path
    output_dir: Path
    command: list[str]
    network: str = "none"
    read_only_inputs: bool = True
    run_as_root: bool = False


def podman_argv(spec: WorkerSpec) -> list[str]:
    if spec.network != "none":
        raise BioreproError(
            "review_rejected",
            f"refusing to create a worker with network {spec.network!r}",
            reason="network_enabled",
        )
    if spec.run_as_root:
        raise BioreproError(
            "review_rejected",
            "refusing to create a worker that runs as root",
            reason="runs_as_root",
        )
    if not spec.read_only_inputs:
        raise BioreproError(
            "review_rejected",
            "refusing to create a worker with writable inputs",
            reason="inputs_not_read_only",
        )
    uid, gid = spec.user.split(":", 1)
    if uid == "0" or gid == "0":
        raise BioreproError(
            "review_rejected",
            "refusing to create a worker with uid or gid 0",
            reason="runs_as_root",
        )
    return [
        "podman",
        "run",
        "--rm",
        "--network=none",
        "--userns=keep-id",
        "--user",
        spec.user,
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        f"--memory={spec.memory_mb}m",
        f"--memory-swap={spec.memory_mb}m",
        "--cpus=1",
        "--pids-limit=128",
        f"--timeout={spec.timeout_seconds}",
        f"--ulimit=fsize={spec.output_byte_limit}:{spec.output_byte_limit}",
        "--mount",
        f"type=bind,src={spec.input_dir},dst=/inputs,ro=true",
        "--mount",
        f"type=bind,src={spec.script_dir},dst=/script,ro=true",
        "--mount",
        f"type=bind,src={spec.output_dir},dst=/output",
        spec.image,
        *spec.command,
    ]


@dataclass
class Evidence:
    status: str
    category: str | None
    reason: str | None
    message: str
    fixture_id: str | None
    estimand: str | None
    unit: str | None
    generation_seed: int | None
    rng_seed: None
    input_sha256: str | None
    entrypoint_sha256: str | None
    image_digest: str | None
    worker_created: bool
    network: str | None
    schema_ok: bool | None
    output_csv: str | None
    differences: list[dict]
    runtime: str | None = None
    r_version: str | None = None
    worker_exit_code: int | None = None
    worker_stderr: str | None = None
    reference_digest_match: bool | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "category": self.category,
            "reason": self.reason,
            "message": self.message,
            "fixture_id": self.fixture_id,
            "estimand": self.estimand,
            "unit": self.unit,
            "generation_seed": self.generation_seed,
            "rng_seed": self.rng_seed,
            "input_sha256": self.input_sha256,
            "entrypoint_sha256": self.entrypoint_sha256,
            "image_digest": self.image_digest,
            "worker_created": self.worker_created,
            "network": self.network,
            "schema_ok": self.schema_ok,
            "output_csv": self.output_csv,
            "differences": self.differences,
            "runtime": self.runtime,
            "r_version": self.r_version,
            "worker_exit_code": self.worker_exit_code,
            "worker_stderr": self.worker_stderr,
            "reference_digest_match": self.reference_digest_match,
            "limitation": (
                "A match is outcome agreement under the recorded tolerances and inputs. "
                "It is not a clinical validation."
            ),
        }


def run_fixture(
    fixture: Path,
    output_dir: Path,
    *,
    oracle: str = "clean",
    launcher: PodmanLauncher | None = None,
) -> Evidence:
    fixture = fixture.resolve()
    output_dir = output_dir.resolve()
    try:
        output_dir.relative_to(fixture)
    except ValueError:
        inside = False
    else:
        inside = True
    if inside:
        raise BioreproError(
            "review_rejected",
            "the output directory must be outside the fixture directory",
            reason="output_inside_fixture",
        )

    try:
        manifest = _read_manifest(fixture)
    except (OSError, json.JSONDecodeError):
        manifest = None
    validation = validate_fixture(fixture)
    identity = _identity(manifest)
    if validation.status != "valid":
        return _finish(output_dir, _from_validation(validation, identity))

    digest = manifest["image"]["digest"]
    if not isinstance(digest, str):
        return _finish(
            output_dir,
            _rejected(
                identity,
                category="review_rejected",
                reason="image_unpinned",
                message="image.digest is null. Build and vet the worker image before a run. No worker was created.",
            ),
        )

    try:
        _recheck_hashes(fixture, manifest)
    except BioreproError as exc:
        return _finish(
            output_dir,
            _rejected(identity, category=exc.category, reason=exc.reason or "hash", message=exc.message),
        )
    launcher = launcher or PodmanLauncher()
    local_id = launcher.image_id(manifest["image"]["name"])
    if local_id is None:
        return _finish(
            output_dir,
            _rejected(
                identity,
                category="isolation_blocked",
                reason="image_missing",
                message=(
                    f"local image {manifest['image']['name']} is not present. "
                    "Build it from deploy/Containerfile and confirm the digest. No worker was created."
                ),
            ),
        )
    reference_match = local_id == digest
    if not reference_match and not _recipe_matches(launcher, manifest):
        return _finish(
            output_dir,
            _rejected(
                identity,
                category="review_rejected",
                reason="image_digest",
                message=(
                    f"local image digest is {local_id}; the manifest reference is {digest}. "
                    "The base layer and Containerfile hash labels also do not match. No worker was created."
                ),
            ),
        )
    manifest["_reference_digest_match"] = reference_match

    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("endpoints.csv", "evidence.json", "evidence.md"):
        stale = output_dir / name
        if stale.exists():
            stale.unlink()
    spec = _spec(manifest, fixture, output_dir)
    result = launcher.run(spec)
    output_csv = output_dir / "endpoints.csv"
    evidence = _after_worker(
        identity,
        manifest,
        result,
        output_csv=output_csv,
        oracle_role=oracle,
        runtime=launcher.runtime_version() if hasattr(launcher, "runtime_version") else None,
    )
    return _finish(output_dir, evidence)


def _finish(output_dir: Path, evidence: Evidence) -> Evidence:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_evidence(output_dir, evidence)
    return evidence


def _recipe_matches(launcher: PodmanLauncher, manifest: dict) -> bool:
    image = manifest["image"]
    name = image["name"]
    labels = launcher.image_labels(name) if hasattr(launcher, "image_labels") else {}
    base_layer = launcher.image_base_layer(name) if hasattr(launcher, "image_base_layer") else None
    return (
        labels.get("org.biorepro.base_digest") == image.get("base_digest")
        and labels.get("org.biorepro.containerfile_sha256") == image.get("containerfile_sha256")
        and labels.get("org.biorepro.base_layer") == image.get("base_layer")
        and base_layer == image.get("base_layer")
    )


def _spec(manifest: dict, fixture: Path, output_dir: Path) -> WorkerSpec:
    limits = manifest["limits"]
    user = f"{os.getuid()}:{os.getgid()}"
    return WorkerSpec(
        image=manifest["image"]["name"],
        user=user,
        memory_mb=limits["memory_mb"],
        timeout_seconds=limits["timeout_seconds"],
        output_byte_limit=limits["max_output_bytes"],
        input_dir=fixture / "inputs",
        script_dir=fixture / "script",
        output_dir=output_dir,
        command=["Rscript", "--vanilla", "/script/analyze.R", "/inputs/groups.csv", "/output/endpoints.csv"],
        network=manifest["isolation"]["network"],
        read_only_inputs=manifest["isolation"]["read_only_inputs"],
        run_as_root=manifest["isolation"]["run_as_root"],
    )


def _after_worker(
    identity: dict,
    manifest: dict,
    result: WorkerResult,
    *,
    output_csv: Path,
    oracle_role: str,
    runtime: str | None,
) -> Evidence:
    stderr = result.stderr[-2000:]
    common = dict(
        runtime=runtime,
        r_version=manifest["image"].get("r_version"),
        worker_exit_code=result.exit_code,
        worker_stderr=stderr,
        worker_created=True,
        reference_digest_match=manifest.get("_reference_digest_match"),
    )
    timeout_seconds = manifest["limits"]["timeout_seconds"]
    hit_deadline = result.elapsed_seconds >= max(0, timeout_seconds - 0.5)
    if hit_deadline and result.exit_code in {124, 137, 255}:
        return Evidence(
            status="rejected",
            category="timeout",
            reason="worker_timeout",
            message=f"the worker exceeded timeout_seconds={timeout_seconds} and was stopped",
            schema_ok=False,
            output_csv=str(output_csv) if output_csv.is_file() else None,
            differences=[],
            **identity,
            **common,
        )
    if result.exit_code == 137 or _stderr_says_allocation(result.stderr):
        return Evidence(
            status="rejected",
            category="resource_limit",
            reason="memory",
            message=f"the worker hit the memory limit of {manifest['limits']['memory_mb']} MiB",
            schema_ok=False,
            output_csv=str(output_csv) if output_csv.is_file() else None,
            differences=[],
            **identity,
            **common,
        )
    if "file size limit" in result.stderr.lower() or result.exit_code == 153:
        return Evidence(
            status="rejected",
            category="resource_limit",
            reason="output_bytes",
            message=f"the worker hit the output size limit of {manifest['limits']['max_output_bytes']} bytes",
            schema_ok=False,
            output_csv=None,
            differences=[],
            **identity,
            **common,
        )
    if not output_csv.is_file():
        return Evidence(
            status="rejected",
            category="missing_output",
            reason="endpoints_csv",
            message="the worker finished without writing endpoints.csv",
            schema_ok=False,
            output_csv=None,
            differences=[],
            **identity,
            **common,
        )
    if result.exit_code != 0:
        return Evidence(
            status="rejected",
            category="worker_failed",
            reason="nonzero_exit",
            message=f"the worker exited {result.exit_code}",
            schema_ok=False,
            output_csv=str(output_csv),
            differences=[],
            **identity,
            **common,
        )
    oracle_path = _oracle_path(manifest, oracle_role)
    comparison = compare_files(
        output_csv,
        oracle_path,
        tolerances=manifest["tolerances"],
        max_bytes=manifest["limits"]["max_output_bytes"],
        max_rows=manifest["limits"]["max_rows"],
    )
    return _from_comparison(identity, comparison, output_csv=output_csv, **common)


def _stderr_says_allocation(stderr: str) -> bool:
    lowered = stderr.lower()
    return "cannot allocate" in lowered or "vector memory exhausted" in lowered


def _oracle_path(manifest: dict, role: str) -> Path:
    # The caller passes a role. The path is resolved by the run_fixture closure via manifest only.
    # compare_files needs an absolute path; run_fixture stores fixture on the manifest copy.
    root = Path(manifest["_fixture_root"])
    for entry in manifest["oracles"]:
        if entry.get("role") == role:
            return root / entry["path"]
    raise BioreproError("malformed_input", f"oracle role {role!r} is not declared")


def _read_manifest(fixture: Path) -> dict:
    manifest = json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))
    manifest["_fixture_root"] = str(fixture)
    image = manifest.get("image")
    if isinstance(image, dict) and "r_version" not in image:
        image["r_version"] = "4.3.3"
    return manifest


def _identity(manifest: dict | None) -> dict:
    if not manifest:
        return {
            "fixture_id": None,
            "estimand": None,
            "unit": None,
            "generation_seed": None,
            "rng_seed": None,
            "input_sha256": None,
            "entrypoint_sha256": None,
            "image_digest": None,
            "network": None,
        }
    estimand = manifest.get("estimand") or {}
    image = manifest.get("image") or {}
    inputs = manifest.get("inputs") or [{}]
    entry = manifest.get("entrypoint") or {}
    isolation = manifest.get("isolation") or {}
    return {
        "fixture_id": manifest.get("fixture_id"),
        "estimand": estimand.get("name"),
        "unit": estimand.get("unit"),
        "generation_seed": manifest.get("generation_seed"),
        "rng_seed": manifest.get("rng_seed"),
        "input_sha256": inputs[0].get("sha256") if inputs else None,
        "entrypoint_sha256": entry.get("sha256"),
        "image_digest": image.get("digest"),
        "network": isolation.get("network"),
    }


def _recheck_hashes(fixture: Path, manifest: dict) -> None:
    pairs = [(fixture / manifest["entrypoint"]["path"], manifest["entrypoint"]["sha256"], "entrypoint")]
    for entry in manifest["inputs"]:
        pairs.append((fixture / entry["path"], entry["sha256"], "input"))
    for path, expected, label in pairs:
        actual = sha256_file(path)
        if actual != expected:
            raise BioreproError(
                "review_rejected",
                f"{path.name} sha256 changed after review ({actual}). No worker was created.",
                reason=f"{label}_hash",
            )


def _from_validation(validation: ValidationReport, identity: dict) -> Evidence:
    return Evidence(
        status="rejected",
        category=validation.category,
        reason=validation.reason,
        message=validation.message,
        schema_ok=False,
        output_csv=None,
        differences=[],
        worker_created=False,
        **identity,
    )


def _rejected(identity: dict, *, category: str, reason: str, message: str) -> Evidence:
    return Evidence(
        status="rejected",
        category=category,
        reason=reason,
        message=message,
        schema_ok=False,
        output_csv=None,
        differences=[],
        worker_created=False,
        **identity,
    )


def _from_comparison(identity: dict, comparison: Comparison, *, output_csv: Path, **common) -> Evidence:
    status = "match" if comparison.category == "match" else "rejected"
    return Evidence(
        status=status,
        category=comparison.category,
        reason=comparison.reason,
        message=comparison.message,
        schema_ok=comparison.schema_ok,
        output_csv=str(output_csv),
        differences=[item.to_dict() for item in comparison.differences],
        **identity,
        **common,
    )


def _write_evidence(output_dir: Path, evidence: Evidence) -> None:
    payload = evidence.to_dict()
    (output_dir / "evidence.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "evidence.md").write_text(render_markdown(payload), encoding="utf-8")


def render_markdown(payload: dict) -> str:
    lines = [
        "# BioRepro evidence",
        "",
        f"- Status: {payload['status']}",
        f"- Category: {payload['category']}",
        f"- Fixture: {payload['fixture_id']}",
        f"- Estimand: {payload['estimand']} ({payload['unit']})",
        f"- Generation seed: {payload['generation_seed']}",
        f"- RNG seed: {payload['rng_seed']}",
        f"- Input SHA-256: {payload['input_sha256']}",
        f"- Script SHA-256: {payload['entrypoint_sha256']}",
        f"- Image digest: {payload['image_digest']}",
        f"- Reference digest matched this image: {payload['reference_digest_match']}",
        f"- Worker created: {payload['worker_created']}",
        f"- Network: {payload['network']}",
        f"- R version: {payload['r_version']}",
        f"- Runtime: {payload['runtime']}",
        f"- Schema matched: {payload['schema_ok']}",
        f"- Output: {payload['output_csv']}",
        "",
        payload["message"],
        "",
        payload["limitation"],
        "",
    ]
    differences = payload["differences"]
    if differences:
        lines.extend(
            [
                "| Endpoint | Column | Kind | Expected | Actual |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for item in differences:
            lines.append(
                f"| {item['endpoint_id']} | {item['column']} | {item['kind']} | {item['expected']} | {item['actual']} |"
            )
        lines.append("")
    else:
        lines.append("No cell differences.")
        lines.append("")
    return "\n".join(lines)


def exit_code_for(evidence: Evidence) -> int:
    if evidence.category is None:
        return EXIT_CODE["valid"]
    return EXIT_CODE[evidence.category]
