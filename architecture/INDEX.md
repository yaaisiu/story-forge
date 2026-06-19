---
type: index
slug: index
updated: 2026-06-19
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
- [[invariants]] — the named "never break" rules (INV-1…INV-9; INV-8 retired at M3.S4a) and where each is enforced
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

## Glossary (25 terms — see [[glossary]])
[[trust-boundary]] · [[invariant]] · [[state-machine]] · [[fail-closed]] ·
[[human-in-the-loop]] · [[idempotency]] · [[open-world-ontology]] · [[source-of-truth]] ·
[[c4-model]] · [[agent]] · [[cascade-matching]] · [[model-tier-routing]] ·
[[compliance-audit-layer]] · [[prefer-deterministic]] · [[failover]] · [[toctou]] ·
[[prompt-injection]] · [[poison-message]] · [[software-composition-analysis]] ·
[[defense-in-depth]] · [[intra-batch-dedup]] · [[referential-integrity]] · [[ego-graph]] ·
[[backend-for-frontend]] · [[lost-update]]

## Proposals & reports
| Note | Type | What |
|---|---|---|
| [[backend-dependency-advisory-scan]] | proposal | **Continuous backend SCA gate in CI (✅ built 2026-06-08, PR #44)** — closes the gap where a vuln disclosed *after* pinning was caught only by Dependabot, not CI (the `starlette` 1.0.0 case). Built: osv-scanner step vs `uv.lock`, fail-on-any, **digest-pinned** scanner (the action is a no-`runs:` stub — stronger than the planned SHA-pin), `infra/osv/` waivers, `starlette` 1.0.0→1.0.1 (self-test red→green), §6.7 baseline (no new INV). |
| [[m2s3-extraction-agent]] | proposal | **M2.S3 nine-layer pass (✅ accepted 2026-06-08, register resolved)** — `ExtractionAgent`, first `LLMRouter` consumer. Decisions: per-paragraph, single-paragraph agent (batch→M2.S4), `candidate_name`, typed `ProviderResponseError`, soft-flag `evidence_quote`. **Built + merged (PR #42).** |
| [[m3-cascade-matching]] | proposal | **M3 cascade dedupe — step-0 forward pass (✅ register FULLY resolved: DM1–DM6 + DM7 + DM-rej; PLAN_SHORT Decided S23)** — the §3.3 four-stage cascade (RapidFuzz → embedding → JudgeAgent → human queue). Draws the candidate lifecycle; 8-entry register (DM1–DM7 + DM-rej). Central fork **DM6** ✅ intercept-before-write. Retires INV-8 at **M3.S4a** (the re-slice), lands INV-1's enforcer. Stages built proposal-only: M3.S1 RapidFuzz ✅ (PR #56), M3.S2 Stage 2 + pgvector ✅ (PR #58), M3.S3 JudgeAgent ✅ (PR #60). DM7 outcome: **INV-2 consent deferred past M3**. DM-rej: **remember rejections**. |
| [[m4-entity-editing]] | proposal | **M4.S3a step-0 — entity & relation editing (the first M4 *write* slice) (🟡 DRAFT, register OPEN DM-S3a-1..8 / OQ-23)** — owner-confirmed scope: from the read-only side panel ([[m4-side-panel]]), make the inspected entity **editable** — `canonical_name`/`aliases`/`type`/`properties` + **add/re-predicate/remove** relations between two already-accepted entities. **The first slice that *writes* committed graph state** — most stations flip from the read view's `n/a` to live; the weight is the write path + reversibility, not the UI. **Centre of gravity = DM-S3a-1** (new named edit handlers, a [[backend-for-frontend]] *write* endpoint, + **rewording INV-9** "exactly two writers" → "only human-reached handlers" — the ADR-0005 broadening precedent, not a new INV) **+ DM-S3a-2** (the INV-3 before→after edit-evidence record — undo's load-bearing call). As-built: `Neo4jRepo` has no committed-object mutators yet; the two graph-writers are the accept (nodes) + decide (edges) gates. Scope **S3b** (merge/delete/undo-merge + DM-Rel-5 re-point) + **S3c** (tag/boundaries/spans) at the seam only. Register OPEN — owner resolves before the first failing test. |
| [[m4-side-panel]] | proposal | **M4.S2 step-0 — entity side panel in the reader (✅ ACCEPTED & BUILT — S2a PR #89 / S2b PR #91; register RESOLVED / OQ-22; DM-SP-4 = cytoscape, S35)** — owner-chosen second M4 slice (side panel over manual-correction-in-reader): click a highlighted entity → side panel with §3.4 details (canonical/aliases/type/**properties**/occurrences/relations/timeline) + a §3.5 **local graph around that entity** (a 1-hop [[ego-graph]]). Still a **read-only projection** (most stations n/a; INV-1/9 untouched; no LLM) — *editing* is the next slice. **Centre of gravity = DM-SP-1 data source:** most data is already on hand (occurrences derive from the reader's highlights; relations/neighbours filter `get_relations`), only `properties` is surfaced by no endpoint and no per-entity *neighbourhood* query exists — so the call is a focused BFF endpoint (`GET …/entities/{eid}`, my lean) vs composing the whole-graph fetch the viewer already does. DM-SP-7 (slice split) is downstream of it. Latent: the M4 entity↔entity merge must re-point edges + mentions or the panel shows ghosts (fail-closed: omit). |
| [[m4-inline-highlights]] | proposal | **M4.S1 step-0 — inline highlights (✅ ACCEPTED, register RESOLVED S32 / OQ-21 mostly resolved; backend built PR #81)** — the owner-chosen first M4 slice (spec §3.5): render the story text, highlight **accepted** entities inline (colour-by-type), hover→tooltip. A **read-only projection** (most stations n/a; INV-1/9 untouched; no LLM call). **DM-IH-1** resolved-as-built = **render-time string search** over name+aliases (*verify-first* found persist-spans illusory — null offsets, spaCy span gone at accept); DM-IH-2 = new `GET /stories/{id}/reader`; DM-IH-3 = plain `<mark>` (not Tiptap); DM-IH-4 longest-match; DM-IH-7 accepted-only; DM-IH-8 name+type+aliases. **DM-IH-5/6 confirm-at-build in the FRONTEND slice (next).** Side-panel + manual-annotation + the entity↔entity-merge re-point are **later** slices. |
| [[m3s4a-intercept-write-path]] | proposal | **M3.S4a step-0 — intercept-before-write (✅ BUILT / ADR 0004)** — stages candidates in the new Postgres `candidates` table, wired the cascade into the coordinator (embed-on-extract → Matching → Judge), moved Neo4j+`entity_mentions` writes to the human-accept endpoints; **retired INV-8 → landed INV-1's enforcer + INV-9**, test-first. Register **DM-S4a-1..5 resolved** (S23) + ADR 0004 authored; `[[candidate-lifecycle]]` → `living`. UI is S4b (✅ built). |
| [[m3-relation-write]] | proposal | **M3 relation-write step-0 — graph edges under human control (✅ ACCEPTED, register resolved / OQ-19 struck; built M3.S4e, ADR 0005)** — completes §9 M3's "clean graph" for *relations*. The *reframe* held: a relation endpoint is a surface string with no entity id until accept → edges write **lazily** (resolve each endpoint to its candidate's *committed* id), so re-point-on-merge dissolved (only an M4 accepted-entity↔entity merge re-points a written edge — DM-Rel-5). **DM-Rel-1 = explicit human gate** (the §3.3 5th action, not auto-write) + slice split backend-now (S4e) / UI-next (S4f); **DM-Rel-2/4/5/6/7** confirmed at build as proposed; `create_relation` now idempotent `MERGE`-on-id (DM-Rel-6). INV-1 broadened to edges (not INV-10). Added [[referential-integrity]]. Carried follow-up: per-mention provenance for triple-deduped edges. |
| [[m3s4c-intra-batch-rematch]] | proposal | **M3.S4c step-0 — intra-batch dedup (✅ accepted, register resolved / OQ-18)** — triggered by the S4b browser walk (a first pass staged `Janek` ×3 → duplicate nodes the queue couldn't merge). Two additive mechanisms on S4a/S4b: **(a) on-accept live re-match** (deterministic Stage 1/2 over still-pending candidates each accept → dupes flip `new → merge`; backend-only, no LLM) + **(b) manual handpick** (entity-search endpoint + picker for matcher false negatives). Writes **only the staging table** — INV-1/INV-9 *hold*. **Resolved (owner S25):** split **S4c** (re-match) + **S4d** (handpick); auto-flip **Stage 1 `>85%` OR Stage 2 `cosine >0.85`** (no live judge); **monotone** (guard, no INV-10); handpick **project-scoped** (supersedes the deferred arbitrary-search item). Spec §3.3 amended. Build test-first (the re-match flip test). |
| [[m2s2-llm-router-budget-cap]] | proposal | M2.S2 nine-layer pass: paid adapters + router + budget cap + status endpoint |
| [[2026-06-17-architecture-review]] | review | **current health snapshot** — M3 feature-complete (S4b–S4f all shipped) → M3→M4 roll. No blockers. `risk`: `overview.md` as-built ~5 sessions stale (lists the relation graph-write + review UI as "planned, not yet built" — both shipped) (**✅ resolved 2026-06-18 — refreshed at the S31 M3→M4 roll: `overview.md` now `2026-06-17`, M3 feature-complete + "Next — M4", no "planned, not yet built"**); the relation lifecycle has no state-machine note (entity twin does → OQ-20 — **✅ resolved 2026-06-18, [[relation-lifecycle]] drawn**). `watch`: `invariants.md` frontmatter date lags its correct body; edge-id provenance collapse (ADR-0005 follow-up); held-relation visibility (**now tracked in [[relation-lifecycle]] Open points (a)**); M4 forward flags (§3.4 graph scoping now live work; DM-Rel-5 re-point becomes real; OQ-14/OQ-15 open). |
| [[2026-06-15-architecture-review]] | review | M3.S3 merged → entering M3.S4 (superseded as snapshot by 2026-06-17; no blockers; `risk`: DM5 resolved-but-framed-open, `overview.md` snapshot predates M3.S1–S3; `watch`: `task_type` label `judging`→`judge`, gate-less Stage-3 egress with INV-2 deferred, staging-table Expiry, store-chatty cascade. INV-8 correctly still live `[TEMPORARY]` — the flip is S4a's, test-first) |
| [[2026-06-11-architecture-review]] | review | M2→M3 roll catch-up + forward sweep (superseded as snapshot by 2026-06-15) (no blockers; `risk`: INV-2 consent gate lost its M2.S5 landing → unscheduled + a real paid call fired gate-less; `overview.md` 2 sessions stale; INV-5/OQ-9 latency built but future-tensed. Forward: M3 lands INV-1's enforcer, lifts INV-8, needs the candidate state machine drawn — the decompose step-0) |
| [[2026-06-09-architecture-review]] | review | pre-M2.S4 drift + forward sweep (superseded as snapshot by 2026-06-11; no blockers; `risk`: `overview.md` 3 sessions stale, `entity_mentions` table absent from migrations, INV-8 needs CREATE-not-MERGE, new write-path must map router errors→HTTP; M2.S4 plan aligned; OQ-1/OQ-2 were the owner's calls — since resolved) |
| [[2026-06-02-architecture-review-post-m2s2]] | review | post-M2.S2 as-built drift sweep (superseded as snapshot by 2026-06-09; no blockers/risks; watches: latency OQ-9, malformed-envelope OQ-10 — now closed, redaction, state-machine undrawn) |
| [[2026-06-02-architecture-review]] | review | OQ-A drift sweep over M0→M2.S1 + ADRs 0001–0002 (point-in-time; findings resolved by ADR 0003) |

## Awaiting content (populated by later runs)
- `decisions/` — ADRs (host-project ADRs live in `docs/decisions/`; this folder is for
  vault-framed decisions once confirmed). Empty — the M2.S2 router/budget decision (D6) was authored as a **host-project** ADR (`docs/decisions/0003`), where product ADRs live; this vault folder stays empty until a vault-framed decision arises.
- `components/` — per-component (C4 Component altitude) notes. Empty.
- `state-machines/` — **two drawn:** **[[candidate-lifecycle]]** (the **node** gate, `living`, M3
  step-0): `extracted → {auto-merge|ambiguous|new}-proposed → judged → review-queued → (human) →
  {merged|created|rejected}`; commit guard = INV-1. **[[relation-lifecycle]]** (the **edge** gate,
  `living`, drawn 2026-06-18 — closes OQ-20): `staged → held|committable → written|rejected` as built in
  `RelationReviewService` (re-resolve-at-commit TOCTOU guard, idempotent-by-edge-id effect, INV-1/INV-9
  broadened to edges; held/committable are derived views of the persisted `staged` row). Still to draw:
  the **ingest-job** + **LLM-call** lifecycles (the M2.S2 proposal sketches the latter).

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
   step-0 (`[[m3-cascade-matching]]`; `[[candidate-lifecycle]]` drawn). Register now resolved through
   S20 — DM1–D4 + DM6; DM5/D7/DM-rej open.
13. **M3.S1 shipped ✅ (PR #56, S20):** `MatchingAgent` Stage 1 (RapidFuzz, deterministic) — proposes
   only, INV-8 untouched. Resolved DM1 (thresholds → `config.py`) + DM2/D3/D4 (embedding model/storage)
   and added the §6.7 HF-model channel. **Next: M3.S2** — `MatchingAgent` Stage 2 (embedding cosine) +
   the `pgvector` read-path switch (`NULL AS embedding` → `vector(768)`). Then M3.S3 JudgeAgent (DM5),
   M3.S4 review queue + the DM6 write-path refactor — where INV-1's enforcer lands, INV-8 retires,
   `[[candidate-lifecycle]]` is finalised, and the DM6/DM2 ADR(s) are drafted (test-first). Still-carried
   watch: INV-6 redaction-before-logging (OQ-15); the store-down→503 + Neo4j lifespan-close M2.S4
   follow-up — see `docs/PLAN_SHORT.md` cross-cutting.
14. **M3.S2/S3/S4a/S4b/S4c/S4d all shipped ✅** (PRs #58/#60/#63 + the S4b review-queue UI + #67 S4c
   on-accept re-match + #70 S4d manual handpick). The cascade is live end-to-end for **entities**:
   extraction stages candidates, the human-accept path is the only graph writer (INV-1/INV-9), the React
   review queue (`features/extraction-review/`) drives accept/change-target/create/reject with keyboard
   nav, on-accept re-match flips intra-batch dupes `new→merge` (staging-only), and manual handpick
   (`GET …/entities?q=`) covers matcher false negatives. **M3 *entity* dedupe is complete.**
15. **M3 relation-write backend — ✅ DONE (M3.S4e, 2026-06-16)** ([[m3-relation-write]] now `accepted`,
   register resolved / OQ-19 struck; ADR 0005). §9 M3's "the graph is clean" is now literally true for
   **relations**: `RelationReviewService` resolves a staged relation's surface endpoints to committed
   entity ids and writes the edge under the explicit §3.3 5th human action, idempotent MERGE-on-id
   (one edge per fact across paragraphs), INV-1 broadened to edges. (M3.S4f — the relation-review UI, the
   S4a→S4b shape — shipped next; see item 16.)
   Still-carried: §3.4 graph story-vs-project scoping; INV-6 redaction (OQ-15); the security-waiver
   drops (PLAN_SHORT); per-mention provenance for triple-deduped edges (ADR 0005 follow-up).
16. **M3.S4f shipped ✅ (PR #78) → M3 FEATURE-COMPLETE; M3→M4 roll started.** The relation-review UI
   (the S4a→S4b shape) closed §3.3's 5th human action; both gates (entities S4a–S4d, edges S4e–S4f)
   ship. **Roll re-sync done (2026-06-17, [[2026-06-17-architecture-review]])** — the overdue post-S4e/S4f
   sweep; no blockers, headline `risk` = a 5-session-stale `overview.md` (**✅ resolved 2026-06-18 — refreshed at the S31 M3→M4 roll: `overview.md` now `2026-06-17`, M3 feature-complete + "Next — M4"**) + the un-drawn relation lifecycle
   (OQ-20). **Next: M4 — "V1 polish"** (`docs/PLAN_LONG.md`: inline highlights, side panel, manual
   annotation, properties/relations edit, multi-story, world graph). The §3.4 graph story-vs-project
   scoping and DM-Rel-5's edge re-point both **graduate from deferred to live M4 work** (multi-story +
   entity↔entity merge land here). The M4 first-slice `decompose-requirement` step-0 is the roll's last gate.
17. **M4 first slice chosen + decomposed ✅ (2026-06-17, roll gate 3).** Owner picked **inline highlights**
   (spec §3.5) as M4.S1 over multi-story/§3.4 and properties-edit. Step-0 → [[m4-inline-highlights]]
   (`status: proposed`, register **OPEN** DM-IH-1..8 / OQ-21). The headline build call is **DM-IH-1 span
   resolution** (mentions carry null offsets). **Next session:** *resolve* the open registers + the
   2026-06-17 report findings (owner asked that the roll's reports be **acted on**, not just filed), then
   build M4.S1 test-first from the span-resolution pure function. Still pending from this roll: the
   **python-multipart OSV waiver drop** (fix 0.0.31 soaks 2026-06-18 → drop on/after, before the 06-19
   `ignoreUntil`).
18. **M4.S1 shipped ✅** — backend (S32, PR #81) + frontend (S33, PR #86), live-verified end-to-end by
    the Oakhaven smoke test. [[m4-inline-highlights]] now `accepted`, register resolved.
19. **M4.S2 first slice chosen + decomposed ✅ (2026-06-18, Session 34).** Owner picked **entity side
    panel** (spec §3.4 detail panel + §3.5 local graph) over manual-correction-in-reader — the
    read-only inspection surface the next slice's corrections build on. Step-0 → [[m4-side-panel]]
    (`status: accepted`, register **RESOLVED** DM-SP-1..8 / OQ-22 — owner chose **DM-SP-1a focused
    endpoint** → **DM-SP-7 split** S2a backend / S2b frontend; strict 1-hop [[ego-graph]]; read-only).
    Built across S34 (backend) + S35 (frontend) — see entry 20.
20. **M4.S2 entity side panel BUILT ✅ (2026-06-18, Sessions 34–35).** **M4.S2a backend** (PR #89,
    S34): pure `build_ego_graph` + targeted 1-hop `Neo4jRepo.get_neighbourhood` + `GET …/entities/{eid}`.
    **M4.S2b frontend** (PR #91, S35): pure `occurrences`/`egoElements` → `useEntityDetail` → a read-only
    `ReaderEntityPanel` (details + `properties` + a 1-hop [[ego-graph]] cytoscape mini-view + an
    occurrence timeline that drills to the prose). **DM-SP-4 resolved at build = reuse cytoscape**
    (`EgoGraphCanvas`), browser-verified. Register fully RESOLVED; [[m4-side-panel]] now `accepted` &
    built. **Next:** the first M4 *write* slice — manual correction / property+relation editing in the
    reader (crosses INV-1/3/9 + the DM-Rel-5 written-edge re-point).
21. **M4.S3a scope locked + decomposed ✅ (2026-06-19).** Owner sliced "manual correction in the reader"
    by **write-risk, lowest first**: **S3a** = edit existing entities (`canonical_name`/`aliases`/`type`/
    `properties`) + add/edit/remove relations between accepted entities (no merge, no re-point, no spans);
    **S3b** = entity↔entity merge + DM-Rel-5/6 re-point + whole-entity delete + undo-merge; **S3c** = manual
    tag/un-tag/boundaries (reopens DM-IH-1 span storage); general split = post-PoC. Completeness-checked the
    cut against the full CRUD-over-{entities,relations,mentions} surface — folded two gaps into the plan
    (entity scalar-field editing → S3a; whole-entity delete + undo-merge → S3b). Step-0 → [[m4-entity-editing]]
    (`status: draft`, register **OPEN** DM-S3a-1..8 / OQ-23). **The first M4 slice that *writes* the graph.**
    **Next session:** *resolve* the register with the owner (esp. DM-S3a-1 write-path + INV-9 rewording, and
    DM-S3a-2 the INV-3 edit-evidence record), then build M4.S3a-be test-first from the pure
    boundary-validation/field-merge function. Also pending: the starlette/jp82 OSV waiver drops (`ignoreUntil`
    2026-06-26/27 — `/triage-advisory` when due).

_Run log: see [[changelog]]. Seeded by `initialize-project-architecture`; extended by
`review-architecture` + `decompose-requirement`, 2026-06-02._
