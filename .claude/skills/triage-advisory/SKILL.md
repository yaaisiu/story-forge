---
name: triage-advisory
description: Triage a security-gate advisory (OSV backend SCA / Trivy image / frontend npm-audit) through its whole lifecycle — assess severity + reachability, prefer a soaked fix (bump via /add-dependency or /pin-image), else a time-boxed waiver with a dated drop-when; AND revisit existing waivers and drop the ones whose fix has now landed. Run when a security CI job reds, or when /resume-session flags an expiring waiver. Closes the "forgotten waiver" gap so an "ignore" is never silent.
---

# Triage a Story Forge security advisory

Story Forge's `security` CI job is **fail-on-any** across three gates — the backend OSV
lockfile SCA (`infra/osv/osv-scanner.toml` vs `backend/uv.lock`), the per-image **Trivy**
scans (`infra/trivy/*.trivyignore`), and the frontend **npm-audit** (`--omit=dev --audit-level=high`
— prod-scoped to shipped deps; spec §6.7, 2026-06-18).
Fresh advisories land against *unchanged* pinned deps/images all the time (the treadmill),
so this gate reds on branches that touched none of them — and fixing one gate can **unmask**
the next (Trivy scans sequentially; OSV runs before Trivy).

A **waiver** is the only way to go green without a fix, so it is a deliberate **"ignore — for
now."** Safe *only* while: (a) no fixed version clears the soak yet (PyPI/npm **≥14 days**,
images **≥7 days**), and (b) the advisory is genuinely unreachable in *this* deployment. The
security risk this skill exists to kill is the **waiver nobody comes back to drop** — a
known-vulnerable dependency shipping behind a green board. So this skill owns **both** ends:
triage-on-surface **and** the drop-revisit.

**This composes the existing skills, it doesn't replace them.** The actual bump is
`/add-dependency` (packages) or `/pin-image` (images); `/review-pr` §5/§8 is the review-side
lens (multiple OSV ranges, package attribution, sequential-unmask). This skill is the
**entry point + decision tree + the drop sweep** that ties them together. It never relaxes
spec §6.7 — it operationalizes the fix-first + time-boxed-waiver + drop-revisit discipline
already recorded in the `WAIVERS.md` registers.

## When to run

- A `security` CI job reds (on a feature branch or `main`).
- `/resume-session` step 3b flags a due/overdue waiver.
- Any time you want a deliberate waiver sweep.

## 1. Enumerate — every live advisory AND every active waiver

Run the gates exactly as CI does (from repo root). **Scan all three; don't stop at the
first red** — fixing one unmasks the next, so you want the whole picture up front.

```bash
# Backend OSV SCA (pinned scanner = the CI action's bundled version):
docker run --rm -v "$PWD/backend:/src:ro" \
  -v "$PWD/infra/osv/osv-scanner.toml:/cfg/osv.toml:ro" \
  ghcr.io/google/osv-scanner:v2.3.8 scan source -L /src/uv.lock --config=/cfg/osv.toml

# Trivy, each image with its own ignore file (neo4j, pgvector, ollama):
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PWD/infra/trivy/<IMG>.trivyignore:/cfg/ignore:ro" \
  aquasec/trivy:0.70.0 image --quiet --severity HIGH,CRITICAL --ignore-unfixed \
  --ignorefile /cfg/ignore "<IMAGE:TAG>"

# Frontend npm-audit (prod-scoped, exactly as CI; a bare `npm audit` also shows
# dev-only advisories for awareness — they don't gate, see spec §6.7):
cd frontend && npm audit --omit=dev --audit-level=high
```

Then list every **active waiver** and its drop-condition: `infra/osv/osv-scanner.toml`
(`[[IgnoredVulns]]` + `ignoreUntil`), the three `infra/trivy/*.trivyignore`, and their
registers (`infra/osv/WAIVERS.md`, `infra/trivy/WAIVERS.md`).

## 2. Each NEW advisory — fix-first, then (only if you must) waive

For every advisory the scan reports:

1. **Identify the fixed version(s).** Read **all** OSV ranges — an advisory often carries one
   range per release branch, so the *first* range may not be the one your version falls in
   (the `/review-pr` §1 multiple-ranges lesson). Verify the package attribution against an
   authoritative source (`gh api /advisories -f cve_id=<CVE>`, GitHub Advisory DB / NVD) —
   don't trust a Trivy title alone.
2. **Is a fixed version soaked?** (package ≥14 days on PyPI/npm; image tag ≥7 days). If yes →
   **fix it**: `/add-dependency` for a package bump, `/pin-image` for an image. Prefer the
   highest soaked version that clears the advisory; check it introduces no *new* advisory.
   A "fix" that needs a parent's range relaxed (e.g. fastapi↔starlette, or torch↔setuptools) —
   confirm the parent allows it **and that the parent version which allows it is itself soaked.**
   **The age-gate (`check_dependency_age.py`) has no per-dependency exception** — a hard
   `released ≤ today−14d` with no waiver hook — so *any* bump under the 14-day soak (the target
   dep **or** an unblocking parent you must move) **cannot green CI**: it only swaps the advisory
   red for an **age red**, and commits a §6.7 soak violation besides. So when the only fix path is
   an *unsoaked* bump, do not offer or attempt it — the green options are exactly **wait-for-soak**
   (then bump) or **waive** (time-boxed to the soak floor). "Bump it young now" is never a path to
   green. (Earned Session 98: a soaked child fix — setuptools 83.0.0 — was blocked by `torch==2.12.0`'s
   `setuptools<82` cap, and the only parent that relaxes it, torch 2.13.0, was 12/14 days old; offering
   the young torch bump as a live option cost a wasted owner decision before the age-gate reality
   retracted it.)
