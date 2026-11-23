# Grokbot progress

## Status index

| Phase | Status | Recorded |
| --- | --- | --- |
| P01 | PASS | 2026-11-23 |
| P02 | PASS | 2026-11-23 |
| P03 | PASS | 2026-11-23 |
| P04 | PASS | 2026-11-23 |
| P05 | PASS | 2026-11-23 |
| P06 | PASS | 2026-11-23 |
| P07 | PASS | 2026-11-23 |

## P01 — Research overlap and confirm the MVP

**Phase and status:** P01 PASS

**Files changed:**

- `docs/overlap.md`
- `docs/project-contract.md`
- `docs/research/p01-shared-fixture/` (shared CSVs and `OBSERVED.md`)
- `docs/grokbot-progress.md`

**Commands and results:**

- GitHub repository metadata, commits, and DESCRIPTION/LICENSE files were read for replicateEverything `f911873e6e8bd4a5cf1bd473e84726afb07d5e1e` (0.7.60), datacompy `c441a430aacda530abf000ab5f33e6190891a2d6` (1.2.0), csv-diff `26903b74eefcd65be761810f51b0e55c033bde66`, clinCompare `01dbe741698fbccac12823628b1bdd98d34f7e56` (CRAN 1.0.0), numcheck `c5803d25eb47698cccd825e80b3e9c155eb8363d` (0.2.0), dataCompareR `0fc1a74ea9162693dbf999756738a27cb8ff4768`, and CohortShift `c1fecd6a4f1744aac7d09fc94a252b3fd966d6fa`. TrialStress README is the title only.
- `python3 -m pip install --target /tmp/p01-libs csv-diff==1.2` succeeded. Click `CliRunner` on the shared fixture: clean change list empty; `+0.25` and `+0.005` both reported as `walk_challenge` / `mean_value`; empty versus `0` reported as a string change; every exit code 0. CLI callback source has no hash, script, or tolerance parameter.
- Code Ocean verification page and the medRxiv / PMC tolerance notes were read as documentation. Code Ocean was not executed (paid service).
- `Rscript` was absent at probe time. `sudo apt-get install` later installed `r-base-core` 4.3.3-2build2 and Podman 4.9.3. `fuse3` / `fuse-overlayfs` stayed unconfigured because of a conffile prompt. `podman info` still reported rootless `true`, graph driver `overlay`, runtime `crun`.
- replicateEverything, clinCompare, dataCompareR, and datacompy were not executed. Reasons are in `docs/overlap.md`.

**Artifact paths:**

- `docs/overlap.md`
- `docs/project-contract.md`
- `docs/research/p01-shared-fixture/OBSERVED.md`

**Open issues:**

- datacompy null-versus-zero behavior was not observed.
- Podman warned that `/` is not a shared mount. P03 must show a real isolated run or record the block.
- `fuse-overlayfs` is not configured. Native overlay initialized.

**Next phase:** P02

**Decision:** proceed. The acceptance case is unmet by the inspected tools. The synthetic fixture and the local toolchain have a provenance path. Build the harness in this repository.

## P02 — Create the repository and data contracts

**Phase and status:** P02 PASS

**Files changed:**

- `README.md`
- `pyproject.toml`
- `requirements-dev.txt`
- `.gitignore`
- `biorepro/` (`cli.py`, `validate.py`, `tables.py`, `errors.py`, `hashutil.py`)
- `fixtures/office-wellness/` (manifest, group totals, reviewed R script, clean oracle, perturbed oracle, hand calculation)
- `fixtures/invalid-missing-column/`
- `tests/test_validate.py`
- `docs/grokbot-progress.md`

**Commands and results:**

- `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"` installed the package with pytest 9.2.0.
- `.venv/bin/pytest -q` → `14 passed`.
- `.venv/bin/biorepro validate fixtures/office-wellness` → exit 0, status `valid`, message `fixture office-wellness accepted`.
- `.venv/bin/biorepro validate fixtures/invalid-missing-column` → exit 4, category `schema_mismatch`, message `groups.csv schema: missing n_people`.
- A direct `Rscript --vanilla` smoke of `script/analyze.R` wrote means `5988.25`, `6120.50`, and `6540.00`, matching `ORACLE.md`. That smoke is not the isolated worker; P03 adds the worker.

**Artifact paths:**

- `fixtures/office-wellness/manifest.json`
- `fixtures/office-wellness/oracle/expected.csv`
- `fixtures/office-wellness/oracle/perturbed.csv`
- `fixtures/office-wellness/ORACLE.md`
- `fixtures/invalid-missing-column/manifest.json`

**Open issues:**

- `image.digest` is null. `validate` accepts the fixture and records the digest as unpinned. `run` must reject an unpinned digest before creating a worker.
- Podman warned that `/` is not a shared mount. P03 has to show a real isolated run or record the block.
- `fuse-overlayfs` is unpacked and not configured. Podman is using the native overlay driver.

