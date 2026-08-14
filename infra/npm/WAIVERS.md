# npm-audit waiver register (frontend shipped deps)

Single reference for **every** advisory we waive in the frontend npm-audit gate, so they
can be reviewed for upstream fixes from time to time. This file is **documentation only**
— the **functional** waiver lives in `infra/npm/audit-waivers.toml` (`[[IgnoredVulns]]`),
read by `scripts/check_npm_audit.py`, which the **`security`** CI job runs (spec §6.7 keeps
waivers *scoped*, never gate-wide). This is the npm analogue of `infra/osv/WAIVERS.md`
(backend Python lockfile) and `infra/trivy/WAIVERS.md` (Docker images).

The gate blocks on any unwaived **HIGH/CRITICAL** advisory in a **shipped** dependency;
`devDependencies` are out of scope because a build/test tool never reaches a user (spec
§6.7, clarified 2026-06-18). **Prefer a fix to a waiver** — bump to the fixed version via
`/add-dependency` (exact pin, ≥14-day soak). Waive only an advisory that is assessed
unreachable in this deployment **and** has no soaked fix.

**Every waiver here carries a mandatory `ignoreUntil` date.** This is stricter than the
OSV register, where `ignoreUntil` is an optional backstop behind a condition-based
drop-when. The reason for the difference: an npm advisory is cleared by a version bump we
control, so there is always a real calendar horizon — and a mandatory expiry means the
gate re-reds on its own rather than an ignore rotting behind a green board.
`/resume-session` §3b surfaces an approaching date proactively; the expiry is the backstop.
A waiver whose advisory has since disappeared is reported as **STALE** by the script —
delete both its toml block and its section here when that happens.

**How to review (do this whenever a frontend dep is bumped, or periodically):**

```bash
# Exactly what CI runs:
python3 scripts/check_npm_audit.py

# The raw picture, including waived + moderate advisories:
cd frontend && npm audit --omit=dev
```

**Last reviewed:** 2026-08-13 — **the register is now empty: the sole waiver was DROPPED by a
fix.** `react-router-dom` bumped `7.18.1 → 7.18.2` (published 2026-07-28, 15 days soaked; OSV
reports no advisories against it), which clears `GHSA-qwww-vcr4-c8h2` outright — the prod-scoped
audit goes to **0 vulnerabilities** with no waiver in place.

**The reason this is worth reading:** the waiver below argued, correctly and with empirical
evidence, that *no forward bump could ever clear this*. When it was written on 2026-07-30 the
advisory listed **8.3.0** as the only patched version, and `react-router-dom` has no v8 — a
scratch install of both 7.18.1 and 7.18.2 still reported the advisory, and npm's own
`audit fix --force` proposed a *downgrade*. The advisory has since been **amended** to record a
**7.x backport**, moving the vulnerable range from `>= 7.12.0, < 8.3.0` to
`>= 7.12.0, < 7.18.2`. Nothing about our code changed; the upstream advisory did.

The lesson: **"no fix available" is a point-in-time fact, not a permanent property.** A waiver
rationale that forecloses a fix ("only a major migration clears this") must still be re-checked
against the live advisory on review, not taken on trust — otherwise it becomes self-sealing, and
a fixable HIGH sits behind a green board until its expiry. Here the drop was surfaced by a
**Dependabot** alert (which tracks the amended range) cross-checked against the gate's own
**STALE** report; the scheduled expiry would not have fired until 2026-08-31. It also means the
v8 migration is **no longer security-driven** — it can be scheduled on its own merits.

---

## ~~React Router — RSC-mode CSRF bypass~~ · added 2026-07-30 · **DROPPED 2026-08-13 (fixed in 7.18.2)**

> Retained as history per the register convention — the waiver is gone from
> `infra/npm/audit-waivers.toml` and no longer suppresses anything. The reachability analysis
> below remains accurate for the period it was live; only the "cannot be fixed" conclusion was
> overtaken by the amended advisory.

| Field | Value |
| --- | --- |
| Advisory | [`GHSA-qwww-vcr4-c8h2`](https://github.com/advisories/GHSA-qwww-vcr4-c8h2) |
| Severity | HIGH (npm/GitHub) |
| Package | `react-router` (also reported transitively via `react-router-dom`) |
| Vulnerable range | ~~`>= 7.12.0, < 8.3.0`~~ → **amended upstream to `>= 7.12.0, < 7.18.2`** |
| First patched | ~~`react-router` **8.3.0** (published 2026-07-22)~~ → **`7.18.2` (published 2026-07-28)**, via a 7.x backport recorded after this waiver was written |
| Our version | `react-router-dom` 7.18.1 when waived → **7.18.2 as of 2026-08-13 (fixed)** |
| `ignoreUntil` | ~~**2026-08-31**~~ — never reached; dropped by a fix on 2026-08-13 |

**Why it is not reachable here.** The advisory is explicit: *"This only affects your
application if you are using the unstable RSC APIs."* It is a follow-up to CVE-2026-22030
covering CSRF flows in **unstable React Server Components** code paths. Story Forge's
frontend is a Vite **SPA** with no SSR and no RSC: it imports only from `react-router-dom`
(28 call sites, all plain routing/navigation) and references no `unstable_*`, `RSC`,
`createCallServer`, `matchRSCServerRequest`, or `routeRSCServerRequest` API. The vulnerable
code path is compiled in but never executed. On top of that, the app is single-user and
loopback-bound with no public surface, so there is no third-party origin to mount a CSRF
from in the first place.

**Why it cannot simply be fixed.** ~~The fix exists only in `react-router` **8.3.0**, and
**`react-router-dom` has no v8 release** — its latest is `7.18.2`. So no forward bump of
the package we actually depend on clears this advisory; verified empirically by installing
`7.18.1` and `7.18.2` in a scratch project and re-running `npm audit --omit=dev` (both
still report it). npm's own `audit fix --force` suggests *downgrading* to `7.11.0`, which
drops below the vulnerable floor but reintroduces `GHSA-chx6-hx7r-mcp5` (the HIGH DoS) —
a net regression, not a fix.~~
**Overturned 2026-08-13** — this paragraph was accurate against the advisory *as published on
2026-07-30*, and the empirical check was real. The amended advisory records the 7.x backport, so
`7.18.2` — the very version tested above and found still-vulnerable — became the fix. The
downgrade analysis stands; only the "no forward bump" conclusion fell.

**Drop when:** ~~the frontend migrates to **React Router v8** (`react-router` ≥ 8.3.0),
which means switching the 28 `react-router-dom` imports to `react-router` and handling the
v7→v8 breaking changes — a scoped piece of work that needs its own session, not a bump.
Availability is *not* the blocker: 8.3.0 cleared its 14-day soak on **2026-08-06** (floor =
publication 2026-07-22 + 15 days). The blocker is the migration itself.~~
**Superseded 2026-08-13** — the 7.x backport in `7.18.2` cleared the advisory, so no migration
was needed. The v8 migration is no longer security-driven and can be scheduled on its own merits.

**On the date.** ~~2026-08-31 gives room to schedule the v8 migration as its own session
while keeping a HIGH waiver on a short leash. If the migration has not landed by then the
gate re-reds — at which point `/triage-advisory` either takes the fix or extends the
waiver with a fresh, written rationale. Extending is a deliberate decision, not a default.~~
**The date was never reached** — the fix landed 18 days early. Note the expiry was *not* what
caught this: a Dependabot alert tracking the amended range was, cross-checked against the gate's
own STALE report. A dated expiry bounds how long an ignore can rot; it does not detect a fix
arriving early. Both signals earn their place.