3. **No soaked fix?** Only then a **time-boxed waiver**. It needs *both*: assessed
   **unreachability** in this deployment (127.0.0.1-bound, single trusted user, non-root,
   no public TLS, or the affected API is never called) **and** a **dated drop-when** = when
   the fix clears the soak. Record it in *both* homes that mirror each other:
   - The enforced file (`osv-scanner.toml` `[[IgnoredVulns]]` with `ignoreUntil`, or the
     `<img>.trivyignore` line) — one-line reason.
   - The register (`WAIVERS.md`) — severity, fixed-in version, **reachability rationale**, and
     the **drop-when** date/condition.

   **Compute a dated drop-when as a *floor*, not `+soak` exactly.** The age gate
   (`scripts/check_dependency_age.py`: `CUTOFF = NOW - 14 days`) is **time-precise to the
   second**, but a recorded date is calendar arithmetic — so a fix published at 08:27 UTC
   "soaks 14 days later" only *after* 08:27 on that day, and a drop acting on the bare date
   is a few hours too young and reds the gate / pre-push hook / CI. Record the date as the
   fix's **first-publication date + (soak_days + 1)** calendar days (package: pub + **15**;
   image: pub + **8**) — that floor clears the time-precise gate at any UTC time, so the
   drop acts cleanly on the date. (Session 32 lost ~50 min to a `+14` date that was
   intra-day optimistic.)
4. **A HIGH/CRITICAL waiver is a §6.7 judgement — surface it to the owner**, don't self-approve.
   State the tradeoff in plain language (what the CVE does, why it's not reachable here, when
   it drops) and get the explicit call before committing.

## 3. Each EXISTING waiver — the drop-revisit (the part that's usually skipped)

For every active waiver, check whether its drop-condition is now met:

- **Date-based** (`ignoreUntil` / "fix soaks YYYY-MM-DD"): has the date passed? Re-run step 2's
  age check on the fixed version — if it now soaks, **drop it**.
- **Condition-based** ("drop when neo4j ships netty ≥4.1.135"): re-run the gate against the
  current image/lockfile — if the advisory no longer appears, the fix landed; **drop it**.

To drop a waiver: **fix-first** (bump to the now-soaked fixed version via `/add-dependency` /
`/pin-image`), then **delete its `[[IgnoredVulns]]` block / ignore line AND its `WAIVERS.md`
row** (the two must stay mirrored — a row in one and not the other is drift `/review-pr` §2/§5
flags). Re-scan to confirm the advisory is gone with no waiver. If the condition is *not* yet
met, leave it and re-confirm the reachability rationale still holds; refresh `Last reviewed`.

**Dropping *on* the floor date? First check `main` for *another* `security` red — if there is
one, plan ONE combined PR, not two.** The floor date is the day the waiver's `ignoreUntil`
*expires*, so until your drop-PR lands `main`'s `security` gate is red on that very advisory.
If `main` *also* carries an unrelated treadmill red (a fresh image/lockfile CVE), the two fixes
**mutually block**: `security` is a *required* status check (branch-protection ruleset), so a
single-fix PR can never go green — it still trips the other red — and neither can merge. The
"split unrelated security discoveries into their own PR" rule (root `AGENTS.md` Merge flow) then
*yields*: carry **both** fixes on one branch so the required gate can actually go green. So before
you start: run all three gates (step 1) and `gh pr checks` / the last `main` run; if a second red
exists, scope one combined PR from the outset instead of opening a single-fix PR that can't merge.
(Earned 2026-06-27: the starlette waiver dropped on its 2026-06-27 floor the same day a fresh
ollama `x/crypto/ssh/agent` HIGH landed; two single-fix PRs each left the other's red on the
required `security` check, so they were folded into one.)

## 4. Verify, then PR

Re-run the affected gate(s) → **green** (or green-with-only-still-valid-waivers). Confirm the
enforced files and the `WAIVERS.md` registers mirror each other. Then the normal flow: branch
→ PR so CI runs the real gates → `/review-pr` (§5 waiver lens) → squash-merge. Mind the
**sequential-unmask** (§8): for waiver/pin changes, wait for the *full* CI run, not just the
first scan, before declaring green — fixing image N can unmask N+1.

## 5. Report

Short close-out: which gates were red and why; what got **fixed** (bumped) vs **waived**
(with drop-when) vs **dropped** (waiver removed because its fix landed); any HIGH/CRITICAL
waiver decision the owner approved; and the next dated drop-when so `/resume-session` step 3b
will surface it. Every "ignore" should leave the room with a name, a reason, and an expiry.
