# Project contract

Status: accepted for implementation after the P01 proceed decision on 2026-11-23.

## User and task

A biomedical methods reviewer, or a journal reviewer, checks one published-style statistical table using artifacts that were explicitly released for that check.

The shipped task is local:

1. Load the bundled synthetic office-wellness fixture (group-level step totals, no people-level rows).
2. Review the manifest: fixture id, input hashes, the allowlisted R entry point and its hash, the worker image digest, the generation seed, the estimand, the output schema, the primary key, and the tolerances.
3. Run that entry point in a non-root worker with networking disabled.
4. Read an evidence packet that states match, or names the endpoint key and column that disagree, and that records hashes, the image digest, the seed, and the run status.

Numerical agreement means outcome agreement under the recorded assumptions and tolerances. It is not a clinical validation.

## MVP boundary

- One synthetic public-health methods example. Estimand: pooled mean daily steps per arm, `sum(steps_sum) / sum(n_people)`, in steps per person per day.
- Original data, original script, hand-calculated oracle, and one perturbed oracle. No patient records and no download during a run.
- Python CLI for review, comparison, and the evidence packet. One reviewed R script inside the worker.
- The table comparator runs without a container. The rerun path requires the vetted image.
- Excluded: pathogen, virology, genome or sequence, assay, and biological-design workflows; live or wet-lab steps; arbitrary remote packages; executable inputs taken from papers at run time.

TrialStress (trial-assumption simulation) and CohortShift (temporal classifier drift) are neighboring ideas. Their public repositories do not implement this acceptance case. TrialStress currently has a title-only README. CohortShift (MIT, commit `c1fecd6a4f1744aac7d09fc94a252b3fd966d6fa`) evaluates classifiers.

## Minimum dependencies

| Dependency | Role | Pin |
| --- | --- | --- |
| Python 3.12 standard library | CLI, manifest validation, typed comparison, evidence packet | Developed on CPython 3.12.3 |
| pytest | Tests only | Exact pin recorded in P02 |
| R 4.3 inside the worker | Reviewed analysis script | Ubuntu `r-base-core` 4.3.3-2build2 on the build host |
| Podman, rootless | Worker runtime | 4.9.3 observed locally |

No paid service. No API keys. No credentials in the tree. Compare-only use needs Python and the fixture. A full rerun needs Podman and the image described by the manifest.

## Measurable acceptance case

Fixture id `office-wellness`, generation seed recorded in the manifest, primary key `endpoint_id`, absolute tolerance `0.01` and relative tolerance `0` on `mean_steps`.

The case passes when all three statements are observed:

1. Two clean reruns write identical tables, the comparison lists zero cell differences, and both evidence packets include the input hash, the script hash, the image digest, the seed, and status `match`.
2. Comparing the clean output with the perturbed oracle, whose `walk_challenge` mean is `0.25` higher, reports that endpoint key and the column `mean_steps`, and reports no other cell.
3. Replacing the script hash in the review set stops the run with status `review_rejected` before any worker is created. The analysis script's process is not started.

Supporting checks that ship with the same case: in-tolerance boundaries, missing values distinct from zeros, and separate categories for a missing endpoint, a duplicate key, a schema change, a timeout, a resource limit, and a missing output.

## Out of scope for the MVP

- A second study, a paper PDF importer, or a registry client.
- CDISC, SDTM, or ADaM validation.
- Claiming that a match confirms the scientific conclusion of a clinical study.
