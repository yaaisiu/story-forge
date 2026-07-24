---
type: overview
slug: overview
updated: 2026-07-24
status: living
related: ["[[project]]", "[[invariants]]", "[[open-questions]]", "[[cascade-matching]]", "[[model-tier-routing]]", "[[m3-cascade-matching]]"]
---

# System overview — Story Forge (nine-layer seed pass)

This is the **system-altitude** analysis note: Story Forge viewed *as a whole*, run through
all nine architectural layers. It is distinct from [[project]], which holds the stable
*inputs* (identity, personas, business, source-of-truth); this note holds the *analysis* that
grows from them.

**Altitude vocabulary.** Throughout the vault I borrow the **C4 model** (**model C4** — a
standard way to draw software at four zoom levels: System → Container → Component → Code; see
[[c4-model]]). This note is at the **System** level — the whole app and its neighbours. Later
per-feature notes (`proposals/`) and per-component notes (`components/`) zoom in. Naming the
altitude matters because a concern that is loud at one level is often silent at another.

---

## Current as-built state (the honest snapshot)

The interview asked the architect to *first check what is already built and decided, then
strategize forward*. So this overview is grounded in what the code actually does today, not
only what the spec plans. (Authoritative roadmap: `docs/PLAN_SHORT.md`; runtime truth: the
code.)

**Built and merged (M0 → M2.S6 — M2 complete):**
- **M0** — secure-by-default infra: docker-compose with Neo4j, Postgres+pgvector, Ollama,
  all localhost-bound and non-root; pinned/aged deps; CI (`ci.yml`).
- **M1** — upload + structure: `.txt/.md/.docx` upload (sandboxed storage,
  `adapters/upload_storage.py`), the `ChunkingAgent` + `ChunkingCoordinator` (story → outline),
  Postgres persistence of the document tree (`adapters/postgres_repo.py`), and a React
  frontend (upload screen + outline editor) wired through a typed API client.
