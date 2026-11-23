# biorepro

Local harness for one synthetic aggregate statistical table. A reviewer checks the manifest, reruns the allowlisted R script in a non-root worker with networking disabled, and reads an evidence packet of endpoint-cell differences.

Numerical agreement is outcome agreement under the recorded tolerances. It is not a clinical validation.

There is no separate hardware, GPU, or real-patient demo. The only supported demo is the synthetic office-wellness fixture in this repository.

## Supported platform

- Linux x86_64. Development and the commands below were run on Ubuntu 24.04 with CPython 3.12.3.
- Python 3.11 or newer for `validate` and `compare`.
- Rootless Podman 4.9 or newer for `run` and `demo`. Podman 4.9.3 was used here.
- The worker image is built on the machine from `deploy/Containerfile`. Analysis runs do not use the network.

R 4.3.3 enters the image from Ubuntu `r-base-core` (GPL) at build time. R is not vendored in this MIT tree. pytest 9.2.0 (MIT) is a test-only dependency, pinned in `requirements-dev.txt` and `pyproject.toml`.

## Install

From a clean checkout:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
scripts/build_worker.sh
.venv/bin/python -m compileall -q biorepro tests
.venv/bin/pytest
```

`scripts/build_worker.sh` prints the built digest and the reference digest. Apt's installed layer is not bit-stable, so those digests may differ. The script exits 0 when the base layer, the base-digest label, and the Containerfile hash label match `fixtures/office-wellness/manifest.json`. Any other image is refused before a worker is created.

## Demo

```bash
.venv/bin/biorepro demo --output outputs/demo
```

Expected result: exit code `0` and `outputs/demo/demo.json` with `"status": "pass"`.

That means all three of these happened:

- the clean rerun matches `fixtures/office-wellness/oracle/expected.csv`
- the perturbed oracle reports only endpoint `walk_challenge`, column `mean_steps` (6540.00 versus 6540.25, absolute tolerance 0.01)
- `fixtures/invalid-missing-column` is rejected and no worker is created

Read these reports:

- `outputs/demo/demo.md`
- `outputs/demo/clean/evidence.md` and `outputs/demo/clean/evidence.json`
- `outputs/demo/clean/endpoints.csv`
- `outputs/demo/perturbed-comparison.md`

## Other commands

JSON is written to stdout. A one-line status is written to stderr.

```bash
.venv/bin/biorepro --help
.venv/bin/biorepro validate fixtures/office-wellness
.venv/bin/biorepro validate fixtures/invalid-missing-column
.venv/bin/biorepro run fixtures/office-wellness --output outputs/office-wellness
.venv/bin/biorepro compare outputs/office-wellness/endpoints.csv \
  fixtures/office-wellness/oracle/perturbed.csv \
  --manifest fixtures/office-wellness/manifest.json
```

`validate` on the office-wellness fixture exits 0. `validate` on the missing-column fixture exits 4 (`schema_mismatch`) and names `n_people`. `run` against the clean oracle exits 0. `compare` against the perturbed oracle exits 1 (`numeric_disagreement`) and does not start a worker.

## Fixture and data terms

`fixtures/office-wellness` is an original synthetic methods example: six workplace groups and a pooled mean of daily steps, in steps per person per day. Generation seed `20261123`. RNG seed is null because the estimand does not use randomness. DOI is null because this is not a published dataset. There are no personal data and no patient records.

The hand calculation is `fixtures/office-wellness/ORACLE.md`. The manifest records input and script SHA-256 hashes, the R entry point, the reference image digest, the base image digest, the Containerfile hash, the output columns, the primary key `endpoint_id`, and the `mean_steps` tolerance (absolute `0.01`, relative `0`).

Fixture data and code are released under the MIT license in `LICENSE`. Do not add patient-level records, credentials, or third-party extracts without recording the DOI, the access conditions, and the redistribution rights separately.

## Notices

- Code and the synthetic fixture: MIT, `LICENSE`.
- Worker base image: `docker.io/library/ubuntu` digest `sha256:9c7f200c07e3d4a03e7249d2c16bf66a51120fb876aa2242cf31451412543289`, under Ubuntu's terms. It is pulled when the image is built and is not stored in git.
- R inside that image: GPL, package `r-base-core=4.3.3-2build2`. Source is provided by Ubuntu. It is not copied into this repository.
- pytest: MIT, test-only.

## Project documents

- `CHANGELOG.md` — version history
- `CONTRIBUTING.md` — how to test a change
- `SECURITY.md` — how to report a vulnerability
- `docs/validation.md` — acceptance evidence, timing, and residual limits
- `docs/project-contract.md` — the user task and the acceptance case
- `docs/overlap.md` — why this repository is separate from existing table-diff and replication tools
