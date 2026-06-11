---
type: index
slug: index
updated: 2026-06-11
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
| [[m3-cascade-matching]] | proposal | **M3 cascade dedupe — step-0 forward pass (`proposed`, register OPEN)** — the §3.3 four-stage cascade (RapidFuzz → embedding → JudgeAgent → human queue). Draws the candidate lifecycle; 8-entry register (DM1–DM7 + DM-rej). Central fork **DM6**: intercept-before-write (gate the graph write) vs dedupe-after — decides whether **INV-8 is replaced or layered**. Retires INV-8, lands INV-1's enforcer. Opener: `MatchingAgent` Stage 1+2 + the `pgvector` read-path switch. |
| [[m2s2-llm-router-budget-cap]] | proposal | M2.S2 nine-layer pass: paid adapters + router + budget cap + status endpoint |
| [[2026-06-11-architecture-review]] | review | **current health snapshot** — M2→M3 roll catch-up + forward sweep (no blockers; `risk`: INV-2 consent gate lost its M2.S5 landing → unscheduled + a real paid call fired gate-less; `overview.md` 2 sessions stale; INV-5/OQ-9 latency built but future-tensed. Forward: M3 lands INV-1's enforcer, lifts INV-8, needs the candidate state machine drawn — the decompose step-0) |
| [[2026-06-09-architecture-review]] | review | pre-M2.S4 drift + forward sweep (superseded as snapshot by 2026-06-11; no blockers; `risk`: `overview.md` 3 sessions stale, `entity_mentions` table absent from migrations, INV-8 needs CREATE-not-MERGE, new write-path must map router errors→HTTP; M2.S4 plan aligned; OQ-1/OQ-2 were the owner's calls — since resolved) |
| [[2026-06-02-architecture-review-post-m2s2]] | review | post-M2.S2 as-built drift sweep (superseded as snapshot by 2026-06-09; no blockers/risks; watches: latency OQ-9, malformed-envelope OQ-10 — now closed, redaction, state-machine undrawn) |
| [[2026-06-02-architecture-review]] | review | OQ-A drift sweep over M0→M2.S1 + ADRs 0001–0002 (point-in-time; findings resolved by ADR 0003) |

## Awaiting content (populated by later runs)
- `decisions/` — ADRs (host-project ADRs live in `docs/decisions/`; this folder is for
  vault-framed decisions once confirmed). Empty — the M2.S2 router/budget decision (D6) was authored as a **host-project** ADR (`docs/decisions/0003`), where product ADRs live; this vault folder stays empty until a vault-framed decision arises.
- `components/` — per-component (C4 Component altitude) notes. Empty.
- `state-machines/` — **[[candidate-lifecycle]]** drawn (the vault's **first**, `status: draft`, M3
  step-0): `extracted → {auto-merge|ambiguous|new}-proposed → judged → review-queued → (human) →
  {merged|created|rejected}`; commit guard = INV-1. Still to draw: the **ingest-job** + **LLM-call**
  lifecycles (the M2.S2 proposal sketches the latter).

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
9. ~~**build M2.S4** (Neo4j writes, no dedupe).~~ ✅ **done 2026-06-10 (PR #48).** `proposal_to_graph`
   + `Neo4jRepo` `CREATE`-not-`MERGE` (INV-8) + `entity_mentions`/`PostgresMentionStore` + the resumable
   `ExtractionCoordinator` + `POST /stories/{id}/extract`; CI gained a neo4j service so the graph
   integration tests run at the gate. **OQ-1** resolved (Neo4j-then-Postgres, accept eventual
   inconsistency; mention is the checkpoint, written last) and **OQ-2** resolved (the batch driver owns
   the pause-and-ask → 202-paused, resume from the last committed mention). overview/invariants
   refreshed in the same PR.
10. ~~**M2.S5** — frontend graph viewer + agent-activity panel.~~ ✅ **done 2026-06-11 (PR #51).**
   `features/{graph-viewer,agent-activity}/`; **OQ-9 (latency) → option (a)**: `latency_ms` column
   (migration `2026_06_11_0956…`) + router capture, shown in the §8.5 panel.
11. ~~**M2.S6** — close M2.~~ ✅ **done 2026-06-11 (PR #53), thin.** Real-provider smoke
   (`scripts/check_openrouter.py`: Ollama Cloud + an OpenRouter model, both 200; key-leak grep clean) +
   the §6.7 key-leak procedure in `backend/AGENTS.md`. **Deferred the §6.5 model-override dropdown** as
   an INV-7-touching *feature* (→ OQ-14); **observability/operational logging** recorded as a later need
   (→ OQ-15). No direct vendor adapters (OpenRouter is the only paid route — ADR 0003).
12. **M2→M3 roll gates ✅ both done (2026-06-11):** cross-cutting curation (`docs/PLAN_SHORT.md`); the
   `review-architecture` catch-up (`[[2026-06-11-architecture-review]]`); the `decompose-requirement`
   step-0 (`[[m3-cascade-matching]]` — `proposed`, register OPEN; `[[candidate-lifecycle]]` drawn).
13. **Next: M3 code — but the owner decides the OPEN register first (OQ-16 / `[[m3-cascade-matching]]`),
   above all DM6** (intercept-before-write vs dedupe-after — decides whether INV-8 is replaced or
   layered). On resolution: fold INV-1's enforcer + retire INV-8 (+ possible INV-9) into
   `[[invariants]]`, finalise `[[candidate-lifecycle]]`, draft the DM6/DM2 ADR(s). **First code:**
   `MatchingAgent` Stage 1 (RapidFuzz, deterministic, failing test first with the App. B
   Bronek/Bronisław fixture), then Stage 2 + the `pgvector` read-path switch (`NULL AS embedding` →
   `vector(768)`). Still-carried watch: INV-6 redaction-before-logging (OQ-15); the store-down→503 +
   Neo4j lifespan-close M2.S4 follow-up — see `docs/PLAN_SHORT.md` cross-cutting.

_Run log: see [[changelog]]. Seeded by `initialize-project-architecture`; extended by
`review-architecture` + `decompose-requirement`, 2026-06-02._
