# Grokbot progress

## Status index

| Phase | Status | Recorded |
| --- | --- | --- |
| P01 | PASS | 2026-11-23 |
| P02 | PASS | 2026-11-23 |
| P03 | pending | |
| P04 | pending | |
| P05 | pending | |
| P06 | pending | |
| P07 | pending | |

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