**Next phase:** P03

## P03 — Build the working core

**Phase and status:** P03 PASS

**Files changed:**

- `biorepro/compare.py`, `biorepro/runner.py`, `biorepro/cli.py`, `biorepro/validate.py`
- `deploy/Containerfile`
- `scripts/build_worker.sh`
- `fixtures/office-wellness/manifest.json` and `fixtures/invalid-missing-column/manifest.json` (image digest and recipe pins)
- `tests/test_compare.py`, `tests/test_runner_gates.py`, `tests/test_run_worker.py`
- `README.md`
- `docs/grokbot-progress.md`

**Commands and results:**

- Worker image built with `podman build --timestamp 1795392000 --layers=false --build-arg CONTAINERFILE_SHA256=4fc53668f1cc8ab3d26ca156efdb29534f95f8740e07281eae1ed2a3c2f35fe4 -t localhost/biorepro-office-wellness:0.1.0 -f deploy/Containerfile deploy`. Reference digest `sha256:3a396efd0e2bff36135e5d943a7510a9910d94358faa05871c37f793d8136cb9`. Base layer `sha256:369ede38a92da8cd72a76f15f37e496def401830f3c8b7d39c0c7695682a51ce`. A second build of the same Containerfile produced a different apt-layer digest (`sha256:75c15f6a7eee5b3a4fc1ca33fcdc4bb27129e9643915d8fdba90d736068e0f69` before the label was added); config, history, and the Ubuntu base layer stayed the same.
- `.venv/bin/pytest -q` → `35 passed` in 4.96s. That includes two clean isolated reruns, the perturbed-cell check, hash and network refusals before any worker, timeout, missing output, and the 32 MiB memory limit.
- `.venv/bin/biorepro run fixtures/office-wellness --output outputs/office-wellness` → exit 0, category `match`, `reference_digest_match` true, worker created, network none.
- `.venv/bin/biorepro run fixtures/office-wellness --oracle perturbed --output outputs/office-wellness-perturbed` → exit 1, category `numeric_disagreement`, the only cell is `walk_challenge` / `mean_steps` with absolute difference `0.25`.

**Artifact paths:**

- `outputs/office-wellness/endpoints.csv`
- `outputs/office-wellness/evidence.json`
- `outputs/office-wellness/evidence.md`
- `outputs/office-wellness-perturbed/evidence.json`
- `deploy/Containerfile`

**Open issues:**

- Apt layer digests change across rebuilds. The run gate accepts an image when the reference digest matches, or when the base layer, base digest label, and Containerfile hash label match. The evidence records `reference_digest_match`.
- Podman still warns that `/` is not a shared mount. The isolated rerun completed and wrote the table.
- `fuse-overlayfs` remains unconfigured. The native overlay driver was used.

**Next phase:** P04

## P04 — Ship the user workflow and reports

**Phase and status:** P04 PASS

**Files changed:**

- `biorepro/demo.py`, `biorepro/cli.py`, `biorepro/compare.py`, `biorepro/runner.py`
- `tests/test_compare.py`, `tests/test_run_worker.py`
- `README.md`
- `docs/grokbot-progress.md`

**Commands and results:**

- `.venv/bin/pytest -q` → `36 passed`.
- `.venv/bin/biorepro demo --output outputs/demo` → exit 0, status `pass`. Clean category `match`. Perturbed category `numeric_disagreement` on `walk_challenge` / `mean_steps`. Invalid fixture category `schema_mismatch` with `worker_created` false.
- `.venv/bin/biorepro run fixtures/invalid-missing-column --output outputs/invalid` → exit 4. Recovery text names `inputs/groups.csv` and says no worker is created.
- `.venv/bin/biorepro --help` lists `validate`, `run`, `demo`, and `compare`. JSON is on stdout and the short status line is on stderr.

**Artifact paths:**

- `outputs/demo/demo.md`
- `outputs/demo/demo.json`
- `outputs/demo/clean/endpoints.csv`
- `outputs/demo/clean/evidence.json`
- `outputs/demo/clean/evidence.md`
- `outputs/demo/perturbed-comparison.md`
- `outputs/invalid/evidence.md`

**Open issues:**

- Apt layer digests still drift across rebuilds. The evidence field `reference_digest_match` records whether this run used the reference digest.
- Podman warns that `/` is not a shared mount. The demo run still wrote the table.

**Next phase:** P05

## P05 — Verify correctness, security, and performance

**Phase and status:** P05 PASS

**Files changed:**

- `docs/validation.md`
- `tests/test_runner_gates.py` (output directory must stay outside the fixture)
- `docs/grokbot-progress.md`

**Commands and results:**

