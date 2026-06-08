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

## Glossary (18 terms — see [[glossary]])
[[trust-boundary]] · [[invariant]] · [[state-machine]] · [[fail-closed]] ·
[[human-in-the-loop]] · [[idempotency]] · [[open-world-ontology]] · [[source-of-truth]] ·
[[c4-model]] · [[agent]] · [[cascade-matching]] · [[model-tier-routing]] ·
[[compliance-audit-layer]] · [[prefer-deterministic]] · [[failover]] · [[toctou]] ·
[[prompt-injection]] · [[poison-message]]

## Proposals & reports
| Note | Type | What |
|---|---|---|
| [[m2s3-extraction-agent]] | proposal | **M2.S3 nine-layer pass (proposed, register OPEN)** — `ExtractionAgent`, first `LLMRouter` consumer; designs OQ-10 `ProviderResponseError`, OQ-2 batch ownership, OQ-5 injection split |
| [[m2s2-llm-router-budget-cap]] | proposal | M2.S2 nine-layer pass: paid adapters + router + budget cap + status endpoint |
| [[2026-06-02-architecture-review-post-m2s2]] | review | **current health snapshot** — post-M2.S2 as-built drift sweep (no blockers/risks; watches: latency OQ-9, malformed-envelope OQ-10, redaction, state-machine undrawn) |
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
5. ~~M2.S3 decompose (forward design pass)~~ ✅ done 2026-06-02 — [[m2s3-extraction-agent]] (register
   OPEN, awaiting owner). Designs OQ-10 (`ProviderResponseError`), OQ-2 (batch ownership → M2.S4),
   OQ-5 (structural vs semantic injection), and surfaces OQ-11/OQ-12 + a spec §6.5 imprecision (G6).
6. **Next:** owner resolves the [[m2s3-extraction-agent]] register (D1–D6 / G1–G6), then build M2.S3
   test-first. Carry the post-M2.S2 watches: resolve **OQ-9** (latency) before M2.S5; keep INV-6
   redaction-before-logging in mind. Candidate architect deep-dives: draw the **LLM-call state
   machine** (`state-machines/`, the first one) and/or the first `components/` note (OQ-C). (Ritual
   integration still deferred per ADR 0002 — evidence now points at `/wrap-session`.)

_Run log: see [[changelog]]. Seeded by `initialize-project-architecture`; extended by
`review-architecture` + `decompose-requirement`, 2026-06-02._
