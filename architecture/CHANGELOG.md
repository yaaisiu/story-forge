---
type: changelog
slug: changelog
updated: 2026-06-25
status: living
related: []
---

# Vault changelog

Append-only audit trail of writes into the vault. Newest entries at the top. History also lives
in `updated` fields (freshness) and git (diffs); this is the human-readable "what changed when".

## 2026-06-25 (Public-readiness Session 2) — review: V1-complete → Public-readiness re-sync sweep

- **`reports/2026-06-25-architecture-review.md`** — new dated snapshot (now the current health
  snapshot). No blockers; two `risk`s (PreNER-as-live-stage; `overview.md` M4 stale — both fixed on
  sight), three `watch` (stale invariants date, build-pending multi-story banner, INDEX regen — folded).
- **`overview.md`** — reconciled the **PreNER framing** (M2.S1 bullet + the "So today" paragraph) to
  spec §7 Step 3 deferred/dormant (code-verified `extraction_agent.py` passes empty hints); refreshed
  the **M4 as-built block** (S3b/S3c/multi-story shipped; V1 feature-complete) and the **"Next"** block
  (V1-complete → Public-readiness → Graph-quality → V2; world graph reframed post-PoC); `updated` →
  2026-06-25.
- **`PROJECT.md`** — replaced the M2.S3-era as-built parenthetical with the V1-complete picture;
  reworded the §7 pipeline classification to mark PreNER built-but-dormant; `updated` → 2026-06-25.
- **`invariants.md`** — frontmatter `updated` → 2026-06-25 (body code-verified honest — INV-9's six
  writer-paths confirmed against `neo4j_repo.py`/`entity_edit.py`, coordinator has no writer; INV-3
  executed — **body unchanged**).
