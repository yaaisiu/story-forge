# Security & CI posture

This document tells the **how and why** behind Story Forge's security baseline — the
supply-chain discipline, the CI gates that enforce it, and the threat model that makes the
trade-offs reasonable. It is the narrative companion to the checklist in
[`story-forge-poc-spec.md`](../story-forge-poc-spec.md) §6.7 (the authoritative *what*) and to
[`SECURITY.md`](../SECURITY.md) (how to report a vulnerability).

If you only read one section, read the threat model — everything else is downstream of it.

---

## Threat model: solo, local, single trusted user

Story Forge is a single-author tool that runs entirely on the author's own machine. There is
no multi-tenancy, no public network surface, no untrusted user. Every data service binds to
`127.0.0.1`; the only HTTP client is the author's own browser.

That shapes every decision below:

- The **dominant risk is the supply chain** — a dependency or base image that ships a
  vulnerability, or a hijacked package release — *not* a remote attacker against a running
  service. So the heavy investment is in pinning, ageing, and scanning what we pull in.
- A vulnerability that needs an **untrusted remote caller** (most denial-of-service bugs, for
  example) has no one to trigger it here. That is what makes a small number of
  unfixable-for-now advisories safely *waivable* with an honest rationale (see the waiver
  lifecycle) — it is never "low risk, ignore it," it is "no reachable caller on this
  deployment, and here is why."
- It is still a **public portfolio repo**, so the bar for what reaches `main` — no secrets, no
  telemetry, reproducible pins, a clean history a stranger can read — is held high regardless
  of the local-only runtime.

The baseline is "secure by default from the first commit," not bolted on later.

---

## Supply chain: pin, age, scan

Three layered rules, all enforced in CI.

### Exact pins, with a soak

Every dependency is pinned to an **exact** version — `pyproject.toml` / `package.json` for
packages, `docker-compose.yml` for image tags. No ranges, no floating majors, no `latest`.

Each pin must clear a **soak** — a minimum age since first publication, so that a malicious or
broken release has time to be caught and pulled before we adopt it:

- **Packages: ≥ 14 days.** Enforced to the second by `scripts/check_dependency_age.py` (a CI
  step *and* a pre-push hook).
- **Images: ≥ 7 days.** Shorter on purpose: official base images come from known, signed
  publishers, so the dominant image risk is *known CVEs* rather than a hijacked release — and
  for CVEs, a fresher rebuild ships *more* patched OS packages, so freshness reduces exposure.
  Trivy CVE-cleanliness (below) is the primary image gate; the 7-day soak still leaves room
  for a compromised-tag alert to surface.

A few artifacts have **no registry** to age against. They are pinned by content instead:

- **spaCy pipeline wheels** (`pl_core_news_lg`, `en_core_web_lg`) ship only as versioned wheels
  on GitHub Releases. They are pinned as PEP 508 direct-URL references (exact by construction —
  a release-asset URL is immutable), hash-locked in `uv.lock`, and the 14-day soak is checked
  against the *release asset's* upload timestamp.
- **The embedding model** (HuggingFace Hub, not PyPI) is pinned by the repo's **immutable commit
  revision SHA** — content-addressed bytes that cannot change under a fixed revision — rather
  than fetched unpinned at first use.

Both adapt — they do not relax — the exact-pin and soak rules to a registry-less artifact;
advisory scanning is genuinely N/A for model weights (not indexed), so residual risk is bounded
by the official publisher + the locked hash + the artifact carrying only weights/config.

### Continuous scanning

Pinning and ageing only protect against what was known *at pin time*. A vulnerability disclosed
*after* a version is pinned is invisible to the soak rule — so three scanners run continuously
in CI (every code-bearing change **and** daily):

| Surface | Scanner | Gate |
|---|---|---|
| Backend lockfile (`backend/uv.lock`) | `osv-scanner` (SCA) | **fail on *any* advisory** |
| Container images (neo4j, pgvector, ollama) | Trivy | fail on HIGH/CRITICAL, fixed-only |
| Frontend shipped deps | `npm audit --omit=dev` | fail on high/critical |

The backend SCA gate is deliberately **fail-on-any**, not just HIGH/CRITICAL: the advisory that
first motivated it (`starlette` 1.0.0, GHSA-86qp-5c8j-p5mr) was a MEDIUM that a severity-gated
scan would have waved through. It is the PyPI analogue of `npm audit`, the continuous complement
to the one-shot OSV check `/add-dependency` runs at pin time, and defense-in-depth *alongside*
GitHub's server-side Dependabot — not a replacement for it.

