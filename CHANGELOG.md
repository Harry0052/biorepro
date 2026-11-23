# Changelog

## 0.1.0

First working release of the office-wellness reproduction harness.

- Manifest validation for the synthetic group-level fixture, including hashes, isolation policy, and schema checks.
- Typed endpoint comparison with absolute and relative tolerances. Missing values stay distinct from zeros.
- Rootless Podman rerun of the reviewed R script with networking disabled, a non-root user, read-only inputs, and timeout, memory, and output-size caps.
- `biorepro demo` writes a clean evidence packet, a perturbed-cell comparison, and the rejection of the missing-column fixture.
- Reference image digest `sha256:b2b0f3e7747a54ad426f7041c81decc7d82fe217ca335c19cf1def853f74cbd2` for the vetted build. A rebuild may differ in the apt layer; the base layer and Containerfile hash must still match.
