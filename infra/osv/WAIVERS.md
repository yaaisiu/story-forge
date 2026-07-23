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
backstop, not the primary expiry. A dated "drop when (soaks)" is a **floor** =
fixed-version publication date **+ 15 days** (one past the 14-day soak): the age
gate is time-precise to the second, so a bare `+14` date is intra-day optimistic
and a drop acting on it can red the gate by hours (`/triage-advisory` step 3).

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

**Last reviewed:** 2026-07-23 — **dropped BOTH remaining waivers; this register is now empty.**
The setuptools `ignoreUntil = 2026-07-23` expired and re-reddened the scheduled `main` run exactly
as designed, and this time the drop was **unblocked**: `torch 2.13.0` (pub 2026-07-08T16:01:59Z)
cleared its 14-day soak that morning, so the planned **combined bump** landed — `torch 2.12.0 →
2.13.0` (which relaxes the `setuptools<82` cap) plus `setuptools 81.0.0 → 83.0.0` in `uv.lock` —
clearing **GHSA-h35f-9h28-mq5c**. The same bump also retired the **torch** waiver as a bonus:
`torch 2.13.0` is the first release outside **GHSA-rrmf-rvhw-rf47**'s range (OSV reports no known
vulnerability for 2.13.0), so the "affects all versions, no fixed version" condition that justified
that waiver no longer holds. A re-scan of `backend/uv.lock` with an **empty** waiver config reports
`No issues found`. Prior (2026-07-21) — **extended the setuptools waiver** `ignoreUntil` 2026-07-19 →
**2026-07-23**. The 2026-07-19 floor passed and the scheduled `main` run re-reddened on the
advisory, as designed — but the drop turned out **blocked**: the fix `setuptools==83.0.0` (soaked)
is forbidden by `torch==2.12.0`, which caps `setuptools<82` (`uv lock` fails on the conflict).
Only **torch 2.13.0** relaxes it (`setuptools>=77.0.3`, no cap), and 2.13.0 (pub 2026-07-08)
does not clear its own 14-day soak until **2026-07-23** (floor = pub + 15). Bumping torch early
was rejected — the `check_dependency_age.py` gate has no per-dep exception, so it would just swap
the OSV red for an age red. So a short, condition-honest extension to torch 2.13.0's soak floor;
on/after 2026-07-23 drop via a combined `torch 2.12.0 → 2.13.0` + `setuptools==83.0.0` bump.
Prior (2026-07-15) — **added the setuptools waiver** (GHSA-h35f-9h28-mq5c /
CVE-2026-59890 / PYSEC-2026-3447, MEDIUM 6.1): the scheduled `main` run reddened on this
freshly-surfaced advisory (published 2026-07-08) against unchanged deps. Fixed in 83.0.0
(pub 2026-07-04) but **not yet soaked** on the resume date (11 days < 14), so a time-boxed
waiver with `ignoreUntil = 2026-07-19` (floor = pub + 15). Prior (2026-07-06) — **dropped the pydantic-settings waiver**: bumped
`pydantic-settings` 2.14.0 → 2.14.2 (its floor, 2026-07-04, reached; the `ignoreUntil`
had expired and re-red the gate), clearing GHSA-4xgf-cpjx-pc3j (MEDIUM 5.3); removed the
`[[IgnoredVulns]]` block + this section. Prior (2026-06-27): **dropped the starlette waiver**:
bumped `starlette` 1.2.0 → 1.3.1 (its floor, 2026-06-27, reached), clearing both CVE-2026-54283
(HIGH DoS) and CVE-2026-54282 (LOW); removed both `[[IgnoredVulns]]` blocks + this section. Prior
(2026-06-26): corrected the starlette floors to pub+15 and batched the LOW's `ignoreUntil`
to 2026-06-27. Prior (2026-06-18): dropped the python-multipart waiver — 0.0.31 cleared its
soak, advisory GHSA-v9pg-7xvm-68hf gone.

---

## Active waivers

_None._ Every advisory this gate has ever raised was ultimately resolved by a **fix**
(a soaked version bump), not a permanent ignore — the two longest-lived waivers,
`setuptools` GHSA-h35f-9h28-mq5c and `torch` GHSA-rrmf-rvhw-rf47, were both dropped on
2026-07-23 (see **Last reviewed** above). `infra/osv/osv-scanner.toml` therefore carries
no `[[IgnoredVulns]]` blocks, and the gate runs fully strict against `backend/uv.lock`.

When the next advisory surfaces, `/triage-advisory` adds its row here and the matching
block there — the two must always mirror each other.

_Historical note: the advisory that motivated this gate — `starlette` 1.0.0,
GHSA-86qp-5c8j-p5mr / PYSEC-2026-161, MEDIUM — was resolved by an explicit
`starlette==1.0.1` pin in `backend/pyproject.toml`, not a waiver. That bump was
this gate's first live self-test: red on 1.0.0, green on 1.0.1._
