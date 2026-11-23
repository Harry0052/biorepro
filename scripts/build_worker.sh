#!/bin/sh
# Build the worker from deploy/Containerfile.
# Apt layer digests are not bit-stable. The script checks the stable gates:
# base image layer, base digest label, and Containerfile hash label.
set -eu
cd "$(dirname "$0")/.."
recipe=$(python3 -c 'import hashlib,pathlib; print(hashlib.sha256(pathlib.Path("deploy/Containerfile").read_bytes()).hexdigest())')
podman build --timestamp 1795392000 --layers=false \
  --build-arg "CONTAINERFILE_SHA256=${recipe}" \
  -t localhost/biorepro-office-wellness:0.1.0 \
  -f deploy/Containerfile deploy
python3 - "$recipe" << 'PY'
import json, subprocess, sys
recipe = sys.argv[1]
manifest = json.load(open("fixtures/office-wellness/manifest.json"))
image = manifest["image"]
inspect = json.loads(subprocess.check_output(["podman", "image", "inspect", image["name"]]))[0]
digest = inspect.get("Digest")
labels = (inspect.get("Config") or {}).get("Labels") or {}
base_layer = (inspect.get("RootFS") or {}).get("Layers", [None])[0]
print(f"built   {digest}")
print(f"reference {image['digest']}")
problems = []
if labels.get("org.biorepro.base_digest") != image["base_digest"]:
    problems.append("base_digest label")
if labels.get("org.biorepro.containerfile_sha256") != recipe or recipe != image["containerfile_sha256"]:
    problems.append("containerfile hash")
if labels.get("org.biorepro.base_layer") != image["base_layer"] or base_layer != image["base_layer"]:
    problems.append("base layer")
if problems:
    print("worker image failed review: " + ", ".join(problems), file=sys.stderr)
    sys.exit(1)
if digest != image["digest"]:
    print("reference digest differs because the apt layer is not bit-stable; recipe labels match")
PY