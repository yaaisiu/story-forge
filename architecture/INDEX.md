---
type: index
slug: index
updated: 2026-06-08
status: living
related: []
---

# Story Forge — architecture vault

> Auto-generated map of the vault. **Regenerated** each run — do not hand-edit. The
> architectural projection layer over Story Forge: invariants, consequence analysis, a decision
> register, and a teaching glossary. It **references** the spec / plans / code as sources of
> truth (see [[project]]) and never duplicates them.

## Start here
- [[project]] — identity, personas, business, **source-of-truth registry**, calibration (the stable inputs)
- [[overview]] — nine-layer system-altitude analysis, grounded in the as-built present
- [[invariants]] — the 8 "never break" rules and where each is enforced
- [[open-questions]] — framed-but-unresolved decisions + the operator's next-step priority queue

## Core notes
| Note | Type | Mode |
|---|---|---|
| [[project]] | project | update-in-place |
| [[overview]] | overview | update-in-place |
| [[invariants]] | invariants | update-in-place |
| [[open-questions]] | open-questions | update-in-place |
| [[glossary]] | glossary (index) | regenerated |
| [[learning-log]] | learning-log | append-only |
| [[changelog]] | changelog | append-only |

## Glossary (20 terms — see [[glossary]])
[[trust-boundary]] · [[invariant]] · [[state-machine]] · [[fail-closed]] ·
[[human-in-the-loop]] · [[idempotency]] · [[open-world-ontology]] · [[source-of-truth]] ·
[[c4-model]] · [[agent]] · [[cascade-matching]] · [[model-tier-routing]] ·
[[compliance-audit-layer]] · [[prefer-deterministic]] · [[failover]] · [[toctou]] ·
[[prompt-injection]] · [[poison-message]] · [[software-composition-analysis]] ·
[[defense-in-depth]]

