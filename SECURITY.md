# Security Policy

Story Forge is a solo public proof-of-concept. It is not production software, but the project still takes security posture seriously — see `story-forge-poc-spec.md` §6.7 for the security baseline (localhost-only services, non-root containers, pinned and aged dependencies, no secrets in code, no telemetry).

## Reporting a vulnerability

If you find a security issue, please **do not** open a public GitHub issue. Instead:

- Open a [private GitHub Security Advisory](../../security/advisories/new) on this repository, **or**
- Email the maintainer directly (contact info on the GitHub profile linked from the repo).

Please include:

- A description of the issue and its impact
- Steps to reproduce
- Any suggested mitigation

You will receive an acknowledgement within a few days. Once the issue is fixed, the advisory is published with credit (unless you prefer to remain anonymous).

## Scope

In scope:

- Code in this repository
- The default `docker-compose.yml` configuration as shipped
- Dependency pins and the CI scripts that enforce them

Out of scope:

- Vulnerabilities in upstream dependencies (please report those to the upstream project; we will pin a patched version once available)
- Issues that require physical access to the developer's machine
- Misconfiguration introduced after forking and editing the project