The frontend `npm audit` is scoped to **shipped** dependencies (`--omit=dev`): the app ships a
static SPA bundle, so a build/test-only dependency (jsdom, vitest, eslint) never reaches a user
and shouldn't red `main` on un-shipped code. This narrows the gate to actual shipped risk — it
does not relax it; runtime deps stay gated, and a dev-tool advisory is still visible to a plain
`npm audit` and to Dependabot.

The OSV scanner is itself a supply-chain surface, so it is pinned by **immutable image digest**
(`ghcr.io/google/osv-scanner@sha256:…`), not a floating tag or a third-party Action — the gate
meant to catch supply-chain risk must not be one.

---

## The waiver lifecycle: fix-first, time-boxed, dropped

A scanner gate is fail-on-any (OSV) or fail-on-HIGH/CRITICAL (Trivy), so the *only* way to go
green without a code change is a waiver. A waiver is therefore a deliberate **"ignore — for
now,"** and it is dangerous exactly when nobody comes back to remove it: a known-vulnerable
dependency shipping behind a green board. The discipline that prevents that:

1. **Prefer a fix.** If a fixed version exists and clears its soak, bump to it
   (`/add-dependency` for packages, `/pin-image` for images) — never waive what you could fix.
2. **Waive only when you must,** and only with *both*: an assessed **reachability rationale**
   ("no untrusted caller on a 127.0.0.1 single-user app," named per advisory — never
   boilerplate) **and** a dated or conditional **"drop when"** (when the fix will clear its
   soak, or "when upstream rebuilds").
3. **Scoped, never repo-wide.** A waiver lives in a scoped file wired to exactly one scan step
   — `infra/osv/osv-scanner.toml` for SCA, the per-image `infra/trivy/*.trivyignore` for images
   — with the full rationale mirrored in a human register (`infra/osv/WAIVERS.md`,
   `infra/trivy/WAIVERS.md`). The enforced file and the register must mirror each other; a row
   in one and not the other is drift the review catches.
4. **Drop it when the condition is met.** The often-skipped half. Date-based waivers carry an
   `ignoreUntil` so the daily scan **re-reds on its own** once the date passes — a backstop, on
   top of the proactive `/resume-session` check that flags a waiver coming due.

The `/triage-advisory` skill owns this whole lifecycle — assess, fix-or-waive, *and* the
drop-revisit — so an "ignore" is never silent or forgotten.

A **floor**, not a `+soak` exactly. The age gate is time-precise to the second, so a recorded
drop-when date is the fix's publication date **+ (soak + 1)** days (package: +15; image: +8).
That one-day cushion clears the gate at any UTC time, so the drop acts cleanly on the date
rather than reddening the gate by a few hours.

> **Worked example (2026-06-26).** Two `starlette` advisories were waived fix-first while their
> fixes (1.3.0 / 1.3.1) soaked. On revisit, the HIGH-DoS fix (1.3.1) turned out to be only 13
> days old — its true floor was the *next* day, not the recorded one (the original date had been
> computed as publication +14, the intra-day-optimistic mistake the +15 rule exists to avoid).
> The dates were corrected, the lower waiver's `ignoreUntil` nudged one day so both CVEs drop in
> a single 1.2.0 → 1.3.1 bump once the soak completes — the lifecycle working as designed, fix
> preferred over a premature pin.

---

## CI enforcement

One workflow (`.github/workflows/ci.yml`) runs on every push to `main`, every pull request, a
**daily schedule** (04:17 UTC), and a manual dispatch button.

| Job | Runs when | What it checks |
|---|---|---|
| `secret-scan` | **always** (docs included) | `detect-secrets` against the committed baseline |
| `backend` | code-bearing | ruff lint + format, mypy `--strict`, pytest (against throwaway Postgres + Neo4j service containers) |
| `frontend` | code-bearing | eslint, prettier, `tsc` build, vitest, `npm audit` (shipped deps) |
| `security` | code-bearing **or** daily | dependency-age sweep, OSV SCA, `docker compose config`, Trivy ×3 images |
| `ollama-cloud-smoke` | code-bearing | cloud-tier reachability (passes if the key is unset, e.g. on forks) |

