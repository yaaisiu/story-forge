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

**Last reviewed:** 2026-07-30 — register created (Grzymalin S5, PR pending). One waiver,
below. Same session bumped `react-router-dom` `7.16.0 → 7.18.1`, which cleared **four** of
the five React Router advisories (`GHSA-chx6-hx7r-mcp5` HIGH DoS, plus three MEDIUMs
`GHSA-wrjc-x8rr-h8h6`, `GHSA-h8fp-f39c-q6mh`, `GHSA-337j-9hxr-rhxg`) — fix-first applied
as far as a soaked version allows.

---

## React Router — RSC-mode CSRF bypass · added 2026-07-30

| Field | Value |
| --- | --- |
| Advisory | [`GHSA-qwww-vcr4-c8h2`](https://github.com/advisories/GHSA-qwww-vcr4-c8h2) |
| Severity | HIGH (npm/GitHub) |
| Package | `react-router` (also reported transitively via `react-router-dom`) |
| Vulnerable range | `>= 7.12.0, < 8.3.0` |
| First patched | `react-router` **8.3.0** (published 2026-07-22) |
| Our version | `react-router-dom` 7.18.1 → `react-router` 7.18.1 |
| `ignoreUntil` | **2026-08-31** |

**Why it is not reachable here.** The advisory is explicit: *"This only affects your
application if you are using the unstable RSC APIs."* It is a follow-up to CVE-2026-22030
covering CSRF flows in **unstable React Server Components** code paths. Story Forge's
frontend is a Vite **SPA** with no SSR and no RSC: it imports only from `react-router-dom`
(28 call sites, all plain routing/navigation) and references no `unstable_*`, `RSC`,
`createCallServer`, `matchRSCServerRequest`, or `routeRSCServerRequest` API. The vulnerable
code path is compiled in but never executed. On top of that, the app is single-user and
loopback-bound with no public surface, so there is no third-party origin to mount a CSRF
from in the first place.

**Why it cannot simply be fixed.** The fix exists only in `react-router` **8.3.0**, and
**`react-router-dom` has no v8 release** — its latest is `7.18.2`. So no forward bump of
the package we actually depend on clears this advisory; verified empirically by installing
`7.18.1` and `7.18.2` in a scratch project and re-running `npm audit --omit=dev` (both
still report it). npm's own `audit fix --force` suggests *downgrading* to `7.11.0`, which
drops below the vulnerable floor but reintroduces `GHSA-chx6-hx7r-mcp5` (the HIGH DoS) —
a net regression, not a fix.

**Drop when:** the frontend migrates to **React Router v8** (`react-router` ≥ 8.3.0),
which means switching the 28 `react-router-dom` imports to `react-router` and handling the
v7→v8 breaking changes — a scoped piece of work that needs its own session, not a bump.
Availability is *not* the blocker: 8.3.0 cleared its 14-day soak on **2026-08-06** (floor =
publication 2026-07-22 + 15 days). The blocker is the migration itself.

**On the date.** 2026-08-31 gives room to schedule the v8 migration as its own session
while keeping a HIGH waiver on a short leash. If the migration has not landed by then the
gate re-reds — at which point `/triage-advisory` either takes the fix or extends the
waiver with a fresh, written rationale. Extending is a deliberate decision, not a default.
