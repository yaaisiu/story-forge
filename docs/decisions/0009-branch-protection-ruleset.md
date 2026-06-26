# ADR 0009 — Branch protection on `main` via a repository ruleset

**Status:** Accepted
**Date:** 2026-06-26
**Related spec section:** §6.7 (security baseline / CI gates); root [`CLAUDE.md`](../../CLAUDE.md) → *Merge flow*

## Context

Until now `main` carried only *classic* branch protection blocking force-pushes and deletion.
CI-green-before-merge and review-before-merge were upheld by **workflow discipline**, not a
server-side rule — documented honestly in [`SECURITY_POSTURE.md`](../SECURITY_POSTURE.md). For a
single maintainer that was a defensible convention, but the gap was real: nothing *enforced* that
a change reached `main` through a green pull request. As a public-portfolio repo, having the
posture provable in repository settings (not only in prose) is worth the small ceremony, and the
choice is the kind of infra decision that warrants a written record.

The well-known footgun with required status checks: a check that never *runs* on a given PR sits
forever as "Expected — waiting for status to be reported" and blocks the merge. That happens when
a whole **workflow** is skipped by a top-level `paths:` filter. Our CI avoids it by construction —
every job lives in one `ci.yml`, and the code jobs skip via **job-level** `if: needs.changes.outputs.code == 'true'`.
GitHub reports a job skipped by an `if:` conditional as **Success** for required-check purposes, so
the code jobs can be required without wedging docs-only PRs (where they skip→success while
`secret-scan` still runs and must pass).

## Decision

Govern `main` with a single **repository ruleset** (`main-protection`), replacing the classic
protection (deleted, so there is one source of truth). Rules:

1. **Block deletion, block force-push** (non-fast-forward), **require linear history.**
2. **Require a pull request before merging**, with **0 required approvals** and **squash-only**
   merges. Zero approvals because a solo maintainer cannot approve their own PR — any non-zero
   count would deadlock every merge. Squash-only matches the squash-to-`main` policy and keeps the
   public history intentional.
3. **Require status checks** (non-strict — a branch need not be up to date before merging):
   `secret-scan`, `backend`, `frontend`, `security`. **`ollama-cloud-smoke` is intentionally not
   required** — it depends on the external Ollama Cloud free tier, and gating merges on a
   rate-limit-prone external service would let an outage wedge the repo.
4. **Bypass actor: the Admin role** (the sole maintainer), mode `always`. The escape hatch is
   deliberate — without it, one misconfigured required check could lock the only maintainer out of
   their own `main` with no recourse. Protection is the *default* path; the bypass is used by
   exception. (This makes explicit and auditable what the prior `enforce_admins: false` did
   implicitly.)

## Alternatives considered

- **Extend the existing classic protection** (add required checks to it) instead of a ruleset:
  works, but rulesets are the modern mechanism — audit log, bypass-actor list, exportable as JSON
  (more portfolio-legible). Running both stacked would duplicate and obscure intent.
- **Require `ollama-cloud-smoke`:** rejected — couples merge-ability to an external free-tier
  service whose outages or rate limits are outside our control.
- **No bypass actor (enforce on admins):** maximal strictness, but for a solo repo it risks a
  self-lockout with no recourse and constrains no second committer (there is none).
- **Require ≥1 approval:** impossible solo without a second account or a bot; would block all
  merges.
- **An aggregate `ci-success` gate job** — a single job that `needs` every other job and asserts
  none failed, required in place of the individual checks: more robust against a future workflow
  restructure silently dropping a required job, but it is a CI **code** change. Deferred as optional
  hardening; recorded here as the mitigation if the "skipped = success" reliance ever feels fragile.

## Consequences

- Nothing reaches `main` except through a pull request; the four required checks must be green (or
  skipped-success on docs-only PRs). The "owner holds the merge button" rule is now backed by a
  server-side gate, not discipline alone.
- The maintainer keeps an **audited** bypass for emergencies.
- [`SECURITY_POSTURE.md`](../SECURITY_POSTURE.md)'s "Branch protection & the merge gate" section is
  updated from "GitHub enforces force-push/deletion only" to describe the ruleset.
- If CI **job names** change, the ruleset's required-check contexts must be updated in lockstep —
  the standard required-checks maintenance cost.
- The reliance on "a job skipped via `if:` reports Success" is documented above; the `ci-success`
  aggregator is the recorded fallback should that ever need hardening.
