# OSV-Scanner waiver register (backend Python deps)

Single reference for **every** advisory we waive in the backend SCA gate, so
they can be reviewed for upstream fixes from time to time. This file is
**documentation only** — the **functional** waiver lives in
`infra/osv/osv-scanner.toml` (`[[IgnoredVulns]]`), wired to exactly one CI step
via `--config` (spec §6.7 keeps waivers *scoped*, never repo-wide). This is the
PyPI-lockfile analogue of `infra/trivy/WAIVERS.md` (which covers Docker images).

The gate is **fail-on-any**: any unwaived advisory in `backend/uv.lock` reds CI.
**Prefer a fix to a waiver** — bump to the fixed version via `/add-dependency`
(exact pin, ≥14-day soak, OSV-clean). Waive only an advisory that is assessed
unreachable, withdrawn/disputed, or genuinely unfixable (e.g. a transitive a
parent's version range forbids bumping). Each waiver here carries a reachability
justification and a **condition-based "drop when"** (mirroring Trivy's model;
the SCA analogue of "drop when upstream rebuilds" is "drop when a fixed version
clears the 14-day soak"). An optional `ignoreUntil` hard date in the toml is a
backstop, not the primary expiry.

This complements, but does not replace, **Dependabot** on `main` (server-side,
post-merge) — keeping both is [[defense-in-depth]]: the CI gate is the pre-merge
blocking net, Dependabot the post-merge redundant one, and their advisory DBs
lag differently.

**How to review (do this whenever a dep is bumped, or periodically):** for each
row, re-scan `backend/uv.lock`; if the advisory no longer appears (a fixed
version is now locked), delete its `[[IgnoredVulns]]` block from
`osv-scanner.toml` **and** its row here.

```bash
# Re-scan the backend lockfile exactly as CI does (pinned scanner = the action's
# bundled osv-scanner v2.3.8; see .github/workflows/ci.yml):
docker run --rm -v "$PWD/backend:/src:ro" \
  -v "$PWD/infra/osv/osv-scanner.toml:/cfg/osv.toml:ro" \
  ghcr.io/google/osv-scanner:v2.3.8 \
  scan source -L /src/uv.lock --config=/cfg/osv.toml
```

**Last reviewed:** 2026-06-08.

---

## Active waivers

**None.** The gate is green because backend dependencies are *fixed*, not
suppressed. (The advisory that motivated this gate — `starlette` 1.0.0,
GHSA-86qp-5c8j-p5mr / PYSEC-2026-161, MEDIUM — was resolved by an explicit
`starlette==1.0.1` pin in `backend/pyproject.toml`, not a waiver. That bump was
this gate's first live self-test: red on 1.0.0, green on 1.0.1.)
