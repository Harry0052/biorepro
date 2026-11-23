# biorepro

Local harness for one synthetic aggregate statistical table. A reviewer checks the manifest, reruns the allowlisted R script in a non-root worker with networking disabled, and reads an evidence packet of endpoint-cell differences.

This tree currently ships the fixture contract and the validation entry point. The isolated rerun and comparison commands are added in later phases. Numerical agreement is outcome agreement under the recorded tolerances. It is not a clinical validation.

The bundled counts are original synthetic group totals for a workplace step-program methods example. There is no DOI, no personal data, and no upstream dataset. Fixture data and code are released under the MIT license in `LICENSE`.

## Prerequisites

- Python 3.11 or newer. Development used CPython 3.12.3.
- For tests: pytest 9.2.0, pinned in `requirements-dev.txt`.
- A full rerun, once that command exists, also needs rootless Podman and R 4.3 inside the worker image. Validation itself does not start a worker and does not use the network.

## Install and test

From a clean checkout:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

## Validate a fixture

Accept the synthetic office-wellness fixture:

```bash
.venv/bin/biorepro validate fixtures/office-wellness
```

Exit code `0`. Standard output is one JSON object. The human line is on standard error.

Reject the labeled invalid fixture. `inputs/groups.csv` omits `n_people`:

```bash
.venv/bin/biorepro validate fixtures/invalid-missing-column
```

Exit code `4` (`schema_mismatch`). The JSON `message` names the missing column.

`biorepro --help` lists the commands. `biorepro --version` prints the version.

## Fixture contract

`fixtures/office-wellness/manifest.json` records the fixture id, a null DOI, input and script SHA-256 hashes, the R entry point allowlist, a null image digest until the worker image is built, generation seed `20261123`, a null RNG seed, the pooled-mean estimand, the output columns, the primary key `endpoint_id`, and the `mean_steps` tolerance (absolute `0.01`, relative `0`).

The hand calculation is in `fixtures/office-wellness/ORACLE.md`. The clean table is `oracle/expected.csv`. `oracle/perturbed.csv` changes `walk_challenge` / `mean_steps` by `+0.25`.

Validation refuses symlinks, paths that leave the fixture directory, undeclared files, hash mismatches, root execution, writable-input policy, and any network setting other than `none`. Those refusals happen before a worker exists. Changed hashes use category `review_rejected`.
