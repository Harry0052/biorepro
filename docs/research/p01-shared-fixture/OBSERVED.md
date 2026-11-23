# P01 shared-fixture probe

Access date: 2026-11-23.

Held constant across tools:

- Input: the CSVs in this directory (original synthetic rows, not a published extract).
- Expected artifact: zero cell differences on `observed_clean.csv`; the perturbed file changes only `walk_challenge` / `mean_value` from `6540.00` to `6540.25`.
- Declared absolute tolerance: `0.01` on `mean_value`. `observed_within_tol.csv` moves the same cell by `+0.005` and must count as agreement under that tolerance.
- `observed_missing.csv` has an empty `n_groups` for `control`. `observed_zero.csv` has `0` in that cell. Those two states are different.
- Acceptance metric: match the clean oracle, name the exact endpoint and column in the perturbed oracle, attach complete provenance, and perform zero script executions when review rejects the script hash.

## csv-diff 1.2 observed run

Package: [csv-diff 1.2](https://pypi.org/project/csv-diff/1.2/) (Apache-2.0). Source commit `26903b74eefcd65be761810f51b0e55c033bde66` on 2024-09-06. Installed with `python3 -m pip install --target /tmp/p01-libs csv-diff==1.2` and invoked through Click's `CliRunner` on `csv_diff.cli:cli`.

Clean (`expected.csv` vs `observed_clean.csv`, `--key endpoint_id --json`):

```json
{"added": [], "removed": [], "changed": [], "columns_added": [], "columns_removed": []}
```

Perturbed (`+0.25`):

```json
{"changed": [{"key": "walk_challenge", "changes": {"mean_value": ["6540.00", "6540.25"]}}]}
```

Within tolerance (`+0.005`):

```json
{"changed": [{"key": "walk_challenge", "changes": {"mean_value": ["6540.00", "6540.005"]}}]}
```

Missing versus zero:

```json
{"changed": [{"key": "control", "changes": {"n_groups": ["", "0"]}}]}
```

Every invocation exited 0, including the disagreements. The CLI callback source contains no `hash`, `script`, or `tolerance` parameter. The tool compares two text tables. It does not rerun an analysis, so a rejected script hash is outside its interface.

## Tools recorded from source or documentation

Those outcomes are in `docs/overlap.md`. This directory is the shared input for the one tool that was executed.
