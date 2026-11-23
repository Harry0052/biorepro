# Validation

Recorded 2026-11-23 on the build host after P04. The checks use the synthetic `office-wellness` fixture. They are not a clinical validation. A match means the recomputed cells agree with the selected oracle under the declared tolerances and the recorded inputs.

## Environment

| Item | Observed |
| --- | --- |
| OS | Linux 6.12.113+ x86_64 |
| Python | CPython 3.12.3 |
| Podman | 4.9.3, rootless, graph driver overlay, runtime crun |
| R in the worker image | 4.3.3, Ubuntu package `r-base-core` 4.3.3-2build2 |
| pytest | 9.2.0 |
| Worker reference digest | `sha256:b2b0f3e7747a54ad426f7041c81decc7d82fe217ca335c19cf1def853f74cbd2` |
| Base layer | `sha256:369ede38a92da8cd72a76f15f37e496def401830f3c8b7d39c0c7695682a51ce` |

`python3 -m compileall -q biorepro tests` completed with status ok. The application imports only the Python standard library. pytest is a test dependency.

## Fixture size and performance budget

| Artifact | Bytes |
| --- | --- |
| `inputs/groups.csv` | 185 |
| `script/analyze.R` | 1563 |
| `oracle/expected.csv` | 283 |
| `oracle/perturbed.csv` | 283 |

Budget for the supported demo, after the worker image is already present: **15 seconds**. The work is six group rows and one pooled mean per arm. Image startup dominates the time. A hang or a network fetch would miss this budget.

Observed fresh run:

```text
.venv/bin/biorepro demo --fixture fixtures/office-wellness \
  --invalid fixtures/invalid-missing-column \
  --output /tmp/fresh-demo
```

Exit 0, status `pass`, elapsed **0.35 seconds**. The budget passes.

After the repository text was normalized to LF line endings, the fixture hashes and the worker image were rebuilt. `.venv/bin/pytest -q` again reported 37 passed, and `biorepro demo` again exited 0 with status `pass`. The reference digest above is that LF build.

## Acceptance evidence

`.venv/bin/pytest -q` → **37 passed** in 4.15 seconds. The same assertions are mapped below.

| Acceptance assertion | Evidence |
| --- | --- |
| Two clean reruns are deterministic and match the frozen oracle | `test_clean_rerun_is_deterministic`, fresh demo status `pass` |
| Perturbed oracle names `walk_challenge` / `mean_steps` and no other cell; absolute difference `0.25` with tolerance `0.01` | `test_perturbed_oracle_names_the_seeded_cell`, `test_seeded_quarter_step_is_named`, demo `perturbed_category=numeric_disagreement` |
| Provenance on both: input hash, script hash, image digest, seed, network, R version | Evidence JSON fields written by `run_fixture`; demo trace block |
| Tolerance boundary is inclusive at `0.01` and fails at `0.02` | `test_tolerance_boundary_is_inclusive` |
| Relative tolerance uses `abs + rel * abs(expected)` | `test_relative_tolerance_uses_the_declared_formula` |
| Missing values are distinct from zeros | `test_missing_value_is_distinct_from_zero` |
| Missing endpoint, duplicate key, and schema change are different categories | `test_missing_and_extra_endpoints_have_their_own_category`, `test_duplicate_endpoint_key`, `test_schema_change` |
| Changed script hash, network enabled, unpinned digest, and digest mismatch do not create a worker | `test_changed_script_hash_does_not_create_a_worker`, `test_network_enabled_manifest_does_not_create_a_worker`, `test_unpinned_image_does_not_create_a_worker`, `test_digest_mismatch_does_not_create_a_worker` |
| Timeout, memory limit, and missing output are not numeric disagreements | `test_timeout_is_not_a_numeric_disagreement`, `test_memory_limit_is_not_a_numeric_disagreement`, `test_missing_output_is_not_a_numeric_disagreement` |
| Malformed sample is rejected with a recovery step and no worker | `test_demo_flow_traces_the_seeded_cell`, `biorepro run fixtures/invalid-missing-column` exit 4 |
| Output directory inside the fixture is rejected | `test_output_directory_inside_the_fixture_is_rejected` |
| Symlink and path escape are rejected | `test_symlink_is_rejected`, `test_path_escape_is_rejected` |

The worker argv is built in `podman_argv` and checked by `test_podman_argv_is_non_root_and_offline`: `--network=none`, `--userns=keep-id`, a non-zero uid, `--read-only`, `--cap-drop=ALL`, `--timeout`, and `--memory`. Root or any other network raises `review_rejected` before `subprocess` runs.

## Trust boundaries

- Fixture files are untrusted until the manifest hashes, the relative-path check, and the symlink check pass. Those checks finish before `PodmanLauncher.run`.
- The analysis command is a fixed argv: `Rscript --vanilla /script/analyze.R /inputs/groups.csv /output/endpoints.csv`. It is not a shell string and it is not taken from the CSV.
- The input and script mounts are read-only. The output mount is the requested directory, which must sit outside the fixture. File size is capped with `RLIMIT_FSIZE`. Memory and swap are capped together. The wall clock is capped with `podman run --timeout`.
- A failed image lookup is `isolation_blocked` and does not call `podman run`.
- Compare-only mode does not start a worker.
- Evidence text states the limitation: agreement under the recorded tolerances is not a clinical validation.

## Dependencies, licenses, and advisories

| Component | Role | License / terms |
| --- | --- | --- |
| This repository | CLI, fixture, tests | MIT (`LICENSE`) |
| Fixture counts and script | Original synthetic methods example | Released with the repository. No upstream dataset and no DOI |
| pytest 9.2.0 | Tests only | MIT, from the installed package metadata |
| Ubuntu 24.04 base image | Worker base, digest-pinned | Ubuntu archive terms. Not copied into the git tree |
| `r-base-core` 4.3.3 | Inside the worker image only | GPL. Not vendored in this MIT tree. Installed when the image is built |

OSV.dev query for PyPI `pytest` 9.2.0 on 2026-11-23 returned **zero** vulnerabilities. There is no third-party Python runtime package to scan. The worker image's full Ubuntu package set was not scanned against a CVE feed in this session; the image is pinned to the Ubuntu digest and `r-base-core=4.3.3-2build2` recorded in `deploy/Containerfile`.

A tracked-file search for typical secret patterns (`AKIA`, private-key blocks, `x-access-token`, `api_key`, `password=`) found no matches.

## Residual limitations

- Rebuilding `deploy/Containerfile` can change the apt layer digest even with `--timestamp`. The reference digest is the build that this file records. A later image is allowed only when its base layer, base-digest label, and Containerfile hash label match the manifest. `reference_digest_match` in the evidence is false in that case. An image that forges those labels and uses the same Ubuntu base layer would pass the recipe gate. The script hash gate still runs first.
- Podman warns that `/` is not a shared mount. The demo still wrote `endpoints.csv`.
- `fuse-overlayfs` is unpacked and not configured. Podman used the native overlay driver.
- The worker image package set has not had a separate CVE review beyond the version pins above.