- **`proposals/m4-multi-story.md`** — **BUILT banner** (be #128 / fe #130 / smoke #133; V1 done).
- **`INDEX.md`** — regenerated: multi-story row → BUILT/V1-complete; 2026-06-20 row → superseded; new
  2026-06-25 snapshot row; Next-steps items 26–27; glossary unchanged (28); `updated` → 2026-06-25.
- **`open-questions.md`** — **OQ-28** added (Graph-quality forward "what if" — auto-chunker silent
  content-loss; membership-derivation under delete); `updated` → 2026-06-25.
- **`learning-log.md`** — +1 line (doc-freshness as a state machine, 4th occurrence).
- **`/review-pr` fold (same session, PR #140):** (1) `INDEX.md` — a run-log framing note under "Next
  steps" so the historical `Next: M4` breadcrumbs (the handoff-flagged item 16) can't read as live;
  (2) `proposals/m4-multi-story.md` — `updated` → 2026-06-25 (the BUILT-banner edit had left the date
  stale, the same class this sweep fixes — matching the m4-entity-editing precedent); (3)
  `proposals/m2s3-extraction-agent.md` — a one-line as-built banner pointing the historical "chunk →
  PreNER → extract" framing at the now-permanent §7 Step 3 deferral (history kept intact); `updated`
  → 2026-06-25.
- Report-only: no code/config touched.

## 2026-06-23 (Session 50) — resolve: M4 multi-story register (DM-MS-1..7) — owner, same session

The owner resolved the register the same session it was framed. **DM-MS-1** = derive membership (set at
the decompose); **DM-MS-2** = a `scope=story|project` param on the existing `GET /stories/{id}/graph`,
**default `story`** (owner refined my `project` default → `story`; safe because the two scopes coincide
for single-story projects), edge rule (i); **DM-MS-3** = optional `project_id` on `POST /stories/upload`;
**DM-MS-4** = `GET /projects` + `GET /projects/{id}/stories` (implicit project creation kept); **DM-MS-5**
= the `world_id` cleanup rides this slice + **amend §8.4/§3.3 "whole world" → "whole project"**;
**DM-MS-6** = verified already covered by S3b; **DM-MS-7** = split be/fe, backend one slice, `world_id`
cleanup the opener. **No ADR.**

- **`proposals/m4-multi-story.md`** → `accepted`; register **RESOLVED** (top resolution banner + each
  entry rewritten to a Decision; Mermaid annotated default=story; gaps-for-PO + hand-off brought to
  resolved). The original forward-design framing kept beneath as history.
- **`open-questions.md`** — OQ-27 struck ✅ with the per-entry resolutions.
- **`INDEX.md`** — proposal row + next-steps item 25 flipped to RESOLVED/accepted.
- **Pending in the main loop (host-repo, not vault):** the §8.4/§3.3 spec stop-and-amend +
  `schema.d.ts` regen, and `docs/PLAN_SHORT.md` Decided + cross-cutting reconciliation (the
  `GET /stories/{id}/graph` scoping item + the `world_id` cleanup both close at the build).

## 2026-06-23 (Session 50) — decompose: M4 narrowed multi-story (DM-MS-1..7) — register OPEN

Step-0 `decompose-requirement` on the narrowed multi-story slice (spec §3.6, amended S44): *add a new
story that reuses the project graph + per-story entity membership*; cross-story world graph OUT of PoC.

- **`proposals/m4-multi-story.md`** (NEW, `proposed`) — nine layers + stations + Mermaid (create-into-
  project + story-scoped read) + register DM-MS-1..7 + "but what if" + plain-language gaps + hand-off.
  **Defining finding:** the slice needs almost no new machinery — membership is **derivable** from the
  `entity_mentions → … → stories` FK chain (rollup `list_entity_mentions_for_story()` exists), the matcher
  seed is already project-scoped, and the reader is already multi-story-correct.
- **DM-MS-1 RESOLVED at the decompose (owner, 2026-06-23) = DERIVE membership** from `entity_mentions`
  (no new storage; single [[source-of-truth]]; edge membership via `source_paragraph_id`'s story).
  *Rejected:* a Neo4j property/edge (a second home to sync) and a membership table.
- OPEN for the owner: **DM-MS-2** graph-read route shape (`?scope=` param vs new `/projects/{id}/graph`) +
  the edge-membership sub-question; **DM-MS-3** create-into-project exposure; **DM-MS-4** list endpoints;
  **DM-MS-7** slice split. **DM-MS-5** = `world_id` cleanup (folded) + a tiny **§8.4/§3.3 "whole world →
  whole project" stop-and-amend** (a home the S49 "world graph" grep missed). **DM-MS-6** = DM-Rel-5
  re-point **verified already covered** by S3b — nothing to build.
- **`glossary/multi-tenancy.md`** (NEW) — tenancy key (`project_id`, stored) vs per-story membership
  (derived); + a `learning-log.md` line. **No ADR, no new invariant, no state-machine** (additive slice).
- **`open-questions.md`** — OQ-27 added (DM-MS register mirror). **`INDEX.md`** — proposal row + next-steps
  item 25 + glossary 27→28. Dates bumped.
- **Host-repo (recorded, not vault):** `docs/BACKLOG.md` gained a *dual-store data architecture* analysis
  item (owner side-note, 2026-06-23 — Postgres+Neo4j split, revisit PoC→V2).

## 2026-06-19 — resolve: M4.S3a register (DM-S3a-1..8) — owner, same day

The owner resolved the M4.S3a register the same session it was framed: the four central calls took the
recommended option and the rest my leans (no objection). **DM-S3a-1** = new named edit handlers + **reword
INV-9** "exactly two writers" → "only human-reached handlers" (ADR drafted at build, test-first);
**DM-S3a-2** = a before→after edit-evidence log (INV-3 undo + flywheel); **DM-S3a-3** = route manual adds
through the decide path (sole edge-writer), re-predicate = delete+re-add, warn-on-collision, allow
self-loops; **DM-S3a-4** = invalidate-on-edit; **DM-S3a-5** = typed `properties` values; **DM-S3a-6** =
last-write-wins; **DM-S3a-7** = split S3a-be/S3a-fe; **DM-S3a-8** = reuse `search_entities_route`.
[[m4-entity-editing]] → `accepted` + fully reconciled (banner + per-entry ✅ Decision lines); OQ-23 struck;
authoritative home `docs/PLAN_SHORT.md` Decided (Session 36). No spec amendment (§3.4/§3.5 already specify
the editable panel; the INV-9 rewording lands test-first at build). Next: build **M4.S3a-be** test-first.

## 2026-06-19 — decompose: M4.S3a entity & relation editing (step-0, the first M4 *write* slice)

`decompose-requirement` step-0 on the owner-confirmed first M4 *write* slice: from the read-only side
panel ([[m4-side-panel]], shipped), make the inspected entity **editable** — scalar fields
(`canonical_name`/`aliases`/`type`) + `properties`, and **add/re-predicate/remove** relations between
two already-accepted entities. New proposal **[[m4-entity-editing]]** (`status: draft`, register
**OPEN** DM-S3a-1..8 / [[open-questions]] OQ-23). Unlike the M4.S1/S2 read-only projections, this slice
**writes committed graph state**, so the station fingerprint flips (Intent/Decision/Evidence/Review go
live) and the design weight is the write path + reversibility: **DM-S3a-1** (new named edit handlers +
**rewording INV-9** "exactly two writers" → "only human-reached handlers", the ADR-0005 broadening
precedent), **DM-S3a-2** (the INV-3 before→after edit-evidence record — the load-bearing call),
**DM-S3a-3** (relation mechanics: re-predicate = delete+re-add on the `uuid5` edge id, sole-edge-writer
preservation, MERGE-collision dedup, manual self-loops). As-built grounding confirmed: `Neo4jRepo` has
**no** committed-object mutators today (only `create_entity`/`add_alias`/`create_relation`/`get_*`), and
the two existing graph-writers are the accept (nodes) + decide (edges) human gates. Two glossary terms
added — [[backend-for-frontend]] (recurred from M4.S2, now also the *write* endpoint) and [[lost-update]]
(the first concurrency anomaly a write slice surfaces); the glossary index was regenerated (22→25,
folding in the [[ego-graph]] note that M4.S2 added but didn't index). Scope **S3b** (merge/delete/undo) +
**S3c** (tag/boundaries/spans) noted at the seam only. Register stays OPEN — owner resolves before the
first failing test.

## 2026-06-18 — decompose: M4.S2 entity side panel in the reader (step-0)

`decompose-requirement` step-0 on the owner-chosen second M4 slice (Session 34): **entity side panel**
(spec §3.4 detail panel + §3.5 local graph around the clicked entity), picked over manual-correction-
in-reader because the read-only inspection surface is what the *next* slice's corrections build on.
A **read-only projection** like its predecessor [[m4-inline-highlights]] — most stations n/a, INV-1/9
untouched, no LLM. Centre of gravity = **DM-SP-1 data source**: most of the §3.4 panel's data is
already on hand (occurrences derive from the reader's rendered highlights; relations/neighbours filter
`get_relations`), so the slice is largely an *assembly* problem — only `properties` is surfaced by no
endpoint, and no per-entity *neighbourhood* query exists. The call is a focused BFF endpoint
(`GET …/entities/{eid}`) vs composing the whole-graph fetch the viewer already does; DM-SP-7 (slice
split) is downstream of it.

- **Register RESOLVED same session (owner, Session 34):** DM-SP-1 = the focused endpoint → DM-SP-7 =
  split S2a backend / S2b frontend; strict 1-hop ego-graph; occurrences from rendered highlights; a new
  reader panel; `properties` from the endpoint; DM-SP-4 (mini-graph render) confirm-at-build in S2b. The
  proposal is flipped to `accepted` (banner + per-entry ✅ Decision lines; original Context/Options kept
  as history), OQ-22 struck, INDEX row + next-steps updated. Authoritative home: `docs/PLAN_SHORT.md`
  Decided S34. **Next: build M4.S2a backend test-first** (first failing test = the pure 1-hop
  neighbourhood-assembly function, dangling endpoints omitted).
- **`proposals/m4-side-panel.md`** (NEW, `status: accepted`) — the nine-layer + nine-station pass, a
  Mermaid data-flow, State & invariants (the read-side echo of INV-1; the M4 merge-re-point coupling
  re-surfaced from the relations direction), the **OPEN** register **DM-SP-1..8**, "but what if"
  edge cases (dangling endpoints, occurrence/mention granularity, hairball protagonist), gaps-for-PO,
  and the DM-SP-1-dependent hand-off.
- **`glossary/ego-graph.md`** (NEW, term #23) — the 1-hop neighbourhood of a focal node; the spec's
  "local graph around that entity" (§3.5) named and bounded (strict 1-hop for a narrow panel).
- **`open-questions.md`** — added **OQ-22** (the DM-SP register mirror, DM-SP-1 the central call);
  `updated` already 2026-06-18.
- **`learning-log.md`** — +2 lines (ego-graph / 1-hop neighbourhood; backend-for-frontend BFF).
- **`INDEX.md`** — regenerated (proposal row + next-steps linked; glossary 22→23; priority queue advanced to M4.S2).

## 2026-06-18 — orientation touch: npm-audit gate scoped to `--omit=dev` (spec §6.7, M4.S1)

A minimal two-edit orienting reflection on a §6.7 amendment already made by the owner (Session 33,
2026-06-18). The decision itself lives in **spec §6.7** (authoritative); the vault only records *why*
the change is sound. The frontend `npm audit` CI gate was changed from `--audit-level=high` (all deps)
to `--omit=dev --audit-level=high` (shipped runtime deps only): the SPA ships a static bundle, so a
`devDependency` (jsdom/vitest/eslint/Vite plugins) never reaches the [[trust-boundary]] surface a user
runs. Trigger: a HIGH `undici` advisory (GHSA-vmh5-mc38-953g) reaching us only transitively via `jsdom`,
unreachable here, with no 14-day-soaked fix. The general principle — *scan what you ship* — and its
escape hatch (narrow the gate's scope, an *adapt* recorded in §6.7, rather than waive or force an
unsoaked bump) is the lesson kept.

**(1) `learning-log.md`** — +1 line ("scan what you ship / gate scope = shipped risk", linked to
[[software-composition-analysis]] / [[trust-boundary]] / [[defense-in-depth]]). `updated` already 2026-06-18.

**(2) `proposals/backend-dependency-advisory-scan.md`** — added a clearly-marked **forward-pointer
annotation** under **D5** (and noting its **G4** as-built). D5 decided the gate's *level* (fail-on-any
vs HIGH/CRITICAL); this notes a *different axis*, the gate's *scope*, narrowed later. The original D5
decision text is **unchanged** (frozen accepted history); `updated:` left at 2026-06-08 (append-pointer,
not a decision change).

**Reconciliation:** none beyond this changelog — no new notes, no glossary terms (the three linked terms
already exist), so `INDEX.md` and `glossary.md` are untouched. No invariants, state machines, or overview
edits. No production code, no spec/plan/`docs/` edits (the §6.7 amendment is the owner's, already landed).

## 2026-06-18 — vault maintenance: relation lifecycle drawn (OQ-20), DM-IH register reflected (OQ-21), glossary routing fixed

A focused M3→M4-boundary sync pass — three already-scoped writes to bring the vault in line with the
as-built reality, no new decomposition.

**(1) OQ-20 closed — the edge gate's state machine.** Drew **`state-machines/relation-lifecycle.md`**
(`living`), the **edge** twin of `[[candidate-lifecycle]]`, grounded in `agents/relation_review.py`
(`RelationReviewService`) + the `staged_relations` migration + ADR 0005: states `staged → held |
committable → written | rejected`, the re-resolve-at-commit [[toctou]] guard (list-time resolution is
advisory; `decide` re-resolves → 409 on drift), the idempotent-by-edge-id effect
(`relation_edge_id = uuid5(subject_id, predicate, object_id)`), and the evidence/status-last effects.
**Faithful surprise recorded:** `held`/`committable` are **not persisted** — only `staged|written|rejected`
is — so they are modelled as *derived views* of the single `staged` row, recomputed each read by
re-resolving endpoints (the same in-memory-transient-states shape the twin uses). Folded OQ-20's two
sub-gaps as carried watch-items in the note (**not** resolved): (a) **held-relation visibility** (a
never-committable relation rests silently with no Evidence row — INV-3 for edges has no home); (b) **edge
Expiry** (held rows never expire — accepted none-at-PoC, ADR 0005, the edge twin of OQ-4). Marked OQ-20
**resolved** in `open-questions.md` with the sub-gaps pointed at the new note.

**(2) OQ-21 reflected — the M4 inline-highlights register.** Brought `proposals/m4-inline-highlights.md`
to `status: accepted` with a dated resolved banner and annotated the **whole** DM-IH register (not just a
top banner): **DM-IH-1/2/3/4/7/8 resolved-as-built** (PR #81) — DM-IH-1 = render-time string search over
name+aliases (*verify-first* found persist-spans illusory: null offsets + the spaCy span gone at accept);
DM-IH-2 = new `GET /stories/{id}/reader`; DM-IH-3 = plain `<mark>` (not Tiptap); DM-IH-4 longest-match;
DM-IH-7 accepted-only; DM-IH-8 name+type+aliases. **DM-IH-5/6 = frontend confirm-at-build (M4.S1 frontend
slice).** Original Context/Options text kept intact (public-portfolio history). Annotated **OQ-21** as
mostly-resolved, pointing at the proposal as the resolved home. Authoritative source: `docs/PLAN_SHORT.md`
Session-32 Decided — the vault is the orienting layer that lagged.

**(3) Glossary routing drift fixed.** `glossary/model-tier-routing.md` still said the `LLMRouter` + paid
adapters were "Planned for M2.S2 — not yet built." Verified as-built (`adapters/llm/router.py` `LLMRouter`,
`openrouter.py` `OpenRouterProvider`) and rewrote to the present tense ("Built in M2.S2"), referencing
`docs/decisions/0003` for provider order — a reference, not a duplication. Bumped its `updated` stamp.

**Reconciliation:** regenerated `INDEX.md` (two state machines now drawn, relation-lifecycle removed from
"still to draw"; m4 proposal row → ACCEPTED; 2026-06-17 review row annotated with OQ-20 resolved); added a
`[[relation-lifecycle]]` learning-log line (derived-vs-persisted state) + bumped its date. Glossary count
unchanged at 22 (model-tier-routing edited, not added). No production code, no spec/plan/`docs/` edits.

## 2026-06-16 — decompose-requirement: M3 relation-write (graph edges under human control, step-0)

Forward-design pass for the M3 slice that completes §9 M3's *"the graph is clean"* **for relations**:
entity dedupe (S4a–S4d) is done, but a merge orphans a candidate's staged relations because **no code
writes graph edges** — the gap M3.S4a's own "but what if" had named and deferred. Owner framing
(2026-06-16): this is an **M3 slice**, not an M3→M4 roll.

Wrote **`proposals/m3-relation-write.md`** (`status: proposed`, register **OPEN**): the nine-layer +
nine-station pass, a Mermaid data-flow, a sketched relation-lifecycle (standalone note deferred until
the gate decision resolves), a seven-entry decision register (**DM-Rel-1..7**), the "but what if" set,
and the gaps-for-PO. Central finding (the *reframe*): under intercept-before-write the feared
"re-point edges on merge" **mostly dissolves** — a relation endpoint is a surface string with no entity
id until accept, so edges can only be written **lazily** by resolving each endpoint to its candidate's
*committed* id; a merge is then handled by construction, and only an accepted-entity↔entity merge (M4)
would re-point a written edge. Concrete must-fix surfaced: `create_relation` uses `CREATE`, so a
retried accept **doubles** the edge — needs deterministic-id `MERGE` (DM-Rel-6). Added glossary
**[[referential-integrity]]** + a learning-log line. Mirrored the register + the empty Evidence/Expiry
stations to `open-questions.md` **OQ-19**. Regenerated `INDEX.md` (new proposal row; refreshed the stale
"Next steps" that still framed S4c as next though S4c/S4d shipped; glossary 21→22) and the `glossary.md`
index (also folded in the previously-missing [[intra-batch-dedup]], count → 22). No ADR, no invariant
fold, no state-machine note, no production code — all deferred to register-resolution per the skill.

## 2026-06-15 — decompose-requirement: M3.S4c intra-batch dedup (live re-match + handpick, step-0)

Forward-design pass triggered by the **M3.S4b browser walk**: a single first-pass extraction of the
sample story staged `Janek` ×3 (and `Marta`/`Konrad`/`Order` ×2) as independent NEW proposals → after
accept, **duplicate Neo4j nodes** the review queue could not merge, undercutting §9 M3's "the graph is
clean". The cascade only dedupes *cross-pass* (against the accepted graph at stage time); this is the
*intra-batch* gap M3.S4a's own "but what if" had named and deferred.

- **New proposal:** `proposals/m3s4c-intra-batch-rematch.md` (`status: proposed`, register **OPEN**).
  Designs two additive mechanisms on top of S4a/S4b: **(a) on-accept live re-match** — re-run the
  *deterministic* matcher (Stage 1 RapidFuzz + Stage 2 cosine, reusing the stage-time `context_embedding`
  + the accepted entity's mention vector; **no LLM**) over still-pending candidates each accept, flipping
  duplicates `new → merge` (backend-only — the S4b card already renders merge proposals); **(b) manual
  handpick** — a `GET …/entities?q=` search + picker so the human can target *any* existing entity, the
  safety net for matcher false negatives. Both write **only the `candidates` staging table** — INV-1 +
  INV-9 **hold, not change** (re-match is the first automated *staging-proposal* writer; INV-9's line is
  graph-vs-staging). Nine-layer + nine-station pass; Mermaid data-flow; but-what-if (false-positive
  re-match, mid-review proposal flips, idempotency/thrash, rejected-not-resurfaced, handpick stale-target
  409, **handpick-merge inherits the deferred relation-write**, perf bound).
- **State machine:** proposes a `review-queued → review-queued` **re-proposal** self-loop (monotone:
  only `new → merge`; no graph write, no evidence row) — folded into `[[candidate-lifecycle]]` only on
  acceptance.
- **Open register OQ-18 / DM-S4c-1..6:** slice S4c (re-match) + S4d (handpick); trigger/scope
  (synchronous-in-accept + incremental); auto-flip strength (Stage-1-only, **no live judge**); monotone
  refinement (possible INV-10 — lean guard); handpick scope (project-scoped — **supersedes** the deferred
  "arbitrary-entity search" cross-cutting); handpick endpoint/source. Mirrored to `open-questions.md`.
- **Glossary +1** → 21: `[[intra-batch-dedup]]`. **learning-log +2** (intra-batch dedup; monotone
  refinement / suggestion-only automated writer). **INDEX** regenerated.
**Register resolved same session (owner, Session 25):** proposal flipped `proposed → accepted`,
every DM-S4c register entry `My proposal` → `Decision` (**DM-S4c-3 overridden** — owner chose auto-flip
on **Stage 1 `>85%` OR Stage 2 `cosine >0.85`** over my Stage-1-only; no live judge), the Stage-1-only
framing de-activated across the body (Policy station, but-what-if, hand-off), Gaps-for-PO + the INV-10
sub-question resolved (not minted — monotonicity stays the transition guard), OQ-18 struck. Decisions:
slice **S4c (re-match) + S4d (handpick)**; synchronous-in-accept + incremental; project-scoped handpick
(`GET /stories/{id}/entities?q=`); relation-write **kept deferred** but priority raised.

**Spec + plan reconciled (host source of truth, stop-and-amend flow):** `story-forge-poc-spec.md` §3.3
gained the **on-accept re-match** + **manual-handpick** clarifications + a deterministic-only cost-note
line. `docs/PLAN_SHORT.md`: M3.S4c + S4d added to the feature order, a Session-25 Decided entry + the
struck M3.S4c register (Blocked), the "arbitrary-entity search" cross-cutting **folded into S4d** (struck
✅), the relation-write cross-cutting **priority-raised** note. No production code; ADR 0005 (if warranted)
authors test-first with the S4c code. The `[[candidate-lifecycle]]` self-loop + INV-9 clarification fold
on that build, witnessed by the failing re-match flip test.

## 2026-06-09 — fold: drift-fixes applied + full doc audit (owner-approved)

The 2026-06-09 sweep's recommended drift-fixes were **approved by the owner and folded**, plus a
full audit of the remaining vault notes for staleness. Edits (all vault-only, no code): **`overview.md`**
— M2.S2 + M2.S3 moved to "built and merged" (was 3 sessions stale, still calling them "planned"), the
"does not yet extract" summary corrected to "extracts but does not yet write the graph", the
nine-station Monitoring row flipped `◻ planned → ✅ partial` (status endpoint + ledger built),
`updated` 06-02→06-09. **`invariants.md`** — INV-5's OQ-10 "coverage gap" clause flipped to
as-built-closed (PR #42), INV-4's "(M2.S3)" planned tense → as-built, `updated` 06-08→06-09.
**`PROJECT.md`** — Identity line "extraction is M2.S3–S4" → "extraction built (M2.S3); graph write
M2.S4", `updated` 06-02→06-09. **`m2s2-llm-router-budget-cap.md`** — the stale `router.route()`
station-table depiction → `router.complete()` (as-built / amended spec §6.5; the cross-cutting
doc-hygiene item), `updated` bumped. Audit confirmed clean: glossary index (20) matches INDEX; no
orphans / ghost refs / stale ADRs. INDEX already current (regenerated).

## 2026-06-09 — review: pre-M2.S4 drift + forward sweep

`review-architecture` run at the owner's request before building M2.S4 (Neo4j writes), diffing the
vault against the as-built after M2.S3 (PR #42) + the SCA gate (PR #44) merged. New
`reports/2026-06-09-architecture-review.md`. **No blockers.** Findings: (1) `risk` — `overview.md` is
three sessions stale, still listing M2.S2 *and* M2.S3 as "planned, not yet built"; (2) `watch` —
INV-5 still calls OQ-10 an open gap though `ProviderResponseError` landed in PR #42, and
`open-questions.md` OQ-10 isn't struck-closed though INDEX says it is; (3) `risk` (forward) — the data
model assumes an `entity_mentions` table that **does not exist in the migrations** (only spec §6.4) —
already fixed in `docs/PLAN_SHORT.md` this morning; (4) `risk` (forward) — INV-8's no-dedupe must be
held by `CREATE`-not-`MERGE` + a failing test; (5) `risk` (forward) — the new graph-write API path
must map router exceptions to HTTP or it 500s (chunking path catches only `ChunkingError`). Forward
lens: M2.S4 plan **aligned** with the invariants; OQ-1 (two-store consistency) + OQ-2 (resumable batch)
are the owner's calls as the session opens. Trail: `open-questions` +findings (deduped into OQ-1/OQ-2
notes); learning-log +3. **Report-only:** the `overview.md`/`invariants.md`/OQ-10 drift fixes are
*recommended* for owner approval, not folded unilaterally.

## 2026-06-08 — decompose: backend dependency-advisory scan (continuous SCA)

`decompose-requirement` on adding a backend Python SCA gate to CI, triggered by GHSA-86qp-5c8j-p5mr
(`starlette` 1.0.0, MEDIUM, via `fastapi`) — Dependabot caught it, CI did not (Trivy scans only
Docker images; no scan of `backend/uv.lock`). New `proposals/backend-dependency-advisory-scan.md`
(`status: proposed`, register D1–D7 open): owner leans **osv-scanner**, **selected fail-on-any +
waiver file** (D2); open G1–G7 (tool confirm, **spec §6.7 amendment** to document the gate, waiver
home/format/expiry reusing the Trivy `WAIVERS.md` split, `npm audit` symmetry, scanner-Action
SHA-pin, baseline-vs-INV-9, bundled `starlette` 1.0.0→1.0.1 bump). Glossary +2
(`software-composition-analysis`, `defense-in-depth` → 20). `open-questions` +OQ-13; learning-log +2.
This is **strengthening** the §6.7 baseline (not the stop-and-amend-to-relax flow). No production code
touched (architect is vault-only); the gate + bump are the implementer's build once the owner resolves.

**Register resolved same day (owner approved G1–G7 cluster):** proposal flipped `proposed → accepted`,
every register `My proposal` → `Decision`, §7 gaps marked resolved, §8 hand-off rewritten with the
next-session build steps. OQ-13 advanced (stays open until code lands, OQ-10 posture). Decisions:
osv-scanner, fail-on-any + scoped waivers (`infra/osv/`), SHA-pinned Action, `npm audit` left
HIGH/CRITICAL, §6.7 baseline control (no new INV), explicit `starlette==1.0.1` pin. **Build deferred to
next session; the spec §6.7 amendment lands *with* the build** (avoids claiming a gate CI doesn't run).

## 2026-06-08 — M2.S3 register resolved + spec §6.5 amended (owner walkthrough)

The owner walked the `[[m2s3-extraction-agent]]` register; the proposal is now `status: accepted` and
rewritten to resolved state (§5b): **D4** per-paragraph (agent fragment-agnostic), **D5**
single-paragraph agent — resumable batch driver → M2.S4 (pause-and-ask propagates), **G5** soft-flag
`evidence_quote`, **D1/D2/D3/D6** accepted as proposed. Rejected options (per-scene, hard-reject,
agent-owns-batching, blanket `except`) marked history in the body, not build instructions.

**Spec amended (host source of truth, stop-and-amend flow) — G6/Codex #2:** `story-forge-poc-spec.md`
§6.5 router block `route(self, task) -> LLMProvider` → `complete(messages, *, weight, task_type,
json_schema=None) -> CompletionResult` (orchestrating API, ADR 0003); §6.5 + §11 "Failover" paragraphs
now split **envelope-malformed (→ failover via `ProviderResponseError`)** from **schema-invalid
(→ agent prompt-retry)**. Reconciled host homes: `README.md` failover line, `docs/PLAN_SHORT.md`
(cross-cutting item struck ✅, line-64 claim now true). Left intact as history: ADR 0001
(superseded-in-part), the M2.S2 Done/Decided log lines. Vault: OQ-11/OQ-12 struck, OQ-2/OQ-10 advanced,
this proposal's register + gaps brought to resolved. No code touched (ProviderResponseError is the
M2.S3 build).

## 2026-06-02 — `decompose-requirement` (M2.S3 ExtractionAgent — feature step 0)

Forward design pass on **M2.S3 (`ExtractionAgent`)**, run by hand as the feature's step 0 (ritual
integration still deferred, ADR 0002). Wrote `proposals/m2s3-extraction-agent.md` (`status: proposed`,
register **OPEN** — D1–D6 / G1–G6 await the owner). Nine layers + nine stations + Mermaid data flow +
"but what if" + gaps. Designs the three threads the post-M2.S2 sweep seeded: **OQ-10** (typed
`ProviderResponseError` — envelope-malformed→failover vs schema-invalid→retry-prompt), **OQ-2** (agent
stays single-paragraph; resumable batch driver → M2.S4), **OQ-5** (structural vs semantic injection).
Surfaced two new open items and one host-doc flag:
- **OQ-11** — `EntityCandidate.candidate_name` (surface form) vs the plan's "canonical_name" wording.
- **OQ-12** — `evidence_quote` verification posture, dangling relations, PreNER-hint deferral.
- **G6 / host flag** — spec §6.5's router comment lumps "malformed response schema → retry the prompt",
  conflating the envelope-vs-schema split; flagged for a one-line spec clarification (owner's call).

Also folded a **Codex review finding** (small-PR, no-PR-flow) into the vault directly: **INV-5's "writes
one row on *every* terminal edge"** over-claimed coverage given OQ-10 — narrowed to "every terminal edge
**the router currently handles**" + an explicit "known coverage gap (OQ-10)" clause, so a reader can't
mistake INV-5 as already total before the `ProviderResponseError` work lands. Glossary +2
(`prompt-injection`, `poison-message`; 16→18), learning-log +1, open-questions extended (OQ-2/5/10) +
OQ-11/OQ-12 added, INDEX regenerated. No code/config/host-plan touched by the architect (the two
host-side Codex findings are handed back to the main loop for `PLAN_SHORT.md`).

## 2026-06-02 — `review-architecture` (post-M2.S2 as-built sweep, Session 11 wrap)

Second `review-architecture` of the day, run at **session wrap** (after merging M2.S2 PR #36 + wrap
PR #37) — distinct subject from the morning's pre-build OQ-A sweep. Wrote
`reports/2026-06-02-architecture-review-post-m2s2.md` (separate filename so neither clobbers the
other). Headline: **no blockers, no risks** — the as-built faithfully implements ADR 0003; the two
pre-build risks are closed and the **INV-7 near-miss is closed** (ledger records system-derived
tier/provider/model). All findings are `watch`.

- **Drift (planned→as-built lag):** INV-2/5/7 still say "planned (M2.S2) … not yet built" — flip each
  guard to as-built (recommendation; the sweep doesn't edit invariants without confirmation). Noted
  `CompletionResult.model_tier` is still the caller-passed arg (cosmetic; ledger ignores it).
- **Source-of-truth conflict → OQ-9 (latency):** INV-5 + the proposal + the M2.S5 panel task all
  promise `latency`, but the as-built `llm_calls` records none and spec §6.6 doesn't list it. Decide
  before M2.S5: add a `latency_ms` column (proposed) or trim the over-claim.
- **Undrecorded decision:** the **independent-commit ledger** (own connection per write so failure
  rows survive a request rollback) is in code + `PLAN_SHORT` Decided but not the vault — proposed a
  one-line INV-5 enforcement clause (not a new ADR).
- **Fresh near-misses:** INV-6 — M2.S2 is the first paid-key code; it logs nothing today (clean), but
  the named redaction middleware still doesn't exist → build it before the first provider log
  (error bodies echo prompts). D3 cap-overshoot bound weakens if M2.S3 batches concurrently.
- **Forward lens (owner ask) — plan vs architecture:** **no contradiction** S3–S6 vs the
  invariants/decisions. Surfaced **OQ-10** (malformed-`200`-envelope → typed `ProviderResponseError`,
  M2.S3) and made **OQ-2 concrete** (the router now *raises* the pause but nothing *catches* it for a
  resumable batch — M2.S3/S4). The built-but-undrawn LLM-call **state machine** is the strong
  candidate for the next architect deep-dive (ties OQ-C).
- **Process evidence:** recorded that running the sweep at **wrap (end)** is the owner's preference and
  points ritual-integration at `/wrap-session` (ADR 0002 still deferred). open-questions priority-queue
  note + learning-log +3 (out-of-band audit logging, poison-message/dead-letter, state-machine totality).
  **No code or config touched.**

## 2026-06-02 — Review fold (PR #34): accepted-proposal honesty + stable refs

Folded the own-`/review-pr` should-fix + a Codex first-pass review (two P2s, same class) into the
M2.S2 proposal. The `accepted` briefing still carried *pre-decision* active-voice guidance that
contradicted the settled scope — and the handoff points the implementer at it before writing tests,
so it would have produced the wrong files/tests.
- **Codex P2 ×2 + the same class my pass under-rated:** rescoped every "build direct vendor adapters"
  spot (Requirement, §3, §4 `T3` node) to OpenRouter-only; struck/annotated the rejected default-deny
  egress gate + proposed INV-9 (§4 `EG` node noted, §5, §7 Layer 7, §8 G2) as superseded history. Added
  a **⚠ Reading note** to the proposal banner naming both superseded threads so nothing in the body
  reads as a build instruction.
- **Own should-fix:** 4 fragile "spec §6.5 line 412" references → stable "§6.5 GPU-less-host paragraph"
  (proposal ×2, this changelog, ADR 0003).
- Lesson (for `/review-pr`): an *accepted* design briefing that the handoff cites as orienting context
  must not contain active-voice guidance contradicting the decision — annotate rejected options as
  history, don't leave them in the imperative. My pass saw the INV-9 instance but rated it "banner
  covers it"; Codex correctly escalated because the doc is a pre-test reading target.
- **Codex second pass (4 P2s, all real — folded):** the spot-annotation approach was still a
  half-measure. Brought the proposal fully to *resolved* state (update-in-place is the proposals'
  mode anyway): §6 decision register header + each D now read **Decided** not "I propose" (D5 marked
  as the owner *overriding* my proposed gate); §7 quota "still open" → resolved; §8 G1/G3/G4 struck
  resolved; hand-off "no ADR authored" → "ADR 0003 authored"; the §2 Policy station, §4 Mermaid
  `EG` gate node, and §5 state-machine guard no longer show the dropped egress gate. **P2#3:**
  `INDEX.md` de-staled (ADR 0003 is authored in `docs/decisions/`; OQ-8 struck). **P2#4:** the
  usage-row wording in spec §6.6 + ADR 0003 + `PLAN_SHORT` corrected — input/output **tokens are kept
  whenever the provider returns them** (incl. Ollama's eval counts), `gpu_seconds` nullable for Ollama
  Cloud, `cost_estimate` nullable for paid (the old "tokens for paid only" reading contradicted INV-5).
  Stronger lesson: when a decompose proposal is *accepted*, resolve its whole body, don't patch
  cited spots — half-resolved reads as undecided.
- **Codex third pass (3 P2 + 1 P3, the long tail — folded):** the handoff `Verify on disk` still
  listed `{anthropic,openai,grok,router}.py` as what M2.S2 builds (→ `{openrouter,router}.py`); the §3
  `config.py` list still named a paid-egress flag (gate dropped); the §4 Mermaid still routed quota
  exhaustion to "pause / escalate / stop" (→ pause-and-ask, no escalate); the clock-skew edge case
  still called the day-origin a "D1 open item" (D1 resolved = local-midnight). After folding, ran an
  **exhaustive grep sweep** (open-framing / egress-flag / escalate / stale-adapter-list / provider-order)
  to stop the patch-and-recheck cycle — this is the lesson the wrap/retro will encode into `/review-pr`.
- **Codex fourth pass (2 P2 + 1 P3 — folded) — the source-of-truth lesson in the flesh.** I had
  amended spec **§6.5** but left the *same fact* stale in its **other homes**: spec §5 hardware-tier
  table, §9 M2 roadmap, the §1 + §M0 provider/key lists; the root `AGENTS.md` stack reminder; the
  vault `overview.md` M2 snapshot (M2.S2=anthropic/openai/grok, M2.S6=OpenRouter); and residual
  "open" framing inside the resolved OQ-8 body. Reconciled all, plus the ones Codex *didn't* flag
  that a repo-wide sweep caught: `docs/PLAN_LONG.md` M2 bullet, `backend/src/story_forge/AGENTS.md`
  adapter-layer doc (the M2.S2 implementer reads it), `README.md` routing blurb. Left ADR 0001's
  original text untouched (append-only history). **Lesson:** a decision touches a fact that lives in
  many homes; reconciling one (even the authoritative §6.5) is not reconciling the decision —
  enumerate every home and grep the *whole repo*, not just the PR's already-touched files.
- **Codex fifth pass (2 P2 + 1 P3 — folded) — the same class one layer deeper.** The remaining
  stale spots were in **tracking / registry / navigation notes that describe a resolved fact in
  *different words*** (so a keyword grep for the decision misses them): `overview.md` Layer 6 still
  called the quota-exhaustion UX "an open UX decision" (→ pause-and-ask resolved); `PROJECT.md`'s
  source-of-truth registry + existing-docs list omitted ADR 0003; `open-questions.md`'s priority
  queue still listed OQ-A/OQ-B as "the next thing to do" though this run completed both;
  `README.md` pointed only to ADR 0001 as "the LLM ADR". **Lesson (sharper):** resolving a decision
  ripples into the notes that *track* it — registries, priority queues, as-built/error analyses,
  doc-pointers — which don't contain the decision's keywords. The reconciliation checklist must
  include "update every note that *tracks status* (ADR registry, OQ priority queue, error-handling
  snapshot, doc indexes)", not just every note that *states the fact*.
- **Codex sixth pass (1 P2 + 1 P3 — folded) — the dated-artifact-as-live class.** The
  `reports/2026-06-02-architecture-review.md` carried `status: living` and INDEX bills it as the
  "current health snapshot," so its `risk`/`watch` findings (all resolved the same day by ADR 0003)
  read as *open* risk. Added a top resolution banner + changed status `living → accepted` — a dated
  review is a point-in-time record, not a live risk board. Also reframed `README.md`'s quickstart
  key list to foreground Ollama Cloud + OpenRouter (Google/Gemini "as the adapter lands"). **Lesson:**
  a *dated* artifact (review report, sweep, snapshot) whose findings get resolved must say so at the
  top, or it masquerades as current state — `status:` and any "latest/current" framing must match.

## 2026-06-02 — Reconciliation: M2.S2 decisions settled (owner) + vault navigability

Not an architect skill run — a host-repo update folding the owner's decisions back into the vault so
it doesn't drift from reality (the exact failure the same-day review warned about). The owner resolved
OQ-8 (D1–D6) + G1; recorded in `docs/decisions/0003` (new ADR, supersedes ADR 0001's provider-priority
+ quota-degradation consequences) + `docs/PLAN_SHORT.md` Decided; spec §6.5/§6.6 amended.

- **open-questions:** OQ-3, OQ-6, OQ-7, OQ-8 struck ✅ with dated resolution pointers (original framing
  kept for history, per the note's convention).
- **invariants:** INV-2 annotated (consent gate a *deliberate* M2.S5 deferral, not an oversight —
  proposed temporary INV-9 dropped); INV-5 annotated with the decided usage-shape + pause-and-ask +
  system-derived tier (closes the INV-7 near-miss).
- **proposal** `m2s2-llm-router-budget-cap` → `status: accepted`, resolution banner added.
- **Navigability (owner ask):** added `architecture/AGENTS.md` (+ `CLAUDE.md` symlink) — a directory
  guide stating the source-of-truth boundary + how to navigate; root `AGENTS.md` now points to the
  vault. This is *awareness*, not ritual-wiring (ADR 0002 §4 integration still deferred).
- **Dogfood verdict (for the record):** this run is the first where the architect's artefacts fed real
  product decisions (provider order, budget posture, the INV-5 seam). Evidence leans "wire
  `review-architecture` at milestone boundaries + `decompose-requirement` for branchy features," but
  the wiring decision stays deferred per ADR 0002.

## 2026-06-02 — `decompose-requirement` (M2.S2 router + budget cap, OQ-B forward pass)

First live `decompose-requirement` run; the OQ-B strategy pass. Wrote
`proposals/m2s2-llm-router-budget-cap.md` (type `proposal`, `status: proposed`) — a full nine-layer +
nine-station pass on M2.S2 (paid adapters + `LLMRouter` + per-call cost tracking + emergency daily
budget cap + status endpoint), grounded in spec §6.5/§6.6 (referenced, not restated), and carrying in
the two review risks (OQ-6 consent-vs-egress, OQ-7 return-shape + cap-ordering) + the stale ADR 0001.

- **Data flow** drawn as Mermaid (route → egress-gate → budget guard → provider → failover → record).
- **New state machine sketched:** the LLM-call lifecycle (`requested → guarded → {refused |
  dispatched} → {succeeded | retrying | exhausted | fatal}`), guard = egress-gate + cap, effect = a
  usage row on **every** terminal edge incl. refusals. Candidate for the vault's first
  `state-machines/` note.
- **Decision register D1–D6** (all open, mirrored to `open-questions.md` OQ-8): budget-knob grain;
  SDK-vs-httpx; cap atomicity (TOCTOU); one usage table / two billing units; paid-egress enablement
  gate; ADR-0001 reconciliation. **Proposed, not resolved; no ADR authored.**
- **Proposed temporary INV-9** (no paid egress without an enablement gate, M2-scoped like INV-8) and
  two invariant *clarifications* (INV-5 best-effort-with-bounded-overshoot; INV-7 tier must be
  system-derived) — folded into `invariants.md` only on acceptance, not yet.
- **Gaps for PO:** G1 quota-exhaustion decision (+ flagged a live **intra-spec** contradiction: §6.5
  step 5 "degrade to local_small" vs the §6.5 GPU-less-host paragraph "local_small impractical" — may
  need a one-line spec amendment via the stop-and-amend flow), G2 egress posture, G3–G6.
- **Glossary +2** → 16: [[failover]], [[toctou]]. Learning-log +3. INDEX regenerated (proposals/reports
  section added; next-steps 1–2 marked done). **No production code written** (design artefact only).

## 2026-06-02 — `review-architecture` (OQ-A drift sweep, M0→M2.S1 + ADRs 0001–0002)

First live `review-architecture` run; the OQ-A sweep the operator queued. Wrote
`reports/2026-06-02-architecture-review.md` (type `review`). Headline: the **vault** is honest
(as-built-vs-planned already separated) — the drift is **ADR-0001-vs-reality** plus **invariant
guards that lag their risk by 1–3 sessions**. No blockers; 2 risks for M2.S2 planning.

- **Drift / source-of-truth / stale-ADR (one fact, three hats):** ADR 0001's Consequences still say
  "quota exhausted → degrade to local_small", contradicted by the Session-3 GPU-less-host decision
  (spec §6.5 amended; OQ-3). Proposed (human decides): annotate ADR 0001 or mint a superseding ADR —
  not authored.
- **Invariant audit (the explicit ask):** INV-1/3/4/8 honest; INV-2 **risk** (paid egress in M2.S2,
  consent UI not until M2.S5 → OQ-6); INV-5 **risk** (`CompletionResult` discards Ollama token
  counts; cap-ordering unenforced → OQ-7); INV-6 **watch** (verify the named log-redaction
  middleware exists before paid adapters log); INV-7 **watch** (`model_tier` caller-asserted).
- **Structural:** slug/filename case mismatch (`PROJECT.md`/`CHANGELOG.md` vs lowercase slugs)
  corroborates Issue #31; `[[note]]` is a benign format-placeholder; no true orphans.
- **Trail:** OQ-6 + OQ-7 added to `open-questions.md`; 4 concepts appended to `learning-log.md`
  (outbox/saga, fail-closed sequencing, provenance, ADR lifecycle). **No code or config touched.**
  The two risks feed the same-session `decompose-requirement` pass on the M2.S2 router + budget cap.

## 2026-06-02 — `initialize-project-architecture` (first run, seed)

First live use of the meta-architect plugin on Story Forge. Created the vault at
`architecture/` (committed to git, per the init interview). Scaffolded:

- `PROJECT.md` — identity, personas/trust (single local user; the only trust boundary is machine ↔ LLM provider), business (personal tool + public portfolio, equal weight), source-of-truth registry, calibration (operator: novice → Scaffolded tier; both readers).
- `overview.md` — nine-layer system-altitude seed pass, grounded in the as-built present (M0→M2.S1 done; M2.S2+ planned); nine-station snapshot with empty boxes named (Monitoring not-yet-built, Expiry gap).
- `invariants.md` — 8 named invariants (INV-1 human-in-the-loop, INV-2 text-egress consent, INV-3 reversibility, INV-4 open-world types, INV-5 budget cap, INV-6 secrets/log redaction, INV-7 one-adapter-per-protocol, INV-8 temporary M2 no-dedupe).
- `open-questions.md` — operator priority queue (review-then-strategize), 5 vault-raised gaps (two-store consistency, ingest recovery, quota-exhausted UX, retention/Expiry, extraction injection pass), and a reference (not copy) to spec §10's ten questions.
- `glossary/` — 14 seed term notes + regenerated `glossary.md` index (trust-boundary, invariant, state-machine, fail-closed, human-in-the-loop, idempotency, open-world-ontology, source-of-truth, c4-model, agent, cascade-matching, model-tier-routing, compliance-audit-layer, prefer-deterministic).
- `learning-log.md` — 14 lines, one per concept taught this run.
- `INDEX.md` — regenerated vault map.
- Empty dirs (with `.gitkeep`): `decisions/`, `components/`, `state-machines/`, `proposals/`, `reports/`.

No production code touched. No ADR written (none confirmed). Sources of truth referenced, not
duplicated: `story-forge-poc-spec.md`, `docs/PLAN_*.md`, `docs/decisions/`, the seven
`AGENTS.md` files, the code.

**Review fold (same day, PR #30):** Codex flagged that `glossary/model-tier-routing.md` said
the router was "Built in M2.S2" while `overview.md` correctly lists M2.S2 as planned and the
repo has only `adapters/llm/{base,ollama}.py`. Reworded to "Planned for M2.S2 … not yet built".
Swept the whole vault for the same tense-overclaim class — this was the only instance.

**Review fold 2 (same day, PR #30, Codex second pass):** folded 5 findings — all valid.
- *No-duplication (2):* `overview.md` Layer 4 was restating the §6.4 schema (table names,
  `vector(768)`, node/relationship shape) → trimmed to the architectural *reading* of the
  two-store split, schema referenced to §6.4 + `infra/neo4j/init.cypher`. `cascade-matching.md`
  was restating the §3.3 staged algorithm → trimmed to the cheapest-first / fail-closed
  *force*, contract referenced to §3.3.
- *Tense/enforcement honesty (2):* `PROJECT.md` Identity present-tense described unbuilt
  extraction/graph features → reframed as target-V1 with an as-built note. INV-2 claimed
  router/consent-UI enforcement that isn't built → split into today's guard (no-telemetry + one
  Ollama adapter) vs planned (M2.S2/M2.S5), matching INV-1's honesty.
- *Registry accuracy (1):* the data-model source-of-truth row implied Alembic owns the graph
  schema; split into relational (Postgres → §6.4 + Alembic) and graph (Neo4j → §6.4 +
  `infra/neo4j/init.cypher`).
- *Class sweep:* the systematic per-invariant guard audit is routed to OQ-A (the queued
  `review-architecture` drift sweep) rather than half-done here. Operating boundary set: Codex
  is review-only (runs host-Windows over a UNC view; no edits, to avoid cross-env artifacts).

## 2026-06-11 — `review-architecture` (M2→M3 roll catch-up + forward sweep)

Run at the M2→M3 milestone boundary (gate 2 of the roll). The last sweep
(`2026-06-09-architecture-review`) predated **M2.S5** (PR #51) and **M2.S6** (PR #53), so the
update-in-place notes lagged two merged sessions.

- **New report:** `reports/2026-06-11-architecture-review.md`. No blockers. One `risk` on a security
  invariant: **INV-2's consent gate was deferred (ADR 0003 D5) with M2.S5 as its landing spot, and
  M2.S5 shipped without it** — the gate is now unscheduled and the M2.S6 smoke fired real paid egress
  gate-less (the OQ-6 window, now realised; accepted at PoC scale but the schedule is stale). Other
  drift is freshness: `overview.md` two sessions stale (header "M0 → M2.S3", M2.S5/S6 under "planned");
  INV-5/OQ-9 latency still future-tensed though `latency_ms` is built (M2.S5, migration
  `2026_06_11_0956…`); INDEX "Next: M2.S5".
- **`open-questions.md`:** added **OQ-14** (§6.5 model-override dropdown vs INV-7 — framed, likely
  future ADR) and **OQ-15** (operational logging absent ⇒ INV-6 vacuously true — framed). This
  discharges the `docs/PLAN_SHORT.md` cross-cutting "reflect the M2→M3 roll decisions in the vault"
  item. `updated` → 2026-06-11.
- **`learning-log.md`:** +3 lines — vacuous truth; accepted deferral vs silent drift; temporary-
  invariant hand-off (INV-8→INV-1).
- **`INDEX.md`:** regenerated — M2.S5/S6 done, M3 next, this report + OQ-14/OQ-15 registered.
- **Recommended (report-only, not applied this sweep) for the decompose step-0 to fold:** re-point
  INV-2's consent gate; flip INV-5/OQ-9 latency to as-built; refresh `overview.md` to M2.S6/M3. Source
  notes `overview.md` / `invariants.md` left unedited per report-only discipline.

## 2026-06-11 — `decompose-requirement` (M3 cascade, step-0)

M2→M3 roll gate 2, part 2: the forward-design pass on M3 — the §3.3 cascade dedupe — before any code.

- **New proposal:** `proposals/m3-cascade-matching.md` (`status: proposed`, register OPEN). Nine-layer +
  nine-station pass; Mermaid data-flow; the candidate-lifecycle state machine; an 8-entry decision
  register (DM1–DM7 + DM-rej); a but-what-if pass (intra-batch dupes, review-gate TOCTOU, fail-closed
  embedding/judge outages, relation re-pointing on merge, rejected-candidate re-surfacing); gaps for the
  PO. Central fork flagged: **DM6** — matching *gates* the write (intercept-before-write, my strong
  proposal) vs dedupe-after — which decides whether **INV-8 is replaced or layered**.
- **New state machine (the vault's first):** `state-machines/candidate-lifecycle.md` (`status: draft`) —
  `extracted → {auto-merge|ambiguous|new}-proposed → judged → review-queued → (human) →
  {merged|created|rejected}`; the commit guard *is* INV-1; every terminal edge writes `edit_history`
  (INV-3).
- **Freshness fixes folded** (the 2026-06-11 review's recommendations, applied because they're honest
  as-built corrections independent of the open M3 register): `invariants.md` INV-2 (consent gate
  re-pointed from the lapsed M2.S5 → M3 review-queue UI + the "real paid call fired gate-less" as-built
  note) and INV-5 (`latency_ms` → as-built M2.S5); `open-questions.md` OQ-9 → built; `overview.md`
  header → M0→M2.S6, M2.S5/S6 into built, planned → M3, Monitoring station → ✅.
- **`open-questions.md`:** added **OQ-16** (the M3 register pointer). **`learning-log.md`:** +2 lines
  (cheapest-first cascade; gate-the-write vs dedupe-after). **`INDEX.md`:** regenerated.
- **Nothing resolved.** Register stays OPEN; no invariant folded into `invariants.md` beyond the
  freshness fixes; no ADR drafted (awaits the owner's DM6/DM2 calls). First code: `MatchingAgent` Stage 1
  (RapidFuzz), failing test first with the App. B "Bronek/Bronisław" fixture.

## 2026-06-15 — review-architecture sweep (M3.S3 merged → entering M3.S4)
- **`reports/2026-06-15-architecture-review.md`:** new dated sweep. Findings: A1 DM5 resolved-but-framed-open
  (risk), A2 `task_type` label drift `"judging"`→`"judge"` (watch), A3 `overview.md` snapshot predates
  M3.S1–S3 (risk), A4 §3.3 confident-yes merge-rule shorthand (watch); B1–B3 the section-B owner
  resolutions (INV-2 deferred past M3, DM-rej remember, M3.S4 re-slice) reported pending PLAN_SHORT;
  C1–C4 S4a-bound (ADR 0004 fuller-MADR, gate-less Stage-3 egress, staging Expiry, store-chatty cascade).
- **Folded (as-built/already-authoritative drift only):** `proposals/m3-cascade-matching.md` — DM5 → ✅
  (PR #60), `"judging"`→`"judge"`, §3.3 confident-yes edge label; `open-questions.md` — OQ-16 DM5 struck,
  label fixed, DM7/DM-rej noted resolved-2026-06-15-pending-record; `overview.md` — snapshot moved to
  M3.S1–S3-built-proposal-only + S4a/S4b. `updated:` bumped on all three.
- **Reported, NOT written (authority lands at this session's wrap):** INV-2 re-point in `invariants.md`,
  DM7/DM-rej body strikes, the re-slice in PLAN_SHORT — the vault must not get ahead of its source of truth.
- **Nothing resolved unilaterally.** INV-8 correctly still live `[TEMPORARY]` (the flip is S4a's, test-first).

## 2026-06-15 — decompose-requirement: M3.S4a intercept-before-write (step-0)
- **`proposals/m3s4a-intercept-write-path.md`:** new step-0 decompose of the **backend** half of the
  milestone-closing session (UI is S4b). Designs the DM6 write-path refactor: a new Postgres `candidates`
  staging table, the cascade wired synchronously into the coordinator (embed-on-extract → Matching →
  Judge), Neo4j + `entity_mentions` writes moved to a human-accept endpoint; **INV-8 retired → INV-1
  enforcer** (+ proposed **INV-9**), test-first (the failing test replaces M2.S4's "two extractions → two
  nodes"). Nine-layer + nine-station pass; data-flow Mermaid; but-what-if (intra-batch dupes, review-gate
  TOCTOU, accept-path OQ-1 crash seam + status-flip-last idempotency, relation re-point on merge,
  rejected-as-default-suppression).
- **Open register OQ-17 / DM-S4a-1..5:** staging-table shape, INV-9 yes/no, resume marker under staging,
  **the evidence home** (focused `candidate_decisions` now vs full §4.2 `edit_history` — the main scoping
  call, may escalate to an ADR), retention. Mirrored to `open-questions.md`. ADR 0004 to author test-first.
- **Resolved inputs carried (not re-opened):** DM6 intercept-before-write, DM-rej remember rejections,
  INV-2 deferred past M3. `INDEX.md` regenerated. **Nothing resolved** — register stays open for the owner.

## 2026-06-15 — /review-pr §2 reconciliation folds (PR #62)
- The own-review §2 sweep found three decision-state homes lagging their now-recorded PLAN_SHORT
  decision. Folded: **`open-questions.md`** OQ-17 header `OPEN` → ✅ resolved (DM-S4a-1..5 struck);
  **`proposals/m3-cascade-matching.md`** → `status: accepted`, DM7/DM-rej register bodies + the Layer-1 /
  Layer-7 / Gaps-for-PO INV-2 mentions struck to Decision, register header `OPEN` → resolved;
  **`proposals/m3s4a-intercept-write-path.md`** → `status: accepted`, all five DM-S4a register entries +
  the Gaps-for-PO list struck to Decision, hand-off de-staled; **`invariants.md`** INV-2 schedule
  re-pointed from "M3 review-queue UI" to "deferred past M3" (the report B1 item, now due since PLAN_SHORT
  records it). Authoritative homes (PLAN_SHORT Decided S23) were already correct; this brings the vault
  framing-notes into agreement throughout their bodies, not just their banners.

## 2026-06-17 — `review-architecture` (M3→M4 roll re-sync)
- **New report** `reports/2026-06-17-architecture-review.md` (`type: review`) — full as-built sweep at
  the M3→M4 boundary, the first since edges + the relation lifecycle landed (S4b–S4f). No blockers.
  **Risk:** `overview.md` as-built snapshot ~5 sessions stale (lists the relation graph-write + the
  review UI as "planned, not yet built" — both shipped); the relation lifecycle has no state-machine
  note while its entity twin does. **Watch:** `invariants.md` frontmatter date lags its (correct) body;
  edge-id provenance collapse (carried ADR-0005 follow-up); held-relation visibility; M4 forward flags
  (§3.4 graph scoping graduates to live work; DM-Rel-5 re-point becomes real; OQ-14/OQ-15 still open).
  Source-of-truth conflicts: none. Missing ADRs: none (0004/0005 present; S4c/S4d ADR-declined on record).
- **`open-questions.md`** — added **OQ-20** (relation lifecycle has no state-machine note; the node/edge
  model asymmetry + held-relation visibility + edge Expiry sub-gaps); `updated` → 2026-06-17.
- **`learning-log.md`** — +2 lines (state-machine symmetry; provenance vs deduplication).
- **`INDEX.md`** — regenerated (priority queue advanced past S4f → M3 feature-complete; new report linked;
  glossary 22 terms; relation-lifecycle named under "still to draw").
- Report-only: no code or config touched.
- **`overview.md`** — folded the headline `risk` (decision-independent as-built drift, all merged basis,
  the same freshness-fold pattern as the 2026-06-11 sweep): the M3 block rewritten from "Stages 1–3 +
  S4a, S4b/relation-write planned" to **M3 feature-complete (S4b–S4f shipped, nodes + edges gated)**; a
  "Next — M4 (V1 polish)" block added naming the two M3-deferred seams that graduate to live M4 work
  (§3.4 graph scoping; DM-Rel-5 written-edge re-point); `updated` → 2026-06-17. The un-drawn relation
  lifecycle stays a *reported* gap (OQ-20) — drawing a state machine is decompose work, not a review fold.

## 2026-06-17 — `decompose-requirement` (M4 first slice: inline highlights)
- **New proposal** `proposals/m4-inline-highlights.md` (`type: proposal`, `status: proposed`) — step-0
  nine-layer + nine-station forward pass on M4.S1 (spec §3.5). Centre of gravity: **span resolution** —
  accepted `entity_mentions` carry null char offsets, so highlighting is a where-does-the-entity-sit
  problem (DM-IH-1), not a render of stored spans. Read-only projection ⇒ most stations n/a, INV-1/9
  untouched (carries only the read-side "highlight accepted-only" rule). 8-entry register (DM-IH-1..8,
  all OPEN), Mermaid data-flow, a but-what-if pass (PL inflection, repeat-occurrence granularity,
  rejected/merged dangling refs, 50k-word perf, overlap), gaps-for-PO. Surfaces the M4 entity↔entity
  merge → mention/edge re-point coupling from a new direction.
- **`open-questions.md`** — added **OQ-21** (the DM-IH register mirror, DM-IH-1 the central call);
  `updated` → 2026-06-17.
- **`learning-log.md`** — +2 lines (span resolution / the null-offset gap; read-only projection &
  n/a stations).
- **`INDEX.md`** — regenerated (proposal linked; priority queue advanced to M4.S1).
- Register stays **OPEN** — the owner resolves DM-IH-1..8 before code (the decompose never self-resolves).

## 2026-06-20 — `review-architecture` (pre-M4.S3b re-sync; owner-requested before the S3b decompose)
- **`reports/2026-06-20-architecture-review.md`** (new) — full vault sweep since the 2026-06-17 M3→M4
  roll. **No blockers.** One `risk`: `overview.md` as-built stopped at M3 (named every M4 slice as
  "Next" though M4.S1/S2/S3a all shipped) — **fixed on sight**. Three `watch`: state/invariant
  frontmatter dates lagged current bodies (**bumped**); `m4-entity-editing` read build-pending though
  M4.S3a is complete (**BUILT banner**); INDEX item 21 stale (**regenerated**). The invariant/lifecycle
  layer (INV-9 rewording, candidate/relation edit-path extensions, ADR 0006, OQ-23) was already honest —
  folded at the S36 decompose + S37 build. Forward "what if" over the S3b boundary: compound-undo
  before-image granularity (a merge is N writes → needs a grouped before-image), MERGE-collision on edge
  re-point, the `entity_mentions.entity_id` re-point cross-store seam — inputs to the S3b decompose.
- **`overview.md`** — update-in-place: added a *Built (M4 so far)* block (S1 highlights / S2 side panel /
  S3a editing-the-first-write-slice, ADR 0006, INV-9 reworded) and reduced "Next" to M4.S3b → S3c →
  multi-story/§3.4 → world graph; `updated` → 2026-06-20.
- **`invariants.md`, `candidate-lifecycle.md`, `relation-lifecycle.md`** — frontmatter `updated` → 2026-06-20
  (bodies already carried the M4.S3a / M3.S4e content; only the freshness stamp lagged).
- **`m4-entity-editing.md`** — BUILT banner appended (be #96 / fe #98, ADR 0006, the `language` read-side
  deviation), pointing forward to S3b; `updated` → 2026-06-20. Status stays `accepted` (a proposal has no
  "built" status).
- **`open-questions.md`** — recorded the S3b forward "what if" against the coming decompose (no new OQ
  minted — the S3b `decompose-requirement` creates the DM-S3b register); `updated` → 2026-06-20.
- **`learning-log.md`** — +1 line (compound/transactional undo — a merge is one action but many writes).
- **`INDEX.md`** — regenerated (2026-06-20 report added as current snapshot, 2026-06-17 marked superseded,
  m4-entity-editing summary → BUILT, next-steps item 22 = M4.S3a built + S3b next).
- Report-only; no code or config touched.

## 2026-06-20 — `decompose-requirement` (M4.S3b — graph mutations: merge · delete · undo)
- **`proposals/m4-s3b-graph-mutations.md`** (new) — step-0 forward design for the slice
  [[m4-entity-editing]] named at its seam. Nine-layer + nine-station pass; **operation-surface
  completeness sweep** over CRUD-of-{entities,relations,mentions} **closes** (every op homed — S3b owns
  entity delete + entity↔entity merge (which contains edge re-point + mention re-point) + mention
  delete-on-delete + undo execution; tag/boundaries → S3c, split/qualifiers → post-PoC). Mermaid
  data-flow, "but what if" pass, gaps-for-owner. **Register OPEN — DM-S3b-1..8**, central call
  **DM-S3b-1** (undo scope + the `graph_edits` grouping — a merge is one action/N writes, the per-row
  S3a log can't group it; proposed: a grouped append-only log = a compensating transaction, which also
  resolves spec §10 q2). **DM-S3b-2/5 flagged spec-silent** (merge + delete semantics) → a likely
  §3.4/§3.5 stop-and-amend before code. `status: proposed` — the decompose never self-resolves.
- **`open-questions.md`** — added **OQ-25** (the DM-S3b register mirror); OQ-24 (the 2026-06-20 report's
  pre-decompose forward note) marked superseded by it.
- **`glossary/compensating-transaction.md`** (new term, #26) — saga-style undo for a multi-write
  operation with no shared transaction; the pattern behind DM-S3b-1's grouped before-image.
- **`learning-log.md`** — +1 line (compensating transaction / saga undo); `updated` -> 2026-06-20.
- **`INDEX.md`** — regenerated (proposal row added; glossary 25->26 + compensating-transaction;
  next-steps item 23 = M4.S3b decomposed, register open).
- Register stays **OPEN** — the owner resolves DM-S3b-1..8 (incl. the spec amendments) before any code.

## 2026-06-22 — M4.S3c step-0 decompose (manual tag / un-tag / change-boundaries)

`decompose-requirement` over the **final slice** of "manual correction in the reader" (S3a · S3b · **S3c**;
spec §3.5). Centre of gravity = the **span-storage model** (DM-S3c-1): today a rendered highlight is a
render-time *search hit with no identity* (DM-IH-1; `entity_mentions` spans NULL/unused), so manual spans
can't be re-found by search and un-tagging acts on a highlight with no row to delete.
- **`proposals/m4-s3c-manual-tagging.md`** — new (`status: proposed`, register **OPEN** DM-S3c-1..9). Nine
  layers + nine stations (first *write* stations of the reader's **mention** layer; Evidence/Review/Policy
  flip ✅), the completeness sweep (mention CRUD + entity-from-tag — **closes**, no slicing gap), a
  three-source reconciliation data-flow (search ∪ manual − suppressions), a 9-entry register, the "but
  what if" pass, and the gaps-for-PO.
- **`glossary/materialization.md`** — new term (derived projection → stored addressable record); the idea
  DM-S3c-1 turns on. Glossary 26 → 27.
- **`learning-log.md`** — +1 line (materialization: derived vs correctable-stored is a real boundary).
- **`open-questions.md`** — OQ-26 mirror (DM-S3c-1..9); `updated` → 2026-06-22.
- **`INDEX.md`** — regenerated (proposal row + glossary 27 + next-steps item 24).
- Register stays **OPEN** — the owner resolves DM-S3c-1..9 (incl. the §3.5/§6.4 amendment + INV-9 reword)
  before any code; likely **ADR 0008** at build.

## 2026-06-22 — M4.S3c register RESOLVED (owner, Session 44) + scope decisions

- **`proposals/m4-s3c-manual-tagging.md`** → `accepted`; register **RESOLVED** (resolution banner + each
  entry reconciled; hand-off + gaps-for-PO brought to resolved). DM-S3c-1 = **(B) overlay / save-only-
  what-you-touch**; DM-S3c-2 = both attach + create-new; DM-S3c-7 = **Tiptap now (owner override)**;
  tag/un-tag/boundary ride the S3b undo; split be/fe; no §3.5 capability amendment (ADR 0008 + INV-9
  reword + a small §6.4 note at build).
- **`open-questions.md`** — OQ-26 struck ✅ with the per-entry resolutions.
- **`INDEX.md`** — proposal row + next-steps item 24 flipped to RESOLVED.
- **Scope decisions (host-repo homes — recorded, not vault):** world-graph multi-story → `docs/BACKLOG.md`
  (out of PoC; reversed the prior "in-PoC" note); narrowed multi-story-in-a-project stays in PoC
  (`docs/PLAN_SHORT.md` Decided S44, concretizes §3.4 scoping; §3.6/§9 stop-and-amend pending);
  code-doc-generation → backlog.
- **Next:** build M4.S3c-be test-first from the pure reconciling-resolver function.

## 2026-06-26 — Graph-quality S0 decompose: the in-place curation surface (register OPEN)

- **`proposals/graph-curation-surface.md`** (NEW, `proposed`) — step-0 decompose of "the graph view as a
  direct in-place curation surface" (`docs/specs/graph-quality.md` §3 S0). Nine-layer pass + stations +
  operation-surface completeness sweep + data-flow + decision register **DM-GQ-1..7 (OPEN)** + "but what
  if" + slice boundaries for S3. **Defining finding:** the write plumbing already exists
  (`EntityEditService` edit/merge/delete/undo, M4.S3a/S3b) — only on the *reader's* panel, not the graph
  canvas — so S3 is a UX-surfacing job, with **one** net-new write (predicate consolidation) and **one**
  modelling call: the **§4 edge-addressability** decision (content-addressed `uuid5` edge id vs a stable
  [[surrogate-key]] handle for future [[reification]]). Proposed slice cut: **S3a** node writes → **S3b**
  edge writes (on S2's panel) → **S3c** consolidation + the §4 handle.
- **`glossary/surrogate-key.md`** + **`glossary/reification.md`** (NEW) — the two concepts the §4 call
  rests on; glossary index 28 → **30**.
- **`learning-log.md`** — two lines (surrogate-vs-natural key; reification = design-constraint-now).
- **`open-questions.md`** → OQ-29 added (the DM-GQ-1..7 register + the §4 call); `updated` bumped.
- **`INDEX.md`** — proposals table row + glossary list + next-steps regenerated.
- **Register stays OPEN.** No ADR (no confirmed decision yet); no production code (S0 is a design slice).
  **Next:** owner resolves DM-GQ-1..7 (DM-GQ-1 §4 + DM-GQ-2 consolidation gate S3c); then S1 (test-first).

## 2026-06-26 — Graph-quality S0 register RESOLVED + milestone reshaped (owner, Session 69)

- **`proposals/graph-curation-surface.md`** → `accepted`; register **RESOLVED** (top resolution banner +
  per-entry `✅ Decision` banners DM-GQ-1..7; original forward-design body kept as history). **DM-GQ-1 §4 =
  reserve a stable `edge_uid` handle now** (content id stays the dedup key per ADR 0005; the surrogate is the
  addressable hook for future [[reification]]; build no feature; ADR at build). **DM-GQ-2 reframed (owner) →
  predicate-*name normalisation*, not edge-joining**, + an NLP/embedding *suggest* layer. **Two owner
  additions promoted from `docs/BACKLOG.md`:** a proactive **entity dedup-suggest** pass over the accepted
  graph, and **navigation pulled early + a layout algorithm**. DM-GQ-3 = editable panel + right-click;
  DM-GQ-4/5 confirmed; DM-GQ-6 = the reshaped order; DM-GQ-7 bulk → backlog.
- **`open-questions.md`** — OQ-29 struck ✅ with the per-entry resolutions.
- **`INDEX.md`** — proposal row + next-steps item 28 flipped to RESOLVED/reshaped.
- **Host-repo reconciliation (recorded, not vault):** `docs/specs/graph-quality.md` amended (§3 reshaped
  slices S1–S7, §4 the edge-handle decision, §5 the curation-time-suggest boundary, §6 criteria, §8 the
  suggest passes); `docs/PLAN_SHORT.md` task list reshaped + Decided S69; `docs/BACKLOG.md` two items marked
  PROMOTED (graph-traversal discovery → S4, predicate proliferation → S6).
- **Next:** **S1** (auto-chunker completeness check) — the first *build* slice, test-first, independent of
  this register. The §4-handle **ADR** + the S4 dedup-suggest **step-0** draft at their build.

## 2026-06-29 — Graph-quality S2 decompose: navigate the graph (register OPEN, Session 72)

- **`proposals/graph-navigation.md`** (NEW, `proposed`) — step-0 decompose of the branchy S2 navigate slice
  (`docs/specs/graph-quality.md` §3 S2): §3.4 filters (type / connection-density / story) + node search by
  name + a better layout algorithm. Nine-layer pass (Concise) + stations (most honestly `n/a` — read-only,
  no gated action) + operation-surface completeness sweep + data-flow Mermaid + decision register
  **DM-GN-1..4 (OPEN)** + "but what if" + hand-off build plan. **Read-only, frontend-led** → INV-1/3/9
  untouched; INV-4 constrains the type filter (derive options from data, never a closed enum).
- **Defining finding (completeness sweep):** every §3.4 filter runs **client-side over the payload
  `useStoryGraph` already fetches** — `GraphNode` carries `type`+names+aliases, node degree derives from
  `edges[]`, and the "by story" axis is *already shipped* as the binary `scope` toggle (DM-MS-2). So
  DM-GN-1 leans **no new backend/endpoint**. DM-GN-2 = one layout dep (lean `cytoscape-fcose`,
  `verify-at-build` the pin via `/add-dependency`). DM-GN-4 = AND-combine + hide-and-relayout + search-as-focus.
- **Surfaced a real spec↔vault conflict (DM-GN-3):** spec §3 places the **edge-tap evidence panel in S3**,
  but the *accepted* parent `[[graph-curation-surface]]` (operation sweep, lines 110/120-122) asserts it is
  **S2's**. Per `architecture/AGENTS.md` (*the source wins; the vault is what drifted*) the lean is
  spec-faithful (S3 owns the edge panel; reconcile the parent-proposal note) — flagged as the owner's
  boundary to draw, **not** corrected unilaterally. A reconcile of the parent note is owed either way.
- **`open-questions.md`** — OQ-30 added (mirrors DM-GN-1..4); `updated` 2026-06-29.
- **`INDEX.md`** — `graph-navigation` proposal row + next-steps item 29; `updated` 2026-06-29.
- **Next:** owner resolves DM-GN-1..4 (one plain-language question at a time, **DM-GN-3 first** — it sizes
  the slice), then build S2 test-first from the pure filter/degree/search functions; `/add-dependency` for
  the layout extension at the canvas step. No ADR anticipated.

## 2026-06-29 — Graph-quality S2 register RESOLVED (owner, Session 72)

- **`proposals/graph-navigation.md`** → `accepted`; resolution banner + every register entry rewritten
  *My proposal → Decision*, rejected options de-activated, gaps-for-PO closed. **DM-GN-1 = (a) client-side**
  filtering over the existing payload (no new backend; reuse the binary `scope` toggle; finer N-story filter
  deferred-as-YAGNI). **DM-GN-2 = `cytoscape-fcose`** (pin via `/add-dependency`, `verify-at-build` the
  version). **DM-GN-3 = (a) spec-faithful — S2 navigation-only; the edge-tap evidence panel stays S3.**
  **DM-GN-4 = AND-combine + hide-and-relayout + search-as-focus.** No spec amendment; no ADR.
- **Drift reconciled (DM-GN-3) — the parent `[[graph-curation-surface]]` "edge panel is S2's" claim.** Per
  `architecture/AGENTS.md` (the spec wins; the vault is what drifted), the parent proposal's §3
  operation-sweep table + routing note 1 (it had asserted the spec puts edge-tap in S2) are corrected to
  **S3** with a dated pointer to DM-GN-3; the DM-GQ-3 interaction-model option, the DM-GQ-6 context, the
  plain-language Q4, and the OQ-29 body cross-refs were likewise fixed ("S2's edge panel" → "the S3
  edge-evidence panel"). The explicitly-"kept for history" superseded blocks are left intact, covered by
  the dated supersession note. One small spec §4 wording nit (spec §4's "S2's edge surface"
  forward-reference read off, since S2 has no edge surface) was **fixed with owner OK 2026-06-29** → the §4
  header + line now read "respected by the S3+ edge slices" (the §4 *constraint* is unchanged).
- **`open-questions.md`** — OQ-30 struck ✅ with the per-entry resolutions; the OQ-29 body cross-ref fixed.
- **`INDEX.md`** — `graph-navigation` row → ACCEPTED/RESOLVED banner; next-steps item 29 → resolved.
- **Host-repo reconciliation (recorded, not vault):** `docs/PLAN_SHORT.md` Decided S72 records the
  resolution (authoritative decision home). `docs/specs/graph-quality.md` §4 carries the small wording fix
  above (owner-approved); no other spec change (decision A keeps S2 aligned with §3).
- **Next:** build **S2** test-first (frontend-led, read-only) from the pure filter/degree/search functions;
  `/add-dependency` for `cytoscape-fcose` at the canvas step.

## 2026-07-01 — Graph-quality S3 decompose (Session 74)

- **`proposals/graph-edge-evidence.md`** (NEW, `type: proposal`, `status: proposed`) — step-0 forward
  design of `docs/specs/graph-quality.md` §3 **S3** ("Edge evidence + verifiable merges"). Register OPEN
  **DM-EE-1..6 / OQ-31**. **Defining finding:** S3 is a *read/verify* slice whose data is real but not on
  the wire — edge [[provenance]] survives commit in `staged_relations` (keyed by the content-addressed
  `edge_id`) but reaches no client and has no by-`edge_id` read/index (`postgres_relation_store.py:94-112`);
  the graph viewer has no edge-tap (`GraphCanvas.tsx:106`, node-only); the merge surfaces show a bare
  `(100)` score + a generic "an existing entity" (`CandidateCard.tsx:75-81,131-132`, no
  `target_canonical_name`). So S3 needs a small set of new **read** surfaces (a focused edge-evidence BFF
  read + merge-context enrichment), **not** new storage and **not** the §4 write-handle. **S3 writes
  nothing** — INV-1/INV-3/INV-9 untouched; INV-4 constrains DM-EE-4 (no closed enum of "group" types).
  Register: DM-EE-1 delivery (focused BFF vs payload-enrich), DM-EE-2 provenance source (one-to-many
  `staged_relations` vs single Neo4j property), DM-EE-3 merge-context enrichment (closes the cross-cutting
  `CandidateView`-no-target-name item), DM-EE-4 the score-100 trap (context not type-classification),
  DM-EE-5 dup-create gate (client-side vs backend), DM-EE-6 slice cut (backend-first / frontend-second).
- **Handoff correction recorded (OQ-31 + the proposal's State & invariants):** the Session-73 handoff read
  "S3 consumes the reserved §4 edge handle for addressing"; code-verified there is **no** surrogate handle
  built yet — the edge id *is* the content-addressed `uuid5` — and S3 addresses edges by it for a *read*
  (stable because S3 writes nothing). The §4 handle is an edge-*write* concern (S5/S6, DM-GQ-1). To be
  reconciled in `docs/PLAN_SHORT.md` at wrap.
- **Glossary 30 → 31:** added **[[provenance]]** (source-text trail, one-to-many; cousin of
  [[compliance-audit-layer]]). `learning-log.md` + `glossary/glossary.md` index updated.
- **`open-questions.md`** — OQ-31 appended (register OPEN, mirrors the proposal). **`INDEX.md`** regenerated
  (proposal row + next-steps item 30 + glossary count/list).
- **No ADR, no spec amendment anticipated** (S3 reads what §3 S3 already scopes). Next: the owner resolves
  DM-EE-1..6 (plain-language "Gaps for the product owner" in the proposal), then the S3 build starts
  backend-first, test-first.