**Path-scoping with two backstops.** The repo is public (unlimited Actions minutes), and the
heavy jobs only have something to catch when *code* changes — so they are scoped to code-bearing
changes (anything outside `docs/**`, `architecture/**`, and `*.md`). A docs-only PR skips them.
That is safe because two things keep the baseline whole:

- The **secret scan runs on every push/PR regardless** — the one gate a Markdown file can still
  trip (a pasted credential).
- The dependency/image scans **also run daily**, so a newly-disclosed advisory against an
  *unchanged* dependency (the CVE treadmill) is caught regardless of how long it has been since
  the last code PR — coverage moves from per-PR-incidental to guaranteed-daily.

This adapts — it does not relax — the "CI enforces every rule" baseline: every code-bearing
change is fully scanned before reaching `main`. Superseded PR runs are auto-cancelled; `main`
and scheduled runs always run to completion.

> Trivy scans images **sequentially** and exits on the first failure, so fixing one image can
> *unmask* fresh CVEs in the next that were hidden behind it. A waiver/pin change is therefore
> judged green only after the *full* run, not the first passing scan.

---

## Branch protection & the merge gate

`main` is governed by a single **repository ruleset** (`main-protection`); see
[ADR 0009](decisions/0009-branch-protection-ruleset.md) for the rationale and the alternatives
weighed. Stated honestly, because a portfolio repo should not imply enforcement it does not have:

- **What GitHub enforces on `main`:** every change must arrive through a **pull request**
  (squash-merge only; linear history required); **force-pushes and branch deletion are blocked**;
  and four **required status checks** must pass — `secret-scan`, `backend`, `frontend`, `security`.
  On a docs-only PR the three code jobs skip via job-level `if:` conditions, which GitHub reports as
  success, so a docs PR is gated by `secret-scan` while a code PR must pass all four.
- **What is deliberately *not* required:** no minimum review count — a single maintainer cannot
  approve their own PR, so a non-zero count would deadlock every merge (review is upheld by the
  `/review-pr` discipline below) — and the `ollama-cloud-smoke` job is informational, not required,
  because it depends on the external Ollama Cloud free tier and gating merges on it would let an
  outage wedge the repo.
- **The maintainer is an audited bypass actor.** As the sole admin, the maintainer can bypass the
  ruleset for emergencies — a deliberate escape hatch so a misconfigured check can never lock the
  only committer out of `main`. It is the exception, not the default path.
- **What the *workflow* enforces on top:** beyond the server-side rule, CI-green-before-merge and
  review-before-merge remain disciplines — the **green-main bar** (never merge on red CI unless a
  failure is pre-existing, unrelated, and diagnosed), a self-review pass (`/review-pr`) plus a
  heavier multi-agent review (`/code-review`) for substantive code, and the maintainer personally
  taking every squash-merge to `main` (the "owner holds the merge button" rule).

The full merge flow lives in the root [`CLAUDE.md`](../CLAUDE.md) → *Merge flow*.

---

## Secrets & runtime hygiene

- **Secrets only in `.env`** (gitignored), never committed. `.env.example` carries only
  **non-functional** placeholders — never a working default credential, even for a loopback
  service. The development agent is forbidden from reading, creating, or editing `.env` /
  `backend/.env`; secret material is user-managed (enforced by deny rules, not just
  convention).
- **No defaults in compose.** Credentials are required via `${VAR:?must be set}` — the stack
  refuses to start rather than fall back to `postgres/postgres`.
- **Containers are hardened.** Every published port binds to `127.0.0.1` only; all services sit
  on a private bridge network (no `network_mode: host`); `no-new-privileges:true` on every
  container; Postgres and Neo4j drop to non-root internally and the Ollama image is wrapped to
  run as a non-root UID. Neo4j's two telemetry channels are explicitly disabled.
- **CORS is strict** — only the four loopback dev origins (`localhost`/`127.0.0.1` × ports
  5173/3000), no wildcards.
- **No telemetry libraries** of any kind (no Sentry, PostHog, Mixpanel, analytics SDKs).
- **API keys never logged** — auth headers are stripped before any log line. (Today this holds
  vacuously: the backend emits no operational logs yet; the rule becomes the redaction
  regression guard when logging lands.)

---

## Reporting a vulnerability

See [`SECURITY.md`](../SECURITY.md) for the private reporting channel and scope. The
authoritative control list is [`story-forge-poc-spec.md`](../story-forge-poc-spec.md) §6.7; the
skills that operationalize these rules are `/add-dependency`, `/pin-image`, and
`/triage-advisory`.
