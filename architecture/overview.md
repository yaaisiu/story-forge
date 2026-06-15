---
type: overview
slug: overview
updated: 2026-06-15
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
  spans per paragraph (`agents/prener_agent.py`).
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

**M3 in progress — Stages 1–3 built, proposal-only / unwired (PRs #56/#58/#60):**
- **M3.S1** — `MatchingAgent` **Stage 1** (RapidFuzz token-set vs `canonical_name`+aliases; PR #56).
- **M3.S2** — **Stage 2** embedding cosine + the **pgvector foundation** (PR #58): real `vector(768)`
  on `entity_mentions`, `register_vector_async`, the multilingual mpnet model pinned via the §6.7
  HF-model channel. EmbeddingAgent built but **not** wired (mentions still written `embedding=None`).
- **M3.S3** — `JudgeAgent` **Stage 3** (PR #60): LLM-as-judge, cloud_free via the router
  (`task_type="judge"`), strict `{match,confidence,reasoning}`, merge iff `match AND conf>0.8`.
- Stages 1–3 are proposal-only through their own sessions; they are **wired into the live path by
  M3.S4a** (below).

**M3.S4a — intercept-before-write, the backend milestone close (built, this PR / ADR 0004):**
- The `ExtractionCoordinator` no longer writes the graph: it *stages* each candidate into a new
  Postgres `candidates` table with the cascade's proposal (embed-on-extract → Matching S1/S2 → Judge
  S3, fail-closed), writing **zero** Neo4j nodes. The graph is written **only** by the human-accept
  path (`CandidateReviewService` → `POST /stories/{id}/candidates/{cid}/accept|reject`).
- This **retires INV-8 → lands INV-1's first enforcer + INV-9** ("no automated stage writes the
  graph"), finalises `[[candidate-lifecycle]]` to `living`, and is recorded in **ADR 0004**. Mentions
  move to accept-time (with the candidate's context vector); the resume checkpoint is a
  `paragraph_processed` marker; accept/reject leave an append-only `candidate_decisions` evidence row.
  The store-down→503 fail-closed mapping + a Neo4j-driver lifespan close landed with it.

**Planned, not yet built:**
- **M3.S4b** (frontend) — the `features/extraction-review/` review-queue UI (§3.3 Stage-4 elements +
  keyboard nav) consuming S4a's endpoints; the relation graph-write + re-point-on-merge (S4a stages
  relation data but writes no edge). INV-2 consent gate is **deferred past M3** (2026-06-15,
  persona-justified).

So today Story Forge ingests and structures text, produces deterministic candidate spans,
**extracts entity/relation candidates with an LLM** (routed, budgeted, recorded), runs the §3.3
cascade and **stages** each candidate with a NEW-vs-MERGE proposal — and writes the graph **only when
the author accepts** at the (backend) review queue (INV-1/INV-9). The graph is empty until reviewed;
the §3.3 dedupe is now the human's gated decision, not an automatic write.

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
Personal tool **and** public portfolio, equal weight (see [[project]] Layer 2). The portfolio
driver imposes an unusual constraint: *the architecture must be legible from outside*. That is
itself an architectural force — it pushes toward small, named, individually-testable agents and
visible decision records rather than clever density.

### 3. Domain — the ubiquitous language
The nouns and verbs the system lives in (a *ubiquitous language* — **język wszechobecny** — is
one shared vocabulary used identically in conversation, spec, and code, so there is no
translation layer to drift). Core nouns: **Story → Chapter → Scene → Paragraph** (the document
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
(**maszyny stanów** — explicit states + the *only* legal transitions between them; see
[[state-machine]]), not loose status flags. Two are worth modelling explicitly later
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
The governing choice: on uncertainty, **fail-closed** (**domyślnie zamknięty** — on failure or
doubt, *stop and ask the human* rather than proceed; see [[fail-closed]]). The cascade is
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