- **M2.S1** — `PreNERAgent`: a deterministic, **no-LLM** spaCy baseline that returns candidate
  spans per paragraph (`agents/prener_agent.py`). **Built but dormant** — it is wired into nothing;
  the live `/extract` path is **LLM-only** (the PreNER-hint param is passed empty, "deferred until a
  real eval exists" — `extraction_agent.py`). Spec **§7 Step 3** marks it *deferred/dormant for the
  PoC* (amended 2026-06-25). The eval that would activate it (the "spaCy PreNER without the LLM"
  comparison) is in `docs/BACKLOG.md`; corrections feed the data flywheel (`docs/PLAN_LONG.md`).
- **M2.S2** — the paid LLM tier + routing (PR #36): `OpenRouterProvider` (the only paid adapter
  built), the `LLMRouter` (tier selection + error-discriminated within-tier failover + fail-closed
  budget cap), the `llm_calls` cost ledger (`PostgresCostStore`, independent-commit), and the
  `GET /llm/status` endpoint (`adapters/llm/{base,ollama,openrouter,router,cost,postgres_cost_store}.py`,
  `api/llm.py`). Provider order + OpenRouter-only scope: `docs/decisions/0003`.
- **M2.S3** — `ExtractionAgent` (PR #42): the first `LLMRouter` consumer — one paragraph → an
  `ExtractionProposal` of entity/relation candidates, render→call→validate→retry, with the typed
  `ProviderResponseError` envelope-failover path (OQ-10, closed) (`agents/extraction_agent.py`).
- **M2.S4** — Neo4j writes, **no dedupe** (PR #48): `proposal_to_graph` (pure candidate→graph
  mapping), the `Neo4jRepo` `CREATE`-not-`MERGE` writes (INV-8), the `entity_mentions` migration +
  `PostgresMentionStore` back-reference, the resumable `ExtractionCoordinator` batch driver
  (OQ-1/OQ-2, resolved), and `POST /stories/{id}/extract` (200 / 202-paused / 502)
  (`agents/{extraction_graph,extraction_coordinator}.py`, `adapters/{neo4j_repo,postgres_mention_store}.py`).

- **M2.S5** — frontend **graph viewer** + **agent-activity panel** (PR #51):
  `features/{graph-viewer,agent-activity}/`, and the `latency_ms` column (migration
  `2026_06_11_0956…`) + router capture shown in the §8.5 panel (OQ-9 → option a).
- **M2.S6** — **thin close of M2** (PR #53): real-provider smoke (`scripts/check_openrouter.py`:
  Ollama Cloud + an OpenRouter model, both 200; key-leak grep clean) + the §6.7 key-leak procedure in
  `backend/AGENTS.md`. **Deferred** the §6.5 model-override dropdown (INV-7-touching feature → OQ-14);
  **observability/operational logging** recorded as a later need (→ OQ-15). No direct vendor adapters
  (OpenRouter is the only paid route — `docs/decisions/0003`).

**M3 — the §3.3 cascade, now FEATURE-COMPLETE (PRs #56/#58/#60/#63/#65/#67/#70/#76/#78):**
- **M3.S1–S3** — the cascade stages, each shipped proposal-only then wired live at S4a:
  **Stage 1** RapidFuzz token-set vs `canonical_name`+aliases (#56); **Stage 2** embedding cosine +
  the **pgvector foundation** — real `vector(768)` on `entity_mentions`, `register_vector_async`, the
  multilingual mpnet model pinned via the §6.7 HF-model channel (#58); **Stage 3** `JudgeAgent`
  (LLM-as-judge, cloud_free via the router `task_type="judge"`, strict `{match,confidence,reasoning}`,
  merge iff `match AND conf>0.8`, #60).
- **M3.S4a — intercept-before-write (ADR 0004).** The `ExtractionCoordinator` no longer writes the
  graph: it *stages* each candidate into a Postgres `candidates` table with the cascade's proposal
  (embed-on-extract → Matching S1/S2 → Judge S3, fail-closed), writing **zero** Neo4j nodes. The graph
  is written **only** by the human-accept path (`CandidateReviewService` → `POST …/candidates/{cid}/accept|reject`).
  **Retired INV-8 → landed INV-1's first enforcer + INV-9**; finalised `[[candidate-lifecycle]]` to
  `living`. Mentions move to accept-time (+ context vector); resume checkpoint = `paragraph_processed`;
  accept/reject leave an append-only `candidate_decisions` evidence row. store-down→503 + the
  Neo4j-driver lifespan close landed here.
- **M3.S4b — review-queue UI (#65).** `features/extraction-review/`: the §3.3 Stage-4 elements +
  keyboard nav, consuming S4a's endpoints (accept/change-target/create/reject).
- **M3.S4c — on-accept live re-match (#67).** Each human accept re-runs the *deterministic* matcher
  (Stage 1/2, no judge) over still-pending candidates, flipping intra-batch duplicates `new → merge`
  in the staging table only (the [[candidate-lifecycle]] self-loop; INV-1/INV-9 hold — see
  [[m3s4c-intra-batch-rematch]]).
- **M3.S4d — manual handpick (#70).** `GET /stories/{id}/entities?q=` (project-scoped, RapidFuzz-ranked,
  injection-safe) + a review-card picker, the false-negative safety net feeding the merge path.
- **M3.S4e — relation-write backend (ADR 0005, #76).** `RelationReviewService` resolves a staged
  relation's surface endpoints to their *committed* entity ids and writes the edge under the **§3.3 5th
  human action** ("decide on relations"), idempotent `MERGE` on `uuid5(subject,predicate,object)` (one
  edge per fact across paragraphs). **INV-1 broadened to edges; INV-9 second witnessed instance.** New
  `staged_relations` table (the edge lifecycle + evidence). See [[m3-relation-write]].
- **M3.S4f — relation-review UI (#78).** The S4a→S4b shape for edges: `features/relation-review/`
  (A=commit / R=reject, J/K nav) consuming `GET …/relations` + `POST …/relations/{rid}/decide`.

So today Story Forge ingests and structures text, **extracts entity/relation candidates with an LLM**
(routed, budgeted, recorded — directly on the raw paragraph text, **not** via PreNER, which stays
dormant — §7 Step 3), runs the §3.3 cascade and **stages** each candidate with a NEW-vs-MERGE proposal
— and writes **both** graph nodes **and edges** **only when the author accepts** at the review queues
(INV-1/INV-9, entities + relations). On-accept re-match and manual handpick keep a single ingest's
graph clean. The graph is empty until reviewed; the §3.3 dedupe — for nodes *and* relations — is the
human's gated decision, not an automatic write.

**M4 ("V1 polish") — FEATURE-COMPLETE; V1 done (the multi-story live smoke PASSED, Session 54). PRs
#81/#86, #89/#91, #96/#98, #102/#105/#107, #111/#115/#117, #128/#130:**
- **M4.S1 — inline highlights** (#81 backend / #86 frontend). A **read-only projection** of the
  accepted graph: render the story text, highlight accepted entities inline (colour-by-type), hover →
  tooltip (name + type + aliases; **since Graph-quality S7 also a graph-derived relation summary** —
  DM-IH-8 superseded, spec §3.5). **DM-IH-1** resolved render-time string search over name+aliases (`entity_mentions` carry
  null char offsets — no stored span to render), exposed by a new story-scoped `GET …/reader` — the
  §3.4 per-story filter's first home. See [[m4-inline-highlights]].
- **M4.S2 — entity side panel** (#89 backend / #91 frontend). Click a highlight → a read-only panel
  with the entity's details/`properties`/occurrences/relations + a 1-hop [[ego-graph]] mini-view, off a
  focused BFF endpoint `GET …/entities/{eid}` ([[backend-for-frontend]]) + a new 1-hop `Neo4jRepo`
  neighbourhood query. Still read-only (INV-1/3/9 untouched). See [[m4-side-panel]].
- **M4.S3a — the panel becomes editable: the FIRST M4 *write* slice** (#96 backend / #98 frontend,
  **ADR 0006**). Edit an accepted entity's `canonical_name`/`aliases`/`type`/`properties` + add/remove
  relations between accepted entities, under a new human-reached `EntityEditService`. **INV-9 reworded**
  "exactly two writers" → "only human-reached handlers — accept, decide, **edit**" (broaden-don't-mint,
  the ADR-0005 precedent); every edit records a before→after `graph_edits` row (INV-3 undo substrate).
  See [[m4-entity-editing]], [[invariants]] INV-9, and the edit-path extensions in
  [[candidate-lifecycle]] / [[relation-lifecycle]].
- **M4.S3b — merge · delete · undo: the first slice that *re-points* committed graph state** (#102
  merge / #105 delete+undo-executor / #107 frontend, **ADR 0007**). Entity↔entity **merge** (fold B
  into A, re-point every incident edge — delete-old+create-new since the `uuid5` edge id changes — and
  re-point B's `entity_mentions`, then `delete_entity` B), whole-entity **delete** (`DETACH DELETE` +
  full snapshot), and the general **undo executor** that *executes* INV-3: a merge/delete's whole
  fan-out is one grouped, reversible `graph_edits` operation (`operation_id`+`seq`, a
  [[compensating-transaction]]; a drift check refuses an undo over since-changed state — a [[lost-update]]
  in reverse). Resolves spec **§10 q2** (graph versioning) the lightest way. See [[m4-s3b-graph-mutations]],
  [[graph-operation]].
- **M4.S3c — manual tag / un-tag / change-boundaries in the reader** (#111 backend / #115 Tiptap
  migration / #117 correction UI, **ADR 0008**). The final "manual correction in the reader" slice:
  a manual tag persists a stored span (`source='manual'`, real offsets) that overlays render-time
  search and wins; rejection writes a `mention_suppressions` row the resolver subtracts; tag-as-new-entity
  mints a node directly (INV-9's sixth witnessed writer-path). Introduces [[materialization]] (the derived
  highlight layer becomes incrementally addressable). The reader migrated to **Tiptap** read-only.
  See [[m4-s3c-manual-tagging]].
- **M4 narrowed multi-story** (#128 backend / #130 frontend). *Add a new story that reuses the existing
  project graph + per-story entity membership* (the cross-story **world graph** is **OUT of PoC** →
  `docs/BACKLOG.md`). Defining finding: how *little* is new — per-story membership is **derived** from
  the `entity_mentions → … → stories` FK chain (no new storage; one [[source-of-truth]]; introduces
  [[multi-tenancy]] — `project_id` is the tenancy key, a story a derived sub-scope), the matcher seed is
  already project-scoped, so a new story auto-matches the project's known entities with no cascade change.
  Adds `scope=story|project` on the graph route (default `story`), `project_id`-on-upload, and project/
  story list endpoints; folds the vestigial `world_id` cleanup. No new invariant, no ADR. See [[m4-multi-story]].

**Public-readiness — CLOSED at the Session-68 roll** (docs / spec / portfolio polish, little-to-no
production code).

**Graph quality — COMPLETE (S0–S7, Sessions 68–100; PRs #164–#223).** The milestone's premise: V1
*deliberately over-extracts* — every graph write passes the human gate (INV-1/INV-9), so the working
graph is dense with duplicates, near-synonym edges, and spurious nodes left *on purpose* for curation.
The enabling insight, and the milestone's thesis: **the human gate is only as good as the context it
shows you**, and bringing the source text to the decision point is mostly *cheap* — the data already
exists. So this was largely a **UX-surfacing** milestone over shipped write plumbing, not net-new
machinery. Scope authority: `docs/specs/graph-quality.md`.
- **S0 — decompose** (#166 era; [[graph-curation-surface]], DM-GQ-1..7). Defining finding: the
  edit/merge/delete/undo plumbing already shipped at M4.S3a/S3b but *only on the reader's panel*, so
  the editing slices are canvas-surfacing. Reserved a stable **edge handle** (§4) for the write slices.
- **S1 — stop silent data loss** (#164). The auto-chunker could drop trailing paragraphs and report
  success. One canonical range invariant (`domain.paragraph_range_problem` — covers every paragraph
  `[0, count)`, nothing past the end) folded into the agent's retried validation via a new `check`
  hook, so **both** a coverage gap *and* an overshoot re-prompt, with the coordinator re-asserting it
  as a terminal `OutlineCoverageError` backstop.
- **S2 — navigate the graph** (#168). A dense real graph (186 nodes / 286 edges) was an unnavigable
  `cose` hairball. Pure `graphFilters.ts` (type / degree / diacritic-folding name search) + a
  `cytoscape-fcose` layout — **client-side over the payload already fetched**, no backend change
  ([[graph-navigation]], DM-GN-1..4).
- **S3 — edge evidence + verifiable merges** (#172 be / #174 fe). Edge **provenance** existed in
  Postgres `staged_relations` but reached no client and had no by-`edge_id` read. Added a focused BFF
  read `GET …/relations/{edge_id}/evidence` ([[backend-for-frontend]]) + an `edge_id` index, and
  enriched every merge surface with type + aliases + a context quote + `target_canonical_name`. Writes
  nothing ([[graph-edge-evidence]], DM-EE-1..6).
- **S4 — suggest duplicate entities** (#179 be / #181 fe, **ADR 0010**). Re-points the §3.3 cascade
  matcher **inward** as a self-join over the *already-accepted* graph — it **suggests, never
  auto-merges** (INV-1/INV-9 hold), feeding the existing merge unchanged. Dismissals persist in a
  reversible Postgres pair-store ([[graph-cluster-dedup]], DM-CD-1..6; [[entity-resolution]]).
- **S5 — in-place editing on the canvas** (#186 S5a / #188 S5b-be **ADR 0011 + INV-10** / #190 S5b-fe).
  A shared `EntityEditPanel` core the reader *and* canvas compose; then the first edge-**write** slice:
  the §4 `edge_uid` surrogate handle ([[surrogate-key]]) + an atomic `retarget_relation`
  ([[graph-canvas-editing]], DM-S5-1..6).
- **S6 — predicate- and type-name normalisation** (#207 read / #212 apply / #214 fe / #216 tune).
  Defining finding at the *storage* layer: a predicate **is** the Neo4j relationship type (part of the
  content-addressed edge id) so renaming it **re-keys every bearing edge**, while an entity type **is**
  a node property so renaming it is a bulk `SET n.type` ⇒ **one shared suggest engine, two forked apply
  paths**. INV-10's first realized consumer ([[graph-name-normalisation]], DM-NN-1..6;
  [[controlled-vocabulary]]).
- **S7 — the reader as a correction surface** (#222, + a perf follow-up #223). The verify-first survey
  found the §3.5 *correction* surface already complete, so the slice instead closed a **spec drift**:
  §3.5 had promised a tooltip "brief description" **no entity has ever carried**. Resolved by deriving
  it from the graph — up to three relations, one line per distinct neighbour, most-connected first,
  `+N more`, read-time, no stored field, no LLM. This **supersedes DM-IH-8** (see
  [[m4-inline-highlights]]). The follow-up cached label embeddings on the app-lifetime
  `LabelVocabularyReader`, taking a vocabulary load ~14 s → ~1.4 s.

**Next — the Grzymalin reality check** (opened Session 102, 2026-07-24). The fork is between deeper
**extraction** work (spec §5: re-extraction, an eval baseline, relation deep-modelling) and **V2 Editing**
(§4), and it was gated on a prerequisite: **run fresh sample text end-to-end first**, because the working
graph has been hand-curated across S4–S7 and no longer shows what the *pipeline* produces — deciding from
it reads the wrong evidence. This milestone *is* that run: the pipeline **unaided** over a real, English,
non-fiction research corpus about the village of Grzymalin (half-synthetic Gemini Deep Research), replacing
the synthetic Oakhaven sample. Deliberately small; the fork stays **open** and is locked only in the
milestone's last session, on the run's evidence. A related direction is on record as a *fork input* — the
owner's *"Story Forge → History Forge"* framing (more research documents to come; timeline/temporal ordering
and cross-document entity joining become first-class), which weights the fork toward deeper extraction
without locking it, and raises a **spec-identity watch** (spec §2 is narrative-framed, the corpus is
non-fiction — a *reversible*-decisions signal, not a stop-and-amend yet). The **world graph** (cross-story)
remains **post-PoC** (`docs/BACKLOG.md`). INV-2's consent gate stays **deferred past M3** (persona-justified,
2026-06-15).

---

## The nine layers (system altitude)

Each layer asks a different question. An unconsidered layer is a blind spot; where a layer
genuinely does not apply, I **name the empty box** rather than leave it blank.

### 1. User / personas
One persona, full trust, local (see [[project]] Layer 1). The architectural payoff: no
inter-user authn/authz, no tenancy, no per-user limits. The only real **trust boundary**
([[trust-boundary]]) is **machine ↔ external LLM provider**, crossed whenever text is sent to
a cloud model.

### 2. Business
Public portfolio + architecture-exploration (currently primary) **and** an authoring tool
(designed-for, currently aspirational — the PoC content is LLM-generated, no real manuscript)
— see [[project]] Layer 2. The portfolio
driver imposes an unusual constraint: *the architecture must be legible from outside*. That is
itself an architectural force — it pushes toward small, named, individually-testable agents and
visible decision records rather than clever density.

### 3. Domain — the ubiquitous language
The nouns and verbs the system lives in (a *ubiquitous language* is one shared vocabulary used
identically in conversation, spec, and code, so there is no translation layer to drift). Core nouns: **Story → Chapter → Scene → Paragraph** (the document
tree); **Entity** (a character/place/object/concept), **Relation** (a typed edge between
entities), **Candidate** (a proposed entity *before* a human accepts it), **Mention** (where an
entity appears in a paragraph). Core verbs: *chunk, extract, match, judge, review, merge*.
Authoritative definitions: spec App. A + §3. The naming discipline is enforced end-to-end —
e.g. `order_index` (never `order`) is the same token in the DB column, the Pydantic field, and
the JSON (§6.4), so there is no DB↔API mapping layer.

### 4. Data — entities, ownership, keys
Two stores, split by *shape*. The concrete schema is **not** restated here — it lives in spec
§6.4, the Alembic migrations (Postgres), and `infra/neo4j/init.cypher` (Neo4j). What the vault
adds is the *architectural reading* of that split:
- **Postgres** owns the *document structure + metadata* (the chapter/scene/paragraph tree, the
  entity↔paragraph occurrences, the edit history). Sibling ordering is a plain integer ordinal
  renumbered on reorder — a fractional/lexical rank was consciously rejected as speculative (§6.4).
- **Neo4j** owns the *knowledge graph* (entities + dynamically-typed relations). Multi-tenancy
  is by `project_id`/`world_id` *property filter*, not a database-per-project (Neo4j
  multi-database needs Enterprise — rejected at §6.4).
- **The ownership seam worth naming** (the vault's value-add, absent from the spec): an entity's
  *identity and relations* live in Neo4j; its *textual occurrences* live in Postgres and
  reference the Neo4j entity id. The two stores **cannot share a transaction**, so that
  back-reference is a consistency seam to watch — see [[open-questions]] OQ-1.

### 5. Behavior — state machines, not statuses
The system's life is a **pipeline with a human gate**, best modelled as state machines
(explicit states + the *only* legal transitions between them; see [[state-machine]]), not loose
status flags. Two are worth modelling explicitly later
(queued in [[open-questions]], not drawn in this seed run):
- **Candidate lifecycle:** `extracted → matched(auto) | ambiguous → judged → {merge-proposed |
  new-proposed} → (human) → {merged | created | rejected}`. The terminal states and the
  *human gate* before any merge are the crux (see Errors + invariant #1).
- **Ingest job lifecycle:** `uploaded → chunked → structured → extracting → graphed`, with
  partial-failure recovery (what happens if extraction dies mid-story?).
A transition's **guard** is where an invariant is enforced (a move is legal only if its
precondition holds); its **effect** is where evidence is born (e.g. writing an `edit_history`
or audit row). Effect is mandatory on every transition — that is the Compliance layer
happening in real time.

### 6. Errors — failure modes, fail-open vs fail-closed
The governing choice: on uncertainty, **fail-closed** (on failure or doubt, *stop and ask the
human* rather than proceed; see [[fail-closed]]). The cascade is
designed exactly this way: anything the automated stages can't resolve with high confidence
**falls through to the human** (Stage 4), never auto-merges (§3.3). Other failure modes the
architecture must answer (some still open):
- LLM returns malformed JSON → parse, validate against a Pydantic schema, retry N times, then
  give up with a clear error (the `ChunkingAgent` pattern, to be mirrored — §6.5).
- Provider rate-limits or errors → router fails over to the next provider *in the same tier*,
  swap logged (§6.5).
- `cloud_free` GPU quota exhausted → **pause and ask the user** (resolved — OQ-3 / ADR 0003 / spec
  §6.5 step 5; never silent paid escalation, and on a GPU-less host `local_small` isn't a degrade
  target — the cheapest cloud_free model is).
- Two-store write (Neo4j entity + Postgres mention) partially fails → **no shared transaction**;
  reconciliation strategy is an open question.

### 7. Security — threat model, abuse paths
With no human trust boundary, the threat model is dominated by **two** axes:
- **Supply chain** — the most-invested-in control: every dependency pinned + ≥14 days old,
  images pinned + ≥7 days + Trivy-scanned, secrets only in `.env`, no telemetry (§6.7). The
  agent is even *deny-ruled* from reading `.env`. This is unusually strong for a solo tool and
  is a deliberate portfolio signal.
- **Untrusted text into LLM prompts** — the author's narrative is trusted, but *prompt structure
  must still be rendered only from trusted templates, never reparsed from model output mixed
  with story text*, or a paragraph containing fake JSON / `[ROLE]` markers could forge
  structure (prompt-injection-by-structure). This is encoded in the `/review-pr` skill and is
  the rule that hardened `ChunkingAgent`. See [[open-questions]] for the `ExtractionAgent` pass.

### 8. Compliance / Audit — provable adherence, durable evidence
A distinct axis from Security: Security asks *can an attacker break in?*; Compliance/Audit asks
*can we prove what happened?* (see [[compliance-audit-layer]]). Story Forge has no external
regulator, but it has a strong **self-imposed** audit requirement driven by both business
drivers:
- **`edit_history`** as an append-only `(before, after, intent, source, model, prompt,
  accepted)` log — explicitly a *future training dataset* (§4.2, §11). This is the loudest
  evidence trail in the system, and it makes Compliance/Audit a first-class layer here despite
  the absence of any regulator.
- **Every LLM call logged** (prompt, response, tokens, cost, latency — §11 observability) and
  **budget-recorded** (§6.6).
- **Reversibility** (§11): every automatic decision manually undoable — evidence that the human,
  not the model, owns the graph.

### 9. Operations — observability, diagnostics, runbooks
Solo + local, so "ops" is lightweight but present: docker-compose up, CI as the only place the
service-container/image-scan jobs run, the **agent-activity panel** (§8.5) that surfaces *which
tier/model/cost* ran each step (observability made visible — itself a portfolio artefact), and
a status endpoint exposing budget + Ollama GPU-quota (M2.S2). No alerting, no multi-host, no
on-call — **n/a, by the single-user-local design** (named, not blank).

---

## Nine-station snapshot (the system's enforcement lifecycle)

The nine **stations** are a separate checklist from the layers: layers are dimensions of
*analysis*; stations check whether each *control* in a feature's lifecycle is present
(Identity → Intent → Policy → Decision → Access → Monitoring → Evidence → Expiry → Review).
Applied to the system as a whole, with empty boxes named:

| Station | Present? | Where |
|---|---|---|
| **Identity** | n/a — single local user, no auth | (no login by design) |
| **Intent** | ✅ | the human explicitly triggers upload / structure / (later) accept-merge |
| **Policy** | ✅ partial | spec §6.7 security baseline; the cascade thresholds (§3.3); budget cap (§6.6) |
| **Decision** | ✅ | router tier choice (§6.5); cascade stage decisions; **human** at Stage 4 |
| **Access** | n/a — no inter-user access control | localhost-only binding is the only "access" gate |
| **Monitoring** | ✅ | `GET /llm/status` + the `llm_calls` ledger (M2.S2) + the **agent-activity panel** + the read-only **graph viewer** that surface them (M2.S5, PR #51) — incl. `latency_ms` |
| **Evidence** | ✅ designed | `edit_history`, per-call LLM logs, reversibility (§4.2, §11) |
| **Expiry** | ◻ gap | no retention/cleanup policy for uploads, logs, or orphaned sandboxes — **open** |
| **Review** | ✅ | Stage 4 human-in-the-loop *is* the review station, by design (§3.3) |

The weak station that remains is **Expiry** (no retention/cleanup for uploads, logs, or orphaned
sandboxes) — logged in [[open-questions]] (OQ-4, and OQ-15 for the absent operational logging). An empty
station is a design gap, not a non-event. (Monitoring closed at M2.S5.)

---

## What this seed pass surfaced (hand-off to open-questions)

The relentless **"but what if"** at system altitude raised, among others: the two-store
write consistency seam (§ Data/Errors), partial-failure recovery in the ingest job, the
`cloud_free`-quota-exhausted UX (since **resolved** → pause-and-ask, OQ-3 / ADR 0003), upload/log
**retention** (Expiry gap, still open), and the `ExtractionAgent` prompt-injection pass. These were
queued in [[open-questions]]; this seed note only *framed* them — the human decided (the M2.S2
cluster is now settled in `docs/decisions/0003`).