## Proposals & reports
| Note | Type | What |
|---|---|---|
| [[backend-dependency-advisory-scan]] | proposal | **Continuous backend SCA gate in CI (✅ built 2026-06-08, PR #44)** — closes the gap where a vuln disclosed *after* pinning was caught only by Dependabot, not CI (the `starlette` 1.0.0 case). Built: osv-scanner step vs `uv.lock`, fail-on-any, **digest-pinned** scanner (the action is a no-`runs:` stub — stronger than the planned SHA-pin), `infra/osv/` waivers, `starlette` 1.0.0→1.0.1 (self-test red→green), §6.7 baseline (no new INV). |
| [[m2s3-extraction-agent]] | proposal | **M2.S3 nine-layer pass (✅ accepted 2026-06-08, register resolved)** — `ExtractionAgent`, first `LLMRouter` consumer. Decisions: per-paragraph, single-paragraph agent (batch→M2.S4), `candidate_name`, typed `ProviderResponseError`, soft-flag `evidence_quote`. **Built + merged (PR #42).** |
| [[m2s2-llm-router-budget-cap]] | proposal | M2.S2 nine-layer pass: paid adapters + router + budget cap + status endpoint |
| [[2026-06-09-architecture-review]] | review | **current health snapshot** — pre-M2.S4 drift + forward sweep (no blockers; `risk`: `overview.md` 3 sessions stale, `entity_mentions` table absent from migrations, INV-8 needs CREATE-not-MERGE, new write-path must map router errors→HTTP; M2.S4 plan aligned; OQ-1/OQ-2 are the owner's calls) |
| [[2026-06-02-architecture-review-post-m2s2]] | review | post-M2.S2 as-built drift sweep (superseded as snapshot by 2026-06-09; no blockers/risks; watches: latency OQ-9, malformed-envelope OQ-10 — now closed, redaction, state-machine undrawn) |
| [[2026-06-02-architecture-review]] | review | OQ-A drift sweep over M0→M2.S1 + ADRs 0001–0002 (point-in-time; findings resolved by ADR 0003) |

## Awaiting content (populated by later runs)
- `decisions/` — ADRs (host-project ADRs live in `docs/decisions/`; this folder is for
  vault-framed decisions once confirmed). Empty — the M2.S2 router/budget decision (D6) was authored as a **host-project** ADR (`docs/decisions/0003`), where product ADRs live; this vault folder stays empty until a vault-framed decision arises.
- `components/` — per-component (C4 Component altitude) notes. Empty.
- `state-machines/` — the candidate + ingest-job lifecycles, plus the **LLM-call lifecycle** the
  M2.S2 proposal sketches (now **built but undrawn** — the post-M2.S2 review nominates it as the
  first one to draw). Empty.

## Next steps
1. ~~Validation/drift sweep over M0→M2.S1 + ADRs 0001–0002~~ ✅ done — [[2026-06-02-architecture-review]].
2. ~~Forward strategy pass on M2.S2 (LLM router + budget)~~ ✅ done — [[m2s2-llm-router-budget-cap]].
3. ~~Operator decides D1–D6~~ ✅ resolved 2026-06-02 ([[open-questions]] OQ-8 struck; `docs/decisions/0003`).
4. ~~Build M2.S2~~ ✅ done 2026-06-02 (PR #36) — post-build sweep [[2026-06-02-architecture-review-post-m2s2]] found no blockers/risks.
5. ~~M2.S3 decompose (forward design pass)~~ ✅ done 2026-06-02; **register resolved by owner
   2026-06-08** — [[m2s3-extraction-agent]] now `accepted`. Decisions: per-paragraph granularity,
   single-paragraph agent (resumable batch driver → M2.S4), `candidate_name`, typed
   `ProviderResponseError`, soft-flag `evidence_quote`; spec §6.5 amended (`route()`→`complete()` +
   envelope-vs-schema split, PR #39).
6. ~~Build **M2.S3** test-first per the [[m2s3-extraction-agent]] §8 hand-off, incl. OQ-10.~~ ✅
   **Done 2026-06-08 (PR #42 merged green)** — `ExtractionAgent` + prompts + candidate schemas + the
   typed `ProviderResponseError` path; `/review-pr` + `/code-review` folded (the latter caught a
   null-content envelope crash). OQ-10 now **closed in code**.
7. ~~Owner resolves the [[backend-dependency-advisory-scan]] register (G1–G7) → build the SCA gate +
   starlette bump.~~ ✅ **done 2026-06-08 (PR #44)** — register resolved + gate built the same day:
   `osv-scanner` step (fail-on-any, digest-pinned), `infra/osv/` waivers, `starlette` 1.0.0→1.0.1
   (self-test red→green), spec §6.7 amended. [[open-questions]] OQ-13 closed in code.
8. ~~Pre-M2.S4 drift + forward sweep (owner-requested).~~ ✅ **done 2026-06-09** —
   [[2026-06-09-architecture-review]]. No blockers; M2.S4 plan aligned with the invariants.
9. **Next:** **build M2.S4** (Neo4j writes, no dedupe). Honour the sweep's forward `risk`s: create the
   `entity_mentions` table in a **new migration** (it's not in the schema — only spec §6.4); hold INV-8
   with `CREATE`-not-`MERGE` + a failing no-dedupe test; map the router's exit exceptions to HTTP on the
   new write path. Owner calls as the session opens: **OQ-1** (two-store write-order + consistency
   posture) and **OQ-2** (batch-driver owns the pause-and-ask catcher). Recommended drift-fixes await
   approval (refresh `overview.md`'s snapshot, flip INV-5's OQ-10 clause). Still-carried watches: **OQ-9**
   (latency) before M2.S5; INV-6 redaction-before-logging. Architect deep-dives still on offer: the
   **LLM-call state machine** (`state-machines/`, the first) and/or the first `components/` note (OQ-C).

_Run log: see [[changelog]]. Seeded by `initialize-project-architecture`; extended by
`review-architecture` + `decompose-requirement`, 2026-06-02._
