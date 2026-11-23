import json
from pathlib import Path

import pytest

from biorepro.errors import BioreproError
from biorepro.runner import WorkerResult, podman_argv, run_fixture
from tests.test_validate import VALID, _copy_valid, _rewrite_manifest


class FakeLauncher:
    def __init__(self, image_id: str | None):
        self._image_id = image_id
        self.inspected = 0
        self.specs = []

    def image_id(self, name: str) -> str | None:
        self.inspected += 1
        return self._image_id

    def image_labels(self, name: str) -> dict:
        return {}

    def image_base_layer(self, name: str) -> str | None:
        return None

    def runtime_version(self) -> str:
        return "podman test"

    def run(self, spec):
        self.specs.append(spec)
        target = spec.output_dir / "endpoints.csv"
        target.write_text(Path(spec.script_dir).parents[0].joinpath("oracle", "expected.csv").read_text(encoding="utf-8"), encoding="utf-8")
        return WorkerResult(exit_code=0, stdout="", stderr="")


def test_changed_script_hash_does_not_create_a_worker(tmp_path):
    root = _copy_valid(tmp_path)
    _rewrite_manifest(root, lambda manifest: manifest["entrypoint"].__setitem__("sha256", "ab" * 32))
    launcher = FakeLauncher("sha256:" + "cd" * 32)
    evidence = run_fixture(root, tmp_path / "out", launcher=launcher)
    assert evidence.category == "review_rejected"
    assert evidence.reason == "entrypoint_hash"
    assert evidence.worker_created is False
    assert launcher.inspected == 0
    assert launcher.specs == []
    assert "No worker was created" in evidence.message


def test_network_enabled_manifest_does_not_create_a_worker(tmp_path):
    root = _copy_valid(tmp_path)
    _rewrite_manifest(root, lambda manifest: manifest["isolation"].__setitem__("network", "bridge"))
    launcher = FakeLauncher("sha256:" + "cd" * 32)
    evidence = run_fixture(root, tmp_path / "out", launcher=launcher)
    assert evidence.category == "review_rejected"
    assert evidence.reason == "network_enabled"
    assert launcher.specs == []


def test_digest_mismatch_does_not_create_a_worker(tmp_path):
    root = _copy_valid(tmp_path)
    allowlisted = "sha256:" + "11" * 32
    _rewrite_manifest(root, lambda manifest: manifest["image"].__setitem__("digest", allowlisted))
    launcher = FakeLauncher("sha256:" + "22" * 32)
    evidence = run_fixture(root, tmp_path / "out", launcher=launcher)
    assert evidence.category == "review_rejected"
    assert evidence.reason == "image_digest"
    assert launcher.inspected == 1
    assert launcher.specs == []


def test_matching_digest_runs_and_matches_the_clean_oracle(tmp_path):
    root = _copy_valid(tmp_path)
    digest = "sha256:" + "33" * 32
    _rewrite_manifest(root, lambda manifest: manifest["image"].__setitem__("digest", digest))
    launcher = FakeLauncher(digest)
    output = tmp_path / "out"
    evidence = run_fixture(root, output, launcher=launcher)
    assert evidence.category == "match"
    assert evidence.worker_created is True
    assert evidence.differences == []
    assert len(launcher.specs) == 1
    assert (output / "evidence.json").is_file()
    assert (output / "endpoints.csv").is_file()


def test_podman_argv_is_non_root_and_offline():
    from biorepro.runner import WorkerSpec

    spec = WorkerSpec(
        image="localhost/biorepro-office-wellness:0.1.0",
        user="1000:1000",
        memory_mb=256,
        timeout_seconds=30,
        output_byte_limit=1048576,
        input_dir=Path("/fixture/inputs"),
        script_dir=Path("/fixture/script"),
        output_dir=Path("/tmp/out"),
        command=["Rscript", "--vanilla", "/script/analyze.R", "/inputs/groups.csv", "/output/endpoints.csv"],
    )
    argv = podman_argv(spec)
    assert "--network=none" in argv
    assert "--userns=keep-id" in argv
    assert "--user" in argv
    assert "1000:1000" in argv
    assert "--read-only" in argv
    assert "--cap-drop=ALL" in argv
    assert "--timeout=30" in argv
    assert "--memory=256m" in argv
    joined = " ".join(argv)
    assert "bridge" not in joined
    assert "--network=host" not in joined


def test_podman_argv_refuses_root_and_network():
    from biorepro.errors import BioreproError
    from biorepro.runner import WorkerSpec

    spec = WorkerSpec(
        image="localhost/example:0",
        user="0:0",
        memory_mb=64,
        timeout_seconds=5,
        output_byte_limit=1000,
        input_dir=Path("/in"),
        script_dir=Path("/script"),
        output_dir=Path("/out"),
        command=["Rscript"],
        network="bridge",
        run_as_root=True,
    )
    with pytest.raises(BioreproError) as caught:
        podman_argv(spec)
    assert caught.value.category == "review_rejected"


def test_output_directory_inside_the_fixture_is_rejected(tmp_path):
    root = _copy_valid(tmp_path)
    with pytest.raises(BioreproError) as caught:
        run_fixture(root, root / "nested-output", launcher=FakeLauncher(None))
    assert caught.value.category == "review_rejected"
    assert caught.value.reason == "output_inside_fixture"


def test_unpinned_image_does_not_create_a_worker(tmp_path):
    root = _copy_valid(tmp_path)
    _rewrite_manifest(root, lambda manifest: manifest["image"].__setitem__("digest", None))
    launcher = FakeLauncher("sha256:" + "44" * 32)
    evidence = run_fixture(root, tmp_path / "out", launcher=launcher)
    assert evidence.reason == "image_unpinned"
    assert evidence.worker_created is False
    assert launcher.inspected == 0
    assert launcher.specs == []
