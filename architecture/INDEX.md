---
type: index
slug: index
updated: 2026-07-13
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

## Glossary (36 terms — see [[glossary]])
[[trust-boundary]] · [[invariant]] · [[state-machine]] · [[fail-closed]] ·
[[human-in-the-loop]] · [[idempotency]] · [[open-world-ontology]] · [[source-of-truth]] ·
[[c4-model]] · [[agent]] · [[cascade-matching]] · [[model-tier-routing]] ·
[[compliance-audit-layer]] · [[prefer-deterministic]] · [[failover]] · [[toctou]] ·
[[prompt-injection]] · [[poison-message]] · [[software-composition-analysis]] ·
[[defense-in-depth]] · [[intra-batch-dedup]] · [[referential-integrity]] · [[ego-graph]] ·
[[backend-for-frontend]] · [[lost-update]] · [[compensating-transaction]] · [[materialization]] ·
[[multi-tenancy]] · [[surrogate-key]] · [[reification]] · [[provenance]] ·
[[entity-resolution]] · [[connected-components]] · [[blocking]] · [[direct-manipulation]] ·
[[controlled-vocabulary]]

## Proposals & reports
| Note | Type | What |
|---|---|---|
| [[graph-name-normalisation]] | proposal | **Graph-quality S6 — predicate- AND entity-type-name normalisation + synonym suggestion (✅ ACCEPTED, register RESOLVED DM-NN-1..6 / OQ-34, owner Session 91)** — **Resolved (each as proposed):** DM-NN-1 shared suggest / forked apply · DM-NN-2 fuzzy + label-string embeddings, recall-first, `name_normalise_suggest_floor` knob · DM-NN-3 persist dismissals (reuse S4 / ADR 0010; no fresh ADR) · DM-NN-4 loop the shipped `plan_relation_rekey` graph-wide in one grouped op (preserve `edge_uid`, fold-report) · DM-NN-5 new bulk `SET n.type` relabel (INV-9 +1 path) · DM-NN-6 dedicated `/stories/:id/normalise-names` list, both vocabularies together, backend-first. — step-0 for `docs/specs/graph-quality.md` §3 **S6** (+ §4, §6). One human-gated **"suggest, then you decide"** naming-normalisation pass over **two** open-world vocabularies: relationship **predicate** names (`PASSENGER_ON`→`ON_SHIP`) *and* entity-**type** labels (`PERSON`/`Person`, `GROUP`/`group`/`GROUP_OF_PERSONS`, …; scope extended to types by the owner, Session 81). An NLP/embedding layer *suggests* synonyms; the human renames graph-wide; predicates/types stay free strings (**INV-4** — nothing auto-collapses); identical-triple collapses on a predicate rename are *reported*, never the goal; the rename carries the §4 `edge_uid` handle (**INV-10** — S6 is the near-term consumer S5 predicted). **Defining finding (answers the task's "one engine or two" at the *storage* layer):** a predicate **is** the Neo4j *relationship type* inside the content-addressed `relation_edge_id`, so renaming it **re-keys every bearing edge** (reuse the S5b `plan_relation_rekey`, preserve `edge_uid`, fold identical triples); an entity type **is** a node *property*, so renaming it is a **bulk `SET n.type`** (no re-key, no handle, no collapse). So S6 = **one shared SUGGEST engine + two forked APPLY paths** — the suggest math + review list are genuinely shared; the apply forks by storage model. A second finding: unlike S4's entity dedup (surface-similar names), S6's synonyms are often fuzzy-*distant* but semantically close (`PASSENGER_ON`↔`ON_SHIP`), so the **embedding rung earns its place more than in S4** — and it embeds the *label string itself*, not mention vectors. Operation-surface sweep over {predicate-vocab, type-vocab} **closes** (the type-relabel is the one genuinely-new writer; bulk/multi-select → BACKLOG, blocking/LSH not even needed at tens-of-labels scale). Register (RESOLVED, owner Session 91 — each on the proposed lean; see the **Resolved:** summary above): **DM-NN-1** shared suggest / forked apply · **DM-NN-2** fuzzy + label-embeddings, recall-first, a `name_normalise_suggest_floor` knob · **DM-NN-3** persist dismissals (the S4 DM-CD-3 / ADR 0010 pattern; no fresh ADR) · **DM-NN-4** predicate apply = loop the shipped S5b re-key in one grouped op at N-write scale · **DM-NN-5** type apply = one new bulk `SET n.type` relabel (the only net-new writer; INV-9 +1 path) · **DM-NN-6** dedicated list, be/fe with both surfaces together. Added [[controlled-vocabulary]] (glossary 35→36). **No spec amendment, no ADR anticipated** (§3 S6 already scopes both surfaces; the re-key/handle is ADR 0011's, the dismissal store ADR 0010's). **Next: build S6a test-first in a fresh conversation.** |
| [[graph-canvas-editing]] | proposal | **Graph-quality S5 — the graph as an in-place editing surface (✅ ACCEPTED, register RESOLVED DM-S5-1..6 / OQ-33, owner Session 80)** — step-0 for `docs/specs/graph-quality.md` §3 **S5** + §4; the milestone **spine**, branchy (S5a node / S5b edge per DM-GQ-6). Bring the existing node/edge write paths onto the graph canvas ([[direct-manipulation]]) — edit name/type/aliases/properties, merge, delete a node; edit / re-target / delete an edge — human gate + grouped undo intact (INV-1/9/3), reusing the reader's edit panel (DM-GQ-3). **Defining finding (two code-level surveys):** node-editing already ships end-to-end and is wired on the *reader* (`EntityEditService.{edit,merge,delete,undo}` + endpoints + `lib/api` hooks + `ReaderEntityPanel`/`MergeControls`, all invalidating the reader/story-graph/entity-detail triad) → **S5a is pure canvas-surfacing**; the *only* net-new plumbing is **edge-editing** — `edit-predicate`/`re-target` have **no atomic op** (only a client remove+add that **re-keys** the content-addressed `relation_edge_id = uuid5(subject,predicate,object)`), which is exactly why **S5b is the first edge-*write* slice and consumes the reserved §4 handle** ([[surrogate-key]], DM-GQ-1 — confirmed unbuilt; a client compose can't preserve a handle across the re-key, an atomic server op can). Operation-surface sweep over node+edge **closes** (node create-from-scratch deferred; bulk → BACKLOG; graph-wide predicate rename → S6). **Register RESOLVED (owner, Session 80):** **DM-S5-1** = **(B) extract a shared `EntityEditPanel` core** (reader + canvas both compose it) · **DM-S5-2** = **(B) atomic backend edge-edit op** (edit-predicate/re-target, one grouped reversible op preserving the §4 handle) · **DM-S5-3** = mint-forward + no-backfill, coalesce-on-MERGE, survivor keeps handle, **+ mint the "handle survives curation" invariant at the S5b build** (ADR-worthy, drafts at S5b build) · **DM-S5-4** = **DEFER right-click** (owner override — panel-only S5) · **DM-S5-5** = single S5a slice + fold the §4 tag into S5b-be · **DM-S5-6** = add the modest panel-vanish guard, LWW-at-PoC carried. Build cut: **S5a → S5b-be → S5b-fe.** Added [[direct-manipulation]] (glossary 34→35). **No `graph-quality.md` amendment, no ADR this session** (the §4 ADR is the S5b build's). **Next: build S5a test-first in a fresh conversation** (extract the shared panel + canvas node edit/merge/delete/undo + the panel guard). |
| [[graph-cluster-dedup]] | proposal | **Graph-quality S4 — Suggest duplicate clusters over the accepted graph (✅ ACCEPTED, register RESOLVED DM-CD-1..6 / OQ-32, owner Session 77)** — **Resolved:** DM-CD-1 pairwise · DM-CD-2 eager/recall-first (name+embeddings, ambiguous floor, deterministic) · DM-CD-3 **persist dismissals** (ADR at build) · DM-CD-4 dedicated list · DM-CD-5/6 S4a be / S4b fe, reuse the merge. — step-0 for `docs/specs/graph-quality.md` §3 **S4** (promoted from `docs/BACKLOG.md`, owner Session 69). Re-point the §3.3 cascade matcher **inward** — each accepted entity scored against the others (a **self-join** over the `AcceptedSnapshot`) — to **suggest** likely-duplicate entities; the human commits each merge through the **existing** `POST …/entities/{id}/merge`. **Suggests, never auto-merges** (INV-1/INV-9 hold; no egress/LLM; INV-4 keeps type a soft ranking signal, never a hard filter). **Defining finding: both halves already ship** — the matcher (`MatchingAgent` + `AcceptedEntityReader.load_accepted`, `_rank`/`cosine_similarity` pure & tested) *and* the merge commit path (`plan_merge` → `EntityEditService.merge_entities` → the merge endpoint) — so S4 adds only a *read/analysis* surface (the self-join) + a *review* surface, **no net-new graph write**; the entity twin of S6's predicate-name suggest. Register (all OPEN): **DM-CD-1** cluster model (pairwise *lean* vs transitive [[connected-components]] — trap: cluster drift) · **DM-CD-2** rungs + a recall-first *suggestion* floor (nothing auto-merges) · **DM-CD-3** dismissal memory (persist a "not a duplicate" — the [[intra-batch-dedup\|DM-rej]] precedent; **ADR-worthy**, adds a Postgres pair-store) · **DM-CD-4** a review-queue-like list (reuse S3 DM-EE-3 merge-context) · **DM-CD-5** S4a be / S4b fe split · **DM-CD-6** reuse-not-fork. Added [[entity-resolution]] + [[connected-components]] + [[blocking]] (glossary 31→34). **No spec amendment at decompose time** (the dismissal store is staging-side plumbing, not a §3 S4 scope change); the **DM-CD-3 ADR drafts at the S4a build**. **Register RESOLVED (owner, Session 77). Next: build S4a test-first in a fresh conversation.** |
| [[graph-edge-evidence]] | proposal | **Graph-quality S3 — Edge evidence + verifiable merges (✅ ACCEPTED, register RESOLVED DM-EE-1..6 / OQ-31, owner Session 74)** — step-0 for `docs/specs/graph-quality.md` §3 **S3**. **Owner resolved every entry on the leaned option (a):** DM-EE-1 focused per-edge BFF read (fetch-on-tap) · DM-EE-2 all `written` `staged_relations` by `edge_id` (+ index; zero-provenance → "added manually") · DM-EE-3 enrich all merge surfaces (type+aliases+quote+`target_canonical_name` — closes the cross-cutting `CandidateView`-no-target-name item at build) · DM-EE-4 solve by context not type-classification (INV-4) · DM-EE-5 client-side warn-and-offer · DM-EE-6 backend-first / frontend-second (amber fix rides S3b). A **read/verify** slice: click an edge → predicate + source sentence(s); each entity-merge option shows a context quote + type + aliases; three cheap safeguards (gate exact-name dup-create; don't privilege a score-100 exact-name match; fix the amber "merge target" highlight on *New* cards). **S3 writes nothing** → INV-1/INV-3/INV-9 untouched; no egress/LLM; INV-4 constrains DM-EE-4 (no closed enum of "group" types). **Defining finding: the data is real but not on the wire** — edge [[provenance]] survives commit in `staged_relations` (keyed by the content-addressed `edge_id`) but reaches no client and has **no by-`edge_id` read/index** (`postgres_relation_store.py:94-112`); `GraphCanvas` taps **nodes only** (`GraphCanvas.tsx:106`); the merge surfaces show a bare `(100)` + generic "an existing entity" (`CandidateCard.tsx:75-81,131-132`, no `target_canonical_name`). So S3 needs a small set of new **read** surfaces (a focused edge-evidence BFF read + merge-context enrichment) — **not** new storage and **not** the §4 write-handle. Register (all ✅ resolved, decisions in the banner above): DM-EE-1 delivery, DM-EE-2 provenance source, DM-EE-3 merge-context, DM-EE-4 the score-100 trap, DM-EE-5 dup-create gate, DM-EE-6 slice cut (the per-entry Context/Options/Decision live in the proposal). Added [[provenance]] (glossary 30→31). **Handoff correction:** the §4 surrogate handle is **not** built or consumed here (S3 reads by the content id; the handle is an edge-*write* concern, S5/S6). **No spec amendment, no ADR anticipated.** |
| [[graph-navigation]] | proposal | **Graph-quality S2 — Navigate the graph (✅ ACCEPTED, register RESOLVED DM-GN-1..4 / OQ-30, owner Session 72)** — the first *navigation* slice (`docs/specs/graph-quality.md` §3 S2): §3.4 **filters** (entity type / connection density / story) + **node search by name** + a **better layout algorithm** to spread the `cose` hairball (`GraphCanvas.tsx:36`). **Read-only, frontend-led:** writes nothing → INV-1/INV-3/INV-9 untouched (INV-4 constrains the type filter — derive options from the data, never a closed enum); no egress/LLM/[[trust-boundary]]. **Defining finding (completeness sweep): every filter runs client-side over the payload `useStoryGraph` already fetches** — `GraphNode` carries `type`+names+aliases, degree derives from `edges[]`, the "by story" axis is *already shipped* as the binary `scope` toggle (DM-MS-2). **Resolved (owner Session 72):** **DM-GN-1 = client-side** (no new backend; finer N-story filter YAGNI-deferred); **DM-GN-2 = `cytoscape-fcose`** (pin via `/add-dependency`); **DM-GN-3 = (a) spec-faithful — S2 navigation-only, the edge-tap evidence panel stays S3** (the parent [[graph-curation-surface]]'s "edge panel is S2's" claim was drift — reconciled in its §3 operation-sweep to S3); **DM-GN-4 = AND-combine + hide-and-relayout + search-as-focus.** No spec amendment; no ADR. **Next: build S2 test-first.** |
| [[graph-curation-surface]] | proposal | **Graph-quality S0 — the graph view as a direct in-place curation surface (✅ ACCEPTED, register RESOLVED DM-GQ-1..7 / OQ-29, owner Session 69; milestone RESHAPED)** — the milestone opener (`docs/specs/graph-quality.md` §3 S0). **Defining finding: the write plumbing already exists** (`EntityEditService` edit/merge/delete/undo + relation ops, M4.S3a/S3b) but only on the *reader's* panel — the graph viewer (`features/graph-viewer/`) is still the read-only M2.S5 projection (node-tap only, no edge-tap, read-only panel). So S3 is **a UX-surfacing job onto the canvas**, with exactly **one** net-new write — **predicate consolidation** (the relation analogue of entity merge, graph-wide P→Q fold) — and exactly **one** modelling call to make first: **DM-GQ-1, the §4 edge-addressability decision** — an edge's id is content-addressed `uuid5(subject,predicate,object)` so curation *changes* it, orphaning any future qualifier ([[reification]]); the call is whether to reserve a stable [[surrogate-key]] handle now (my lean (b): cheapest moment, makes the future additive, **builds no feature**). **Resolved (owner Session 69) → milestone RESHAPED:** **§4 = reserve a stable `edge_uid` handle now** (DM-GQ-1; content id stays the dedup key, the surrogate is the addressable hook for future [[reification]]; build no feature; ADR at build). **DM-GQ-2 reframed → predicate-*name normalisation* + an NLP suggest layer** (slice **S6**). **Two owner additions:** a proactive **entity dedup-suggest** pass over the accepted graph (slice **S4**) + **navigation pulled early with a layout algorithm** (slice **S2**) — both promoted from `docs/BACKLOG.md`. Final order: S1 chunker → S2 navigate → S3 edge evidence → S4 dedup-suggest → S5 in-place editing (S5a/S5b) → S6 predicate normalise+suggest → S7 reader. Invariants (§8): INV-1/9 (the suggest passes propose, the human commits), INV-3 (grouped [[graph-operation]] undo), INV-4 (name normalisation stays open-world). DM-GQ-7 bulk → backlog. Reconciled across `graph-quality.md` (§3/4/5/6/8), `PLAN_SHORT` Decided S69, OQ-29, BACKLOG. ADR for §4 drafts at build. |
| [[m4-multi-story]] | proposal | **M4 narrowed multi-story — step-0 (✅ ACCEPTED, register RESOLVED DM-MS-1..7 / OQ-27, owner 2026-06-23; no ADR)** — spec §3.6 (amended S44): *add a new story that reuses the existing project graph + per-story entity membership*; the cross-story **world graph** is OUT of PoC. **Defining finding = how little is new:** per-story membership is already **derivable** from the `entity_mentions → … → stories` FK chain (rollup query `list_entity_mentions_for_story()` exists), and the matcher seed is already project-scoped (`load_accepted(project_id)`) — so a new story auto-matches the project's known entities with **no cascade change** (§B.4 incrementality). **DM-MS-1 RESOLVED (owner) = DERIVE membership** (no new storage; single [[source-of-truth]]; introduces [[multi-tenancy]] — `project_id` is the *tenancy key*, a story is a *derived sub-scope*). Genuine gaps only: create-story-**into-existing-project** (today every upload mints a new project), project/story **list** endpoints (none exist), and a **story-scoped graph read** for the §3.4 toggle. Completeness sweep over {project,story} CRUD + graph-scope **closes** (rename + delete-project/story deferred — post-PoC / orphaned-sandbox). **No new invariant/state-machine, no ADR anticipated.** Folds the **`world_id` cleanup** (5 files/8 edits, all deletions) + a tiny **§8.4/§3.3 "whole world → whole project" stop-and-amend** (a home the S49 sweep's "world graph" grep missed). **Resolved (owner):** DM-MS-2 = `scope=` param on the existing route, **default `story`** (owner refined the default; edge rule = both-endpoints-member) · DM-MS-3 = optional `project_id` on upload · DM-MS-4 = `GET /projects` + `GET /projects/{id}/stories` · DM-MS-7 = split be/fe, `world_id` cleanup the opener. **✅ BUILT & SHIPPED (be #128 / fe #130; §8.4/§3.3 amend #119; `world_id` cleanup #124) → the multi-story live smoke PASSED (Session 54, #133) → V1 FEATURE-COMPLETE.** No new invariant/ADR (membership stayed derived). |
| [[backend-dependency-advisory-scan]] | proposal | **Continuous backend SCA gate in CI (✅ built 2026-06-08, PR #44)** — closes the gap where a vuln disclosed *after* pinning was caught only by Dependabot, not CI (the `starlette` 1.0.0 case). Built: osv-scanner step vs `uv.lock`, fail-on-any, **digest-pinned** scanner (the action is a no-`runs:` stub — stronger than the planned SHA-pin), `infra/osv/` waivers, `starlette` 1.0.0→1.0.1 (self-test red→green), §6.7 baseline (no new INV). |
| [[m2s3-extraction-agent]] | proposal | **M2.S3 nine-layer pass (✅ accepted 2026-06-08, register resolved)** — `ExtractionAgent`, first `LLMRouter` consumer. Decisions: per-paragraph, single-paragraph agent (batch→M2.S4), `candidate_name`, typed `ProviderResponseError`, soft-flag `evidence_quote`. **Built + merged (PR #42).** |
| [[m3-cascade-matching]] | proposal | **M3 cascade dedupe — step-0 forward pass (✅ register FULLY resolved: DM1–DM6 + DM7 + DM-rej; PLAN_SHORT Decided S23)** — the §3.3 four-stage cascade (RapidFuzz → embedding → JudgeAgent → human queue). Draws the candidate lifecycle; 8-entry register (DM1–DM7 + DM-rej). Central fork **DM6** ✅ intercept-before-write. Retires INV-8 at **M3.S4a** (the re-slice), lands INV-1's enforcer. Stages built proposal-only: M3.S1 RapidFuzz ✅ (PR #56), M3.S2 Stage 2 + pgvector ✅ (PR #58), M3.S3 JudgeAgent ✅ (PR #60). DM7 outcome: **INV-2 consent deferred past M3**. DM-rej: **remember rejections**. |
| [[m4-s3c-manual-tagging]] | proposal | **M4.S3c step-0 — manual tag / un-tag / change-boundaries (✅ FULLY BUILT — be PR #111 + fe1 PR #115 + fe2 PR #117; register RESOLVED DM-S3c-1..9 / OQ-26; ADR 0008 landed, §6.4 amended; "manual correction in the reader" feature-complete)** — the **final slice** of "manual correction in the reader" (S3a · S3b · **S3c**; spec §3.5 manual tagging + the right-click correction menu). **Resolved = DM-S3c-1 (B) overlay "save only what you touch":** a rendered highlight was a render-time **search hit with no identity** (DM-IH-1; `entity_mentions` char-offsets NULL/unused), so a manual span (an inflected form, a pronoun, a new entity) can't be re-found by search and un-tagging acts on a highlight with *no row to delete*. As-built: render-time search stays for the auto layer; a manual tag persists a stored span (`source='manual'`, real offsets) that overlays + wins (`reconcile_highlights` = search ∪ manual − suppressions, manual-wins-then-longest-match); rejection writes a `mention_suppressions` row (uniformly — even over a manual span); change-boundaries on an auto hit materializes the occurrence. Introduces [[materialization]]. First reader *write* slice for the **mention** layer (Evidence/Policy/Review stations flipped ✅); `tag_new_entity` grew INV-9's human-reached-writer enumeration (sixth instance); tag/un-tag/boundary ride the S3b `graph_edits` undo via new op-kinds (DM-S3c-5), contract-tested from real rows. Completeness sweep over mention CRUD + entity-from-tag **closed** (general split + relation qualifiers stay post-PoC). **ADR 0008** + the §6.4 amendment landed; **no §3.5** amendment (S3a precedent). Tiptap (DM-S3c-7, owner override) was adopted in fe1 (read-only migration) and the correction UI built on it in fe2 — selection→tag, the right-click menu (`ReaderContextMenu`/`ReaderCorrectionPopover`), and the three mutation hooks; the `editable:false`-selection risk cleared in the browser smoke. |
| [[m4-s3b-graph-mutations]] | proposal | **M4.S3b step-0 — graph mutations that need downstream cleanup: merge · delete · undo (⚠ PROPOSED, register OPEN DM-S3b-1..8 / OQ-25 — owner resolves before code)** — the slice [[m4-entity-editing]] named at its seam, and the **first to re-point already-written graph state**: entity↔entity **merge** (fold B into survivor A; re-point every incident edge — delete-old+create-new since the `uuid5` edge id changes, DM-Rel-5/6 — and re-point B's `entity_mentions`; delete B), whole-entity **delete**, and **undo** (the first *execution* of INV-3, not just S3a's substrate). **Centre of gravity = DM-S3b-1:** a merge is *one action = N writes* but the S3a `graph_edits` log is per-row, ungrouped, write-only — so undo needs a grouped append-only log (a [[compensating-transaction]]), which also resolves spec **§10 q2** (graph versioning) the lightest way. **Spec-silent on merge/delete/undo semantics → likely a §3.4/§3.5 stop-and-amend before code.** Completeness sweep over CRUD-of-{entities,relations,mentions} closes (no slicing gap). Reuses `add_alias`/`get_neighbourhood`/`delete_relation`/`create_relation`/`get_entity` + the `EntityEditService` home. Likely splits be/fe; likely **ADR 0007**. |
| [[m4-entity-editing]] | proposal | **M4.S3a — entity & relation editing (the first M4 *write* slice) (✅ BUILT + COMPLETE — be #96 / fe #98, ADR 0006; register RESOLVED DM-S3a-1..8 / OQ-23)** — owner-confirmed scope: from the read-only side panel ([[m4-side-panel]]), make the inspected entity **editable** — `canonical_name`/`aliases`/`type`/`properties` + **add/re-predicate/remove** relations between two already-accepted entities. **The first slice that *writes* committed graph state** — most stations flip from the read view's `n/a` to live; the weight is the write path + reversibility, not the UI. **Centre of gravity = DM-S3a-1** (resolved = new named edit handlers, a [[backend-for-frontend]] *write* endpoint, + **reword INV-9** "exactly two writers" → "only human-reached handlers" — the ADR-0005 broaden-don't-mint precedent, ADR drafted at build) **+ DM-S3a-2** (resolved = a before→after edit-evidence record — INV-3 undo's load-bearing call). As-built: `Neo4jRepo` has no committed-object mutators yet; the two graph-writers are the accept (nodes) + decide (edges) gates. Scope **S3b** (merge/delete/undo-merge + DM-Rel-5 re-point) + **S3c** (tag/boundaries/spans) at the seam only. **Next: build M4.S3a-be test-first.** |
| [[m4-side-panel]] | proposal | **M4.S2 step-0 — entity side panel in the reader (✅ ACCEPTED & BUILT — S2a PR #89 / S2b PR #91; register RESOLVED / OQ-22; DM-SP-4 = cytoscape, S35)** — owner-chosen second M4 slice (side panel over manual-correction-in-reader): click a highlighted entity → side panel with §3.4 details (canonical/aliases/type/**properties**/occurrences/relations/timeline) + a §3.5 **local graph around that entity** (a 1-hop [[ego-graph]]). Still a **read-only projection** (most stations n/a; INV-1/9 untouched; no LLM) — *editing* is the next slice. **Centre of gravity = DM-SP-1 data source:** most data is already on hand (occurrences derive from the reader's highlights; relations/neighbours filter `get_relations`), only `properties` is surfaced by no endpoint and no per-entity *neighbourhood* query exists — so the call is a focused BFF endpoint (`GET …/entities/{eid}`, my lean) vs composing the whole-graph fetch the viewer already does. DM-SP-7 (slice split) is downstream of it. Latent: the M4 entity↔entity merge must re-point edges + mentions or the panel shows ghosts (fail-closed: omit). |
| [[m4-inline-highlights]] | proposal | **M4.S1 step-0 — inline highlights (✅ ACCEPTED, register RESOLVED S32 / OQ-21 mostly resolved; backend built PR #81)** — the owner-chosen first M4 slice (spec §3.5): render the story text, highlight **accepted** entities inline (colour-by-type), hover→tooltip. A **read-only projection** (most stations n/a; INV-1/9 untouched; no LLM call). **DM-IH-1** resolved-as-built = **render-time string search** over name+aliases (*verify-first* found persist-spans illusory — null offsets, spaCy span gone at accept); DM-IH-2 = new `GET /stories/{id}/reader`; DM-IH-3 = plain `<mark>` (not Tiptap); DM-IH-4 longest-match; DM-IH-7 accepted-only; DM-IH-8 name+type+aliases. **DM-IH-5/6 confirm-at-build in the FRONTEND slice (next).** Side-panel + manual-annotation + the entity↔entity-merge re-point are **later** slices. |
| [[m3s4a-intercept-write-path]] | proposal | **M3.S4a step-0 — intercept-before-write (✅ BUILT / ADR 0004)** — stages candidates in the new Postgres `candidates` table, wired the cascade into the coordinator (embed-on-extract → Matching → Judge), moved Neo4j+`entity_mentions` writes to the human-accept endpoints; **retired INV-8 → landed INV-1's enforcer + INV-9**, test-first. Register **DM-S4a-1..5 resolved** (S23) + ADR 0004 authored; `[[candidate-lifecycle]]` → `living`. UI is S4b (✅ built). |
| [[m3-relation-write]] | proposal | **M3 relation-write step-0 — graph edges under human control (✅ ACCEPTED, register resolved / OQ-19 struck; built M3.S4e, ADR 0005)** — completes §9 M3's "clean graph" for *relations*. The *reframe* held: a relation endpoint is a surface string with no entity id until accept → edges write **lazily** (resolve each endpoint to its candidate's *committed* id), so re-point-on-merge dissolved (only an M4 accepted-entity↔entity merge re-points a written edge — DM-Rel-5). **DM-Rel-1 = explicit human gate** (the §3.3 5th action, not auto-write) + slice split backend-now (S4e) / UI-next (S4f); **DM-Rel-2/4/5/6/7** confirmed at build as proposed; `create_relation` now idempotent `MERGE`-on-id (DM-Rel-6). INV-1 broadened to edges (not INV-10). Added [[referential-integrity]]. Carried follow-up: per-mention provenance for triple-deduped edges. |
| [[m3s4c-intra-batch-rematch]] | proposal | **M3.S4c step-0 — intra-batch dedup (✅ accepted, register resolved / OQ-18)** — triggered by the S4b browser walk (a first pass staged `Janek` ×3 → duplicate nodes the queue couldn't merge). Two additive mechanisms on S4a/S4b: **(a) on-accept live re-match** (deterministic Stage 1/2 over still-pending candidates each accept → dupes flip `new → merge`; backend-only, no LLM) + **(b) manual handpick** (entity-search endpoint + picker for matcher false negatives). Writes **only the staging table** — INV-1/INV-9 *hold*. **Resolved (owner S25):** split **S4c** (re-match) + **S4d** (handpick); auto-flip **Stage 1 `>85%` OR Stage 2 `cosine >0.85`** (no live judge); **monotone** (guard, no INV-10); handpick **project-scoped** (supersedes the deferred arbitrary-search item). Spec §3.3 amended. Build test-first (the re-match flip test). |
| [[m2s2-llm-router-budget-cap]] | proposal | M2.S2 nine-layer pass: paid adapters + router + budget cap + status endpoint |
| [[2026-06-25-architecture-review]] | review | **current health snapshot** — V1-complete → Public-readiness vault re-sync. **No blockers.** `risk` (fixed on sight): the vault framed **PreNER as a live pipeline stage** (`PROJECT.md`/`overview.md`) though spec §7 Step 3 was amended to *deferred/dormant* (PR #138) — code-verified dormant (`extraction_agent.py` passes empty hints) and **reconciled**; `overview.md` as-built stopped at **M4.S3a** + framed M4 "in progress" though S3b/S3c/multi-story shipped and V1 is feature-complete (the 4th recurrence of doc-freshness drift) — **refreshed**, world-graph reframed post-PoC. `watch` (folded): `invariants.md` frontmatter date lagged its S3b/S3c body (**bumped**, body code-verified honest — INV-9 six writer-paths, INV-3 executed); `m4-multi-story` read build-pending (**BUILT banner**); INDEX regenerated. Forward "but what if" → the Graph-quality milestone (auto-chunker silent content-loss; membership-derivation under delete) — OQ-28. |
| [[2026-06-20-architecture-review]] | review | pre-M4.S3b re-sync (superseded as snapshot by 2026-06-25). M4.S1/S2/S3a all shipped since the roll (S3a = the first M4 *write* slice, ADR 0006). **No blockers.** `risk`: `overview.md` as-built stopped at M3 (lists every M4 slice as "Next" though all shipped) — **fixed on sight**. `watch`: three state/invariant notes' frontmatter dates lagged current bodies (**bumped**); `m4-entity-editing` read build-pending (**BUILT banner added**); INDEX item 21 stale (**regenerated**). The invariant/lifecycle layer (INV-9 rewording, candidate/relation edit-path extensions, OQ-23) was already honest — folded at the S36 decompose + S37 build. Forward "what if" over the S3b boundary: compound-undo before-image granularity (a merge is N writes), MERGE-collision on edge re-point, the `entity_mentions` re-point cross-store seam — inputs to the S3b decompose. |
| [[2026-06-17-architecture-review]] | review | M3→M4 roll re-sync (superseded as snapshot by 2026-06-20) — M3 feature-complete (S4b–S4f all shipped) → M3→M4 roll. No blockers. `risk`: `overview.md` as-built ~5 sessions stale (lists the relation graph-write + review UI as "planned, not yet built" — both shipped) (**✅ resolved 2026-06-18 — refreshed at the S31 M3→M4 roll: `overview.md` now `2026-06-17`, M3 feature-complete + "Next — M4", no "planned, not yet built"**); the relation lifecycle has no state-machine note (entity twin does → OQ-20 — **✅ resolved 2026-06-18, [[relation-lifecycle]] drawn**). `watch`: `invariants.md` frontmatter date lags its correct body; edge-id provenance collapse (ADR-0005 follow-up); held-relation visibility (**now tracked in [[relation-lifecycle]] Open points (a)**); M4 forward flags (§3.4 graph scoping now live work; DM-Rel-5 re-point becomes real; OQ-14/OQ-15 open). |
| [[2026-06-15-architecture-review]] | review | M3.S3 merged → entering M3.S4 (superseded as snapshot by 2026-06-17; no blockers; `risk`: DM5 resolved-but-framed-open, `overview.md` snapshot predates M3.S1–S3; `watch`: `task_type` label `judging`→`judge`, gate-less Stage-3 egress with INV-2 deferred, staging-table Expiry, store-chatty cascade. INV-8 correctly still live `[TEMPORARY]` — the flip is S4a's, test-first) |
| [[2026-06-11-architecture-review]] | review | M2→M3 roll catch-up + forward sweep (superseded as snapshot by 2026-06-15) (no blockers; `risk`: INV-2 consent gate lost its M2.S5 landing → unscheduled + a real paid call fired gate-less; `overview.md` 2 sessions stale; INV-5/OQ-9 latency built but future-tensed. Forward: M3 lands INV-1's enforcer, lifts INV-8, needs the candidate state machine drawn — the decompose step-0) |
| [[2026-06-09-architecture-review]] | review | pre-M2.S4 drift + forward sweep (superseded as snapshot by 2026-06-11; no blockers; `risk`: `overview.md` 3 sessions stale, `entity_mentions` table absent from migrations, INV-8 needs CREATE-not-MERGE, new write-path must map router errors→HTTP; M2.S4 plan aligned; OQ-1/OQ-2 were the owner's calls — since resolved) |
| [[2026-06-02-architecture-review-post-m2s2]] | review | post-M2.S2 as-built drift sweep (superseded as snapshot by 2026-06-09; no blockers/risks; watches: latency OQ-9, malformed-envelope OQ-10 — now closed, redaction, state-machine undrawn) |
| [[2026-06-02-architecture-review]] | review | OQ-A drift sweep over M0→M2.S1 + ADRs 0001–0002 (point-in-time; findings resolved by ADR 0003) |

## Awaiting content (populated by later runs)
- `decisions/` — ADRs (host-project ADRs live in `docs/decisions/`; this folder is for
  vault-framed decisions once confirmed). Empty — the M2.S2 router/budget decision (D6) was authored as a **host-project** ADR (`docs/decisions/0003`), where product ADRs live; this vault folder stays empty until a vault-framed decision arises.
- `components/` — per-component (C4 Component altitude) notes. Empty.
- `state-machines/` — **three drawn:** **[[candidate-lifecycle]]** (the **node** gate, `living`, M3
  step-0): `extracted → {auto-merge|ambiguous|new}-proposed → judged → review-queued → (human) →
  {merged|created|rejected}`; commit guard = INV-1. **[[relation-lifecycle]]** (the **edge** gate,
  `living`, drawn 2026-06-18 — closes OQ-20): `staged → held|committable → written|rejected` as built in
  `RelationReviewService` (re-resolve-at-commit TOCTOU guard, idempotent-by-edge-id effect, INV-1/INV-9
  broadened to edges; held/committable are derived views of the persisted `staged` row).
  **[[graph-operation]]** (the **undo stack**, `living`, drawn 2026-06-20 — M4.S3b): the *operation*
  twin of the per-object gates — `applied → undone` for a whole author action (edit/merge/delete) in
  the grouped `graph_edits` log; transition = `undo_last` (replay inverse in reverse `seq`, stamp
  `undone_at`); drift check guards it (lost-update-in-reverse → 409), re-undo a no-op. INV-3 *executed*
  (ADR 0007). Still to draw: the **ingest-job** + **LLM-call** lifecycles (the M2.S2 proposal sketches
  the latter).

## Next steps

> **Chronological run-log — newest at the bottom.** Each numbered entry records the next step *as of
> that session*; the **current** next is the **last item**. Earlier `Next: …` phrases (e.g. item 16's
> "Next: M4") are **historical breadcrumbs**, not live — read them in their dated context. (Regenerated
> note: this list grows by append each sweep.)

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
    (`status: accepted`, register **RESOLVED** DM-S3a-1..8 / OQ-23 — owner, same session). **The first M4 slice
    that *writes* the graph** (DM-S3a-1 = new named edit handlers + reword INV-9; DM-S3a-2 = before→after
    edit-evidence log; typed `properties`; split be/fe). **Next session:** build **M4.S3a-be** test-first from
    the pure boundary-validation/field-merge function (the resolved register is the build spec; the INV-9
    rewording + its ADR land test-first at build). Also pending: the starlette/jp82 OSV waiver drops
    (`ignoreUntil` 2026-06-26/27 — `/triage-advisory` when due).
22. **M4.S3a entity & relation editing BUILT ✅ — M4's first *write* slice complete (2026-06-19/20, Sessions 37–38).**
    **M4.S3a-be** (PR #96): `EntityEditService` + `Neo4jRepo.update_entity`/`delete_relation`/`get_relation`
    + the `graph_edits` before→after evidence migration + `PostgresEditStore` + `PATCH …/entities/{eid}` /
    `POST`+`DELETE …/relations`. **ADR 0006** authored (edit committed graph state under human-reached
    handlers); **INV-9 reworded** "exactly two writers" → "only human-reached handlers — accept, decide,
    edit" (broaden-don't-mint, ADR-0005 precedent); **DM-S3a-3 resolved-at-build to a direct edge-writer**
    (the decide path is surface-name/paragraph-keyed, a hand-picked edge has neither); the committed-node
    edit self-transition folded into [[candidate-lifecycle]], the edge edit-path into [[relation-lifecycle]].
    **M4.S3a-fe** (PR #98): the panel's Edit mode + relation add/remove, mutation hooks invalidating
    reader+graph+detail; one read-side add (`language` on `EntityDetailResponse`; bilingual-per-project out
    of PoC scope — spec §10 q8 resolved-for-PoC). Both review gates ran; live-smoke-verified.
    **Next: M4.S3b** — entity↔entity **merge** (DM-Rel-5 written-edge re-point + `entity_mentions.entity_id`
    re-point + DM-Rel-6 idempotency) + whole-entity **delete** + **undo** (consuming the S3a `graph_edits`
    log — no undo execution wired yet). Branchy → its **step-0 `decompose-requirement`** is the first task;
    this 2026-06-20 sweep ([[2026-06-20-architecture-review]]) is its pre-decompose re-sync, flagging the
    **compound-undo before-image granularity** (a merge is N writes) the decompose must resolve.
23. **M4.S3b decomposed ✅ (2026-06-20) — register OPEN, owner resolves before code.** Step-0 →
    [[m4-s3b-graph-mutations]] (`status: proposed`, register **OPEN** DM-S3b-1..8 / OQ-25). The slice
    [[m4-entity-editing]] named at its seam: entity↔entity **merge** (DM-Rel-5/6 edge re-point +
    `entity_mentions` re-point), whole-entity **delete**, **undo** (the first *execution* of INV-3). The
    completeness sweep over CRUD-of-{entities,relations,mentions} **closes** (no slicing gap). **Centre of
    gravity = DM-S3b-1:** the per-row S3a `graph_edits` log can't group a merge's N writes → undo needs a
    grouped append-only log (a [[compensating-transaction]]), resolving spec **§10 q2** the lightest way.
    **DM-S3b-2/5 are spec-silent (merge + delete semantics) → a likely §3.4/§3.5 stop-and-amend first.**
    Added the [[compensating-transaction]] glossary term. **Next:** the owner resolves DM-S3b-1..8 (one
    plain-language question at a time) — incl. any spec amendment — **then** build M4.S3b-be test-first
    from the pure merge-consolidation function. Likely **ADR 0007** at build.
24. **M4.S3c decomposed + register RESOLVED ✅ (2026-06-22, Session 44).** Owner chose **S3c manual tag /
    un-tag / change-boundaries** (spec §3.5) as the next M4 slice **to build** (over the multi-story work,
    which was re-scoped — see below). Step-0 → [[m4-s3c-manual-tagging]] (`status: accepted`, register
    **RESOLVED** DM-S3c-1..9 / OQ-26). **Centre of gravity = DM-S3c-1 (span storage):** a rendered
    highlight is a render-time *search hit with no identity* (DM-IH-1), so manual spans can't be searched
    and un-tagging has no row to delete. **Owner resolutions:** DM-S3c-1 = **(B) overlay / save-only-what-
    you-touch** (keep search + stored manual spans + suppressions; incremental [[materialization]], no
    backfill); DM-S3c-2 = **both attach-existing + create-new-entity**; DM-S3c-7 = **adopt Tiptap now**
    (owner override — V2 editing inherits it); tag/un-tag/boundary ride the S3b undo (DM-S3c-5); split
    be/fe; no §3.5 capability amendment (S3a precedent) — storage model + INV-9 reword in **ADR 0008** at
    build. Added the [[materialization]] glossary term. Completeness sweep over mention CRUD +
    entity-from-tag **closes**. **Scope decisions same session (owner):** world-level/world-graph
    multi-story **OUT of PoC** → `docs/BACKLOG.md`; the narrowed multi-story (new story reuses the project
    graph + per-story entity membership + extraction leverage) stays in PoC and concretizes the §3.4
    scoping cross-cutting (pending a §3.6/§9 stop-and-amend); **code-doc-generation** added to backlog.
    **Next:** build **M4.S3c-be** test-first from the pure reconciling-resolver function (`/add-dependency`
    for Tiptap at the fe build).
25. **M4 narrowed multi-story decomposed + register RESOLVED ✅ (2026-06-23, Session 50).** Step-0 →
    [[m4-multi-story]] (`status: accepted`, register **RESOLVED** DM-MS-1..7 / OQ-27).
    "Manual correction in the reader" (S3a/S3b/S3c) is feature-complete; this is the next M4 slice. Spec
    §3.6 (amended S44): *add a new story that reuses the project graph + per-story membership*; world
    graph OUT of PoC. **Defining finding = how little is new** — membership is already **derivable** (the
    `entity_mentions → … → stories` FK chain + the existing `list_entity_mentions_for_story()` rollup), the
    matcher seed is already project-scoped, and the reader is already multi-story-correct. **DM-MS-1
    RESOLVED (owner) = DERIVE membership** (no new storage; one [[source-of-truth]]); introduced the
    [[multi-tenancy]] glossary term (`project_id` = tenancy key; a story = a derived sub-scope). Genuine
    gaps: create-into-existing-project, project/story list endpoints, story-scoped graph read (§3.4
    toggle). **No new invariant/state-machine; no ADR.** Folds the `world_id` cleanup + a tiny **§8.4/§3.3
    "whole world → whole project" stop-and-amend** (the S49 sweep's "world graph" grep missed it).
    **Owner resolutions (2026-06-23):** DM-MS-2 = `scope=` param on the existing route, **default
    `story`** (owner refined the default from my `project`); DM-MS-3 = optional `project_id` on upload;
    DM-MS-4 = two list endpoints; DM-MS-7 = split be/fe, `world_id` cleanup the opener; DM-MS-6 verified
    already-covered by S3b. **Next:** the §8.4/§3.3 spec amendment (main loop), **then** build test-first
    from the pure membership-rollup property; the `world_id` cleanup is the low-risk opener.
26. **M4 narrowed multi-story BUILT → V1 FEATURE-COMPLETE ✅ (2026-06-23/24, Sessions 52–54).** Backend
    #128 + frontend #130; the multi-story live smoke **PASSED** (Session 54, #133). M0–M4 ship; V1 is
    done. The project rolled into the **Public-readiness** milestone (Session 55, `docs/PLAN_SHORT.md`):
    docs/spec/portfolio polish, little-to-no production code, before the next build milestone. Roadmap
    (owner-DECIDED Session 54, `docs/PLAN_LONG.md`): **Public-readiness → Graph-quality polish → V2 Editing.**
27. **Public-readiness re-sync sweep ✅ (2026-06-25, this run) — [[2026-06-25-architecture-review]].** Brought
    the vault current with the V1-complete reality + the PreNER spec amendment (PR #138): reconciled the
    PreNER-as-live-stage drift (`PROJECT.md`/`overview.md` → dormant, code-verified), refreshed the stale M4
    block (S3b/S3c/multi-story shipped; world-graph reframed post-PoC), bumped `invariants.md` (body
    code-verified honest), added the `m4-multi-story` BUILT banner. No blockers. Forward "what if" → OQ-28
    (Graph-quality inputs). **Next:** the Public-readiness build sessions (README overhaul + demo artifacts,
    code documentation, doc hygiene).
28. **Graph-quality S0 decompose ✅ + register RESOLVED + milestone RESHAPED (2026-06-26, Session 69).**
    Step-0 → [[graph-curation-surface]] (`status: accepted`, register **RESOLVED** DM-GQ-1..7 / OQ-29,
    owner same session). **Defining finding:** the edit/merge/delete/undo write plumbing already ships
    (`EntityEditService`, M4.S3a/S3b) but only on the *reader's* panel, so the editing slices are
    UX-surfacing onto the canvas; net-new code is the **§4 edge handle**, **predicate-name normalisation**,
    and a **dedup-suggest** pass. **Owner resolutions:** §4 = reserve a stable [[surrogate-key]] handle now
    (future [[reification]] additive, build no feature, ADR at build); DM-GQ-2 reframed → predicate-*name
    normalisation* + NLP suggest (S6); + two owner additions promoted from BACKLOG — an **entity dedup-suggest**
    pass (S4) and **navigation pulled early + a layout algorithm** (S2). **Milestone reshaped:** S1 chunker →
    S2 navigate → S3 edge evidence → S4 dedup-suggest → S5 in-place editing (S5a/S5b) → S6 predicate
    normalise+suggest → S7 reader. Added `[[surrogate-key]]` + `[[reification]]` (glossary 28 → 30).
    Reconciled across `graph-quality.md` (§3/4/5/6/8), `PLAN_SHORT` (task list + Decided S69), OQ-29, BACKLOG.
    **Next:** **S1** — the auto-chunker completeness check, the first *build* slice, **test-first**
    (independent of this register). The §4-handle ADR + the S4 dedup-suggest step-0 draft at their build.
29. **Graph-quality S2 decompose ✅ + register RESOLVED (2026-06-29, Session 72, owner).** Owner approved a
    step-0 for the branchy navigate-the-graph slice; decomposed + resolved same session. Step-0 →
    [[graph-navigation]] (`status: accepted`, register **RESOLVED** DM-GN-1..4 / OQ-30). **Read-only,
    frontend-led** (INV-1/3/9 untouched; INV-4 constrains the type filter). **Defining finding (completeness
    sweep): every §3.4 filter runs client-side over the payload `useStoryGraph` already fetches** (type +
    names + aliases on `GraphNode`, degree from `edges[]`, the "by story" axis already shipped as the binary
    `scope` toggle). **Owner resolutions:** DM-GN-1 = **client-side** (no new backend; finer N-story filter
    YAGNI-deferred); DM-GN-2 = **`cytoscape-fcose`** (pin via `/add-dependency`, `verify-at-build` the
    version); DM-GN-3 = **(a) spec-faithful — S2 navigation-only, edge-tap evidence panel stays S3** (the
    parent [[graph-curation-surface]] "edge panel is S2's" claim was **drift** — per `AGENTS.md` the spec
    wins; reconciled in that proposal's §3 operation-sweep + the OQ-29 body + DM-GQ-3/6 cross-refs); DM-GN-4
    = **AND-combine + hide-and-relayout + search-as-focus.** No substantive spec change (a tiny §4 wording nit
    fixed with owner OK — "S2's edge surface" → "the S3+ edge slices"); no ADR. **Next:** build **S2** test-first from the pure filter/degree/search functions
    (`frontend/src/AGENTS.md` — logic out of `GraphCanvas`), then `/add-dependency` for `cytoscape-fcose` at
    the canvas step; the layout swap is browser-smoke-verified.
30. **Graph-quality S2 BUILT (Session 73, PR #168) → S3 decomposed (2026-07-01, Session 74).** S2 shipped
    frontend-only, read-only — client-side type/degree filters + diacritic name search + `cose`→
    `cytoscape-fcose`, browser-smoke-verified at Oakhaven scale (`[[graph-navigation]]` was its step-0).
    **S3 step-0 → [[graph-edge-evidence]]** (`status: accepted`, register **RESOLVED** DM-EE-1..6 / OQ-31,
    owner same session — every entry on the leaned option a). A
    **read/verify** slice (edge evidence + verifiable merges + three safeguards); **writes nothing**
    (INV-1/3/9 untouched). **Defining finding:** the context S3 must show is real but not on the wire — edge
    [[provenance]] survives commit in `staged_relations` (content-addressed `edge_id`) but has no client
    read/index; the viewer has no edge-tap; the merge surfaces show a bare score + generic target. So S3's
    real work is a small set of new **read** surfaces (a focused edge-evidence BFF read + merge-context
    enrichment) — not new storage, not the §4 write-handle. Added [[provenance]] (glossary 30→31). Central
    call **DM-EE-1** (focused per-edge read vs payload-enrich). **Register RESOLVED same session (owner,
    Session 74) — every entry on the leaned option (a)** (see the [[graph-edge-evidence]] banner /
    `[[open-questions]]` OQ-31). **No spec amendment / no ADR.** **Next:** build **S3a backend-first,
    test-first** from the pure `staged_relations`-by-`edge_id` read + the enriched `CandidateView`
    projection (+ `target_canonical_name`, closing the cross-cutting item); then S3b frontend.
    **S3 BUILT + merged (S3a PR #172, S3b PR #174; Sessions 75–76) — S3 COMPLETE.**

    **S4 step-0 → [[graph-cluster-dedup]]** (`status: accepted`, register **RESOLVED** DM-CD-1..6 / OQ-32,
    owner Session 77). Re-point the §3.3 cascade matcher **inward** (a self-join over the
    `AcceptedSnapshot`) to **suggest** likely-duplicate accepted entities; the human commits each merge
    through the **existing** merge endpoint — **suggests, never auto-merges** (INV-1/9 hold; no egress/LLM).
    **Defining finding:** both the matcher and the merge commit path already ship, so S4 adds only a
    *read/analysis* self-join + a *review* surface — **no net-new graph write** (the entity twin of S6's
    predicate-name suggest). **Register RESOLVED (owner, Session 77):** DM-CD-1 **pairwise** ·
    DM-CD-2 **eager/recall-first** (name + embeddings, ambiguous floor, deterministic) · DM-CD-3 **persist
    dismissals** (ADR-worthy, drafts at build — the [[intra-batch-dedup|DM-rej]] precedent) · DM-CD-4
    dedicated list · DM-CD-5/6 S4a be / S4b fe, reuse the merge. Added [[entity-resolution]] +
    [[connected-components]] + [[blocking]] (glossary 31→34). **Next: build S4a backend-first, test-first**
    (pure `domain/duplicate_clusters.py` self-join + `GET …/duplicate-suggestions` + the dismissal store),
    then S4b frontend — **a fresh conversation**.

31. **Graph-quality S4 BUILT (S4a #179 / S4b #181, Sessions 78–79) → S5 decomposed (2026-07-08, Session 80).**
    S4 shipped be+fe (duplicate-suggestion self-join + review list; ADR 0010 for the dismissal store) — S4
    COMPLETE. **S5 step-0 → [[graph-canvas-editing]]** (`status: accepted`, register **RESOLVED** DM-S5-1..6 /
    OQ-33, owner Session 80). The milestone **spine**, branchy (S5a node / S5b edge per DM-GQ-6): bring the existing node/edge
    write paths onto the graph canvas ([[direct-manipulation]]), human gate + grouped undo intact
    (INV-1/9/3), reusing the reader's edit panel (DM-GQ-3). **Grounded in two code-level surveys.** Defining
    finding: node-editing already ships end-to-end and is wired on the *reader* → **S5a is pure
    canvas-surfacing**; the only net-new plumbing is **edge-editing** (`edit-predicate`/`re-target` have no
    atomic op — a client remove+add re-keys the content-addressed `relation_edge_id`), so **S5b is the first
    edge-*write* slice and consumes the reserved §4 handle** ([[surrogate-key]], DM-GQ-1, confirmed unbuilt;
    **ADR drafts at the S5b build**). Operation-surface sweep over node+edge closes. Added
    [[direct-manipulation]] (glossary 34→35). No spec amendment; no ADR this session. **Register RESOLVED
    same session (owner, Session 80):** DM-S5-1 extract a shared `EntityEditPanel` core · DM-S5-2 atomic
    backend edge-edit op · DM-S5-3 mint-forward/no-backfill + invariant-at-build (ADR at S5b build) · DM-S5-4
    **defer right-click** (owner override, panel-only S5) · DM-S5-5 single S5a + tag in S5b-be · DM-S5-6
    panel-vanish guard + LWW. Build cut: **S5a → S5b-be → S5b-fe. Next: build S5a test-first in a fresh
    conversation.**
32. **Graph-quality S5 BUILT (S5a #185 / S5b-be #189 / S5b-fe #191, Sessions 81–83) + out-of-sequence
    tooling-extraction unit COMPLETE (Sessions 84–89) → S6 decomposed (2026-07-13, Session 90).** S5 shipped
    the in-place editing canvas (node + edge editing, the §4 `edge_uid` handle + ADR 0011 + INV-10, the two
    atomic edge re-key ops) — S5 COMPLETE. The tooling-extraction unit (graduate `meta-architect` to its own
    repo; SF vendors a copy — path A) then ran and completed. **S6 step-0 → [[graph-name-normalisation]]**
    (`status: proposed`, register **OPEN** DM-NN-1..6 / OQ-34). One human-gated *suggest-then-you-decide*
    normalisation pass over **both** relationship-predicate names and entity-type labels (INV-4 — nothing
    auto-collapses; INV-1/9 human gate). **Defining finding = "one engine or two" answered at the storage
    layer:** a predicate is the Neo4j *relationship type* (part of the content-addressed edge id → renaming
    **re-keys** every bearing edge, reusing the S5b `plan_relation_rekey`, preserving `edge_uid` per INV-10,
    folding identical triples — the reported side-effect); an entity type is a node *property* (renaming is a
    bulk `SET n.type` — no re-key, no handle, no collapse). So **one shared SUGGEST engine + two forked APPLY
    paths** — S6 is also the near-term consumer of the §4 handle S5 reserved. Second finding: the embedding
    rung matters *more* than in S4 (synonyms like `PASSENGER_ON`↔`ON_SHIP` are fuzzy-distant but semantically
    close), embedding the label string itself. Operation sweep over the two vocabularies **closes** (the
    type-relabel is the only net-new writer). Added [[controlled-vocabulary]] (glossary 35→36). **No spec
    amendment, no ADR anticipated.** **Register RESOLVED (owner, Session 91, 2026-07-13) — all six on the
    proposed lean** (see the [[graph-name-normalisation]] row + OQ-34). **Next:** build S6a test-first from the
    shared pure suggest function — a fresh conversation.

_Run log: see [[changelog]]. Seeded by `initialize-project-architecture`; extended by
`review-architecture` + `decompose-requirement`, 2026-06-02._
