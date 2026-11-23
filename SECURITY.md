# Security

BioRepro runs a reviewed script inside a local worker. A hash miss, a symlink, a path that leaves the fixture, or an isolation setting other than non-root and `network=none` must stop the run before a worker is created.

## Reporting

Report a vulnerability through GitHub private vulnerability reporting:

https://github.com/Harry0052/biorepro/security/advisories/new

Please include the version or commit, the command you ran, and the evidence category. Do not include patient data, credentials, or a live exploit against a system you do not own.

## Supported use

Run the worker only on fixtures you are allowed to execute. The synthetic fixture in this repository is the supported demo. Agreement with an oracle is not a statement about a clinical study.
