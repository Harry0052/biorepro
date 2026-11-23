# Overlap review

Access date: 2026-11-23. Decision: **proceed**.

BioRepro is a local harness that reruns one reviewed, non-sensitive statistical script and reports endpoint-cell agreement under a declared tolerance, with hashes and isolation recorded in an evidence packet. The user is a biomedical methods reviewer working from released aggregate artifacts. The MVP uses original synthetic group-level data only. It excludes patient records, live experiments, and pathogen, virology, genome, assay, and biological-design workflows.

The acceptance case held constant in this review:

1. A clean rerun matches a frozen oracle (zero cell differences) and records provenance.
2. A perturbed oracle that changes `walk_challenge` / `mean_value` by `+0.25` is reported at that endpoint key and column under absolute tolerance `0.01`. A `+0.005` move of the same cell stays inside tolerance.
3. A script hash outside the allowlist produces zero executions of the analysis script.

## Search record

Queries run on 2026-11-23:

- `GitHub reproducible clinical statistics tables endpoint tolerance compare published aggregate outcomes`
- `GitHub aggregate public-health analysis reproducibility data provenance checksum table difference`
- `journal reproducibility verification expected outputs numeric tolerance medical statistics public data`
- Named starting points: replicateEverything, Code Ocean verification, and the boundary names TrialStress and CohortShift.

Closest credible results: csv-diff (executed), datacompy (documentation), clinCompare (CRAN/README), numcheck (README), dataCompareR (archived README), replicateEverything (source at a pinned commit), Code Ocean verification (documentation).

## Capability matrix

| Tool | Version inspected | License evidence | What the inspection showed | Acceptance case |
| --- | --- | --- | --- | --- |
| csv-diff | PyPI 1.2; commit `26903b74eefcd65be761810f51b0e55c033bde66` (2024-09-06) | Apache-2.0 | Observed run on the shared fixture. Exact string match is empty. The `+0.25` cell is named. The `+0.005` cell is also reported as a change. Empty versus `0` is the same change type. Exit code stays 0. No hash, script, or tolerance flag. | Unmet |
| datacompy | 1.2.0; commit `c441a430aacda530abf000ab5f33e6190891a2d6` (2026-11-21) | Apache-2.0 | Documentation only. CLI documents join keys, absolute and relative tolerances, and exit codes 0 / 1 / 2. It compares files that already exist. | Unmet |
| clinCompare | GitHub `01dbe741698fbccac12823628b1bdd98d34f7e56` (2026-02-20); CRAN 1.0.0 | DESCRIPTION: MIT + file LICENSE. GitHub SPDX: NOASSERTION. CRAN record [10.32614/cran.package.clincompare](https://doi.org/10.32614/cran.package.clincompare) | README and DESCRIPTION. Key matching, numeric tolerance, missing-value handling, optional CDISC checks. No rerun gate. | Unmet |
| dataCompareR | commit `0fc1a74ea9162693dbf999756738a27cb8ff4768` (2025-10-06); repository archived | Apache-2.0 in the LICENSE file. GitHub SPDX: NOASSERTION | README. Keyed frame compare with optional digit rounding. | Unmet |
| numcheck | 0.2.0; commit `c5803d25eb47698cccd825e80b3e9c155eb8363d` (2026-11-19) | MIT | README. Recomputes printed clinical-report figures from other figures in the same document. | Unmet. Different task |
| replicateEverything | 0.7.60; commit `f911873e6e8bd4a5cf1bd473e84726afb07d5e1e` (2026-10-21) | DESCRIPTION: MIT + file LICENSE. LICENSE file names copyright holder Vermon Washington, year 2026. GitHub SPDX: NOASSERTION | Source read, not executed. Registry client fetches study code and data. `check_glm_table_benchmark()` applies one absolute tolerance (default 0.001) to GLM coefficients and standard errors and names the model index and term. Study checks are loaded with `sys.source`. | Unmet |
| Code Ocean verification | Hosted page, no software version | Proprietary service. Public documentation | Documentation. Staff check that a capsule run saves outputs under `/results`, installs dependencies at image build, and keeps data in `/data`. The page states that this process does not check agreement with a published article. | Unmet |
| CohortShift | commit `c1fecd6a4f1744aac7d09fc94a252b3fd966d6fa` (2026-09-27) | MIT | README. Temporal classifier validation and drift audits. | Unmet. Different task |
| TrialStress | `Harry0052/trialstress`, README is the title only (pushed 2026-11-23) | No license file inspected beyond the empty-looking README | README fetch. No implementation to compare. | Unmet |

Primary URLs:

- csv-diff: https://github.com/simonw/csv-diff and https://pypi.org/project/csv-diff/1.2/
- datacompy: https://github.com/capitalone/datacompy and https://capitalone.github.io/datacompy/cli.html
- clinCompare: https://github.com/siddharthlokineni/clinCompare and https://cran.r-project.org/package=clinCompare
- dataCompareR: https://github.com/capitalone/dataCompareR
- numcheck: https://github.com/joonalorenz-commits/numcheck
- replicateEverything: https://github.com/replicate-anything/replicateEverything
- Code Ocean: https://docs.codeocean.com/osl-guide/publishing-on-code-ocean/the-verification-process/code-oceans-verification-process-for-computational-reproducibility-and-quality
- CohortShift: https://github.com/williamtbarker/cohortshift
- TrialStress: https://github.com/Harry0052/trialstress

Published methods that informed the tolerance rule, and that are papers rather than tools:

- A 2026 medRxiv linear-regression reproducibility study compares regenerated statistics with thresholds `0.50 × 10^(−d)` and `0.999 × 10^(−d)`: https://www.medrxiv.org/content/10.64898/2026.04.07.26350286v1
- An earlier re-executable neuroimaging note compares outputs at absolute tolerance `1e-6` and writes a CSV of differences: https://pmc.ncbi.nlm.nih.gov/articles/PMC5516225/

Dataset terms: this review used an original synthetic fixture. No published microdata, registry extract, or paper supplement was downloaded. Per-study licenses inside replicateEverything were not accepted and were not tested.

## Probe outcome

Observed run: csv-diff 1.2 on `docs/research/p01-shared-fixture/`. Full JSON is in `OBSERVED.md`.

- Clean tables produce an empty change list.
- The seeded `+0.25` cell is localized to key `walk_challenge` and column `mean_value`.
- The in-tolerance `+0.005` cell is localized the same way, so a declared absolute tolerance of `0.01` is not applied.
- A missing cell and a zero are both ordinary string changes.
- Disagreement and success share exit code 0.
- Provenance fields and a pre-execution hash gate are outside the command.

Documentation and source reads:

- datacompy 1.2.0 documents the tolerance and key behavior the comparator needs, and documents distinct exit codes for match, difference, and usage errors. It has no analysis script, image digest, or review gate. The package was not installed: the 1.2.0 release depends on pandas, polars, and numpy, which is more than this probe required. Null-versus-zero behavior was not executed.
- replicateEverything's GLM helper is the nearest published-table check. It is absolute-tolerance only, it expects fitted `glm` objects, and the package reaches it by retrieving and sourcing study code. R was not used to run that package. A live run would fetch remote study material, which this MVP excludes.
- clinCompare and dataCompareR were not executed. R is now present on the build machine (`Rscript` 4.3.3) for the later worker image; those packages were still left uninstalled so the probe would not pull CDISC-oriented or archived comparison libraries into the project.
- Code Ocean was not run. The service is paid. The documented verification result is "the capsule run completed and wrote files," which is a different claim from endpoint agreement.
- numcheck, CohortShift, and TrialStress address other jobs (internal report arithmetic, classifier drift, and an unimplemented title).

## What already matches

- Keyed row identity and a per-cell change list: csv-diff, observed.
- Absolute and relative numeric tolerances, plus match/difference/error exit codes: datacompy CLI documentation.
- A single absolute tolerance against published GLM coefficients: replicateEverything `check_glm_table_benchmark()`, source at the pinned commit.
- "Install dependencies when the environment is built, keep data beside the code, write concrete result files": Code Ocean checklist.
- Checksums on public-health release files showed up in adjacent projects (PHIG, DATASUS parquet provenance, healtharchive export manifests). Those projects seal datasets. They do not rerun a methods script.

## What the acceptance case still requires

A reviewer-facing packet that, for one allowlisted script and one synthetic aggregate table:

- refuses to create the worker when the script hash, the input hash, or the isolation settings fail review;
- runs that script as a non-root process with networking disabled, read-only inputs, a size-capped output directory, and a timeout;
- joins on the declared endpoint key;
- applies prespecified absolute and relative tolerances and keeps missing values distinct from zeros;
- names the endpoint and column for a real difference;
- records input hash, script hash, image digest, seed, package versions, and run status;
- uses different error categories for a missing endpoint, a duplicate key, a schema change, a timeout, a resource limit, a missing output, and a numeric disagreement.

No inspected tool covers that set. Extending datacompy would add a worker and a review gate to a file-comparison library. Extending replicateEverything would add a refusal to source study code to a registry whose purpose is to source study code. Those are separate products. This repository should stay a small harness and should keep its comparator in the Python standard library so a compare-only run does not download packages.

## Dependency provenance path

Viable on the evidence gathered here:

- Fixture: original synthetic group-level office-wellness counts, written in this repository, with a generation seed and a hand-calculated oracle. No DOI, because the table is not a published dataset. Fixture id is assigned here.
- Script: one R file written and reviewed in this repository, identified by SHA-256.
- Comparator: Python 3.12 standard library.
- Tests: pytest, pinned in P02, test-only.
- Worker: rootless Podman. On this machine, `podman info` reported rootless `true`, graph driver `overlay`, OCI runtime `crun`, Podman 4.9.3. `Rscript` 4.3.3 is installed from Ubuntu `r-base-core` 4.3.3-2build2. The image will be built locally and the manifest will pin the image digest that build produces. Analysis runs do not enable the network.
- `fuse-overlayfs` is unpacked and not configured: noninteractive `apt-get` stopped on the `fuse3` conffile prompt. Native overlay still initialized. Image build in P03 has to confirm a real container start. If that start fails, P03 records the exact missing package state.

## Remaining uncertainties

- datacompy's treatment of null versus zero was not observed.
- replicateEverything was not executed. The GLM helper's messages were read from `R/substantive_checks.R` at commit `f911873e`.
- GitHub's license API returns `NOASSERTION` for replicateEverything and clinCompare. The DESCRIPTION lines are the license evidence used here. Their source is not copied into this repository.
- Hosted CI image builds are a P06/P07 check.
- Podman printed: `"/"` is not a shared mount, which can drop mounts in rootless containers. P03 must show a successful isolated run on this host or record the block.

## Decision

Proceed. The MVP hypothesis is concrete: for one synthetic aggregate analysis, an evidence packet with allowlisted inputs and an endpoint-cell tolerance report gives a reviewer a check that current file-diff tools and registry rerunners do not package together. The fixture and the toolchain have a local provenance path. No existing workflow meets the acceptance case, so the work stays in this repository rather than a patch to csv-diff, datacompy, or replicateEverything.
