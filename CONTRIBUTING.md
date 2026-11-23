# Contributing

Issues and pull requests are welcome. Keep changes small and describe the behavior they affect.

## Local check

On Linux with rootless Podman:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
scripts/build_worker.sh
.venv/bin/python -m compileall -q biorepro tests
.venv/bin/pytest
.venv/bin/biorepro demo --output outputs/demo
```

`outputs/demo/demo.json` should report `"status": "pass"`.

## Fixture rules

- The shipped example stays synthetic and aggregate. Do not add patient-level rows, identifiers, or credentials.
- A new fixture needs a manifest, SHA-256 hashes, an allowlisted entry point, and an oracle a reviewer can recompute.
- If you change `deploy/Containerfile` or the analysis script, update the manifest hashes in the same change and say so in the pull request.
- Numerical agreement is agreement with the oracle under the declared tolerance. Do not describe it as clinical validation.

## Licenses

This repository is MIT. Do not vendor the GPL R packages or the Ubuntu root filesystem into git. The worker image installs them at build time.