- `python3 -m compileall -q biorepro tests` → ok.
- `.venv/bin/pytest -q` → `37 passed` in 4.15 seconds.
- Fresh demo `.venv/bin/biorepro demo --fixture fixtures/office-wellness --invalid fixtures/invalid-missing-column --output /tmp/fresh-demo` → exit 0, status `pass`, elapsed 0.35 seconds. Budget is 15 seconds.
- Fixture tables and script total 2314 bytes.
- OSV.dev query for pytest 9.2.0 returned zero vulnerabilities. No third-party Python runtime dependency.
- Secret-pattern search of tracked files found no matches.
- Host: Linux 6.12.113+ x86_64, CPython 3.12.3, Podman 4.9.3, R 4.3.3.

**Artifact paths:**

- `docs/validation.md`
- `/tmp/fresh-demo/demo.json` (fresh-state demo, outside the git tree)

**Open issues:**

- Apt layer digests drift across rebuilds. Recipe labels are the fallback gate and are described in `docs/validation.md`.
- The Ubuntu package set inside the worker image was not scanned against a CVE feed beyond the version pins.
- Podman warns that `/` is not a shared mount. The fresh demo still passed.

**Next phase:** P06

## P06 — Prepare a reproducible open-source release

**Phase and status:** P06 PASS

**Files changed:**

- `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `.gitattributes`
- `.github/workflows/ci.yml`
- `docs/validation.md` (reference digest updated after LF normalization)
- Text files normalized from CRLF to LF. Fixture SHA-256 values and the worker reference digest were recomputed.
- `docs/grokbot-progress.md`

**Commands and results:**

- Line-ending normalization, then a worker rebuild. Reference digest `sha256:b2b0f3e7747a54ad426f7041c81decc7d82fe217ca335c19cf1def853f74cbd2`. Containerfile SHA-256 `652fdef7c4c1b2c016faf1fbead31b26319be5d054ea13a38f7aaddd117cd5a2`.
- `.venv/bin/pytest -q` → `37 passed`. `biorepro demo` → exit 0, status `pass`.
- Clean copy at `/tmp/biorepro-clean` followed the README: venv, `pip install -e ".[dev]"`, `scripts/build_worker.sh`, `compileall`, `pytest`, `biorepro demo`. The rebuild digest was `sha256:7b252c70df1e482ef26bc5c029b883844c7cac0d4f029a7f5c251a2813b989c1` and the script reported that the recipe labels match. pytest → `37 passed` in 5.34 seconds. Demo status `pass` (`/tmp/clean-room.log` is `CLEAN_OK`).
- Workflow permissions are `contents: read` and `actions: write` (artifact upload). Actions are pinned to commit SHAs. The workflow does not use secrets.

**Artifact paths:**

- `/tmp/biorepro-clean/outputs/demo/demo.json`
- `.github/workflows/ci.yml`
- `SECURITY.md`

**Open issues:**

- Hosted CI has not run yet. P07 watches it.
- Apt layer digests differ across rebuilds. The clean-room demo ran on a non-reference digest whose recipe labels matched.

**Next phase:** P07

## P07 — Publish and verify on GitHub

**Phase and status:** P07 PASS

**Files changed:**

- `docs/grokbot-progress.md` (this record). The release tag points at the parent commit, which is the revision CI and the archive demo already tested.

**Commands and results:**

- Destination checked: `Harry0052/biorepro`, public, license SPDX `MIT`. Remote is `origin` for that repository. History on `main` was not rewritten. The branch was not merged.
- Pull request: https://github.com/Harry0052/biorepro/pull/1
- CI on commit `65ec47ed4c8a6e0b69bd551e3585859488dd09f6`:
  - Push run https://github.com/Harry0052/biorepro/actions/runs/45115749411 — `demo` passed in 1m45s (install, pytest, fixture demo, artifact upload).
  - Pull request run https://github.com/Harry0052/biorepro/actions/runs/45115935141 — `demo` passed in 1m30s.
  - Annotation only: the pinned actions still target Node.js 20 and GitHub forced Node.js 24. The jobs succeeded.
- Tag `v0.1.0` points at `65ec47ed4c8a6e0b69bd551e3585859488dd09f6` and was pushed. There is no separate release binary; the CI artifact is the demo evidence packet.
- `git archive v0.1.0` into `/tmp/biorepro-tag`, then the README sequence: venv, editable install, `scripts/build_worker.sh`, pytest, `biorepro demo --output outputs/demo`. pytest → `37 passed`. Demo status `pass`. The rebuilt image digest differed from the reference digest and the recipe labels matched, which is the documented rebuild rule.

**Artifact paths:**

- https://github.com/Harry0052/biorepro/releases/tag/v0.1.0 (annotated tag; no extra binary)
- `/tmp/biorepro-tag/outputs/demo/demo.json`
- CI artifact `demo-evidence` on the runs above

**Open issues:**

- `main` is unchanged until the owner merges pull request 1.
- Apt layer digests still differ across rebuilds. Recipe labels are the acceptance check in that case.
- Actions Node.js 20 deprecation is a warning, not a failed check.

**Next phase:** none. This is the last phase in the playbook.
