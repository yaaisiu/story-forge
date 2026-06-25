# Adapters layer — the I/O bridges

> **Reference note.** What lives in `backend/src/story_forge/adapters/` and what each piece is for.
> The code and [`backend/src/story_forge/AGENTS.md`](../../backend/src/story_forge/AGENTS.md) own
> the details and stay current — this note is a map of the territory, not a copy of it.

## What this layer is responsible for

`adapters/` is the **only** layer that touches the outside world — PostgreSQL, Neo4j, the LLM
providers, and the filesystem. Every other layer stays pure: `domain/` and `agents/` define
`typing.Protocol`s for what they need (a store, a repo, an `LLMProvider`/`Router`), and an adapter
here is the concrete implementation of one. That inversion is what lets a domain test run without a
database and an agent test run against a mocked provider.

Nothing constructs an adapter except `main.py`, which wires the concrete classes onto `app.state`
and injects them into the agents and services (dependency injection). The inner layers never import a
concrete adapter — they only ever see the Protocol. See spec §6.4 (storage) and §6.5/§6.6 (LLM tier
+ cost) for the contracts these implement.

## Postgres stores

Plain async `psycopg` 3 with raw SQL — no ORM. Connection wiring lives in
[`db.py`](../../backend/src/story_forge/adapters/db.py): `connect` opens a connection with the
pgvector type registered (mandatory for any `vector(768)` column), `libpq_kwargs` translates the
SQLAlchemy-style `DATABASE_URL` into psycopg kwargs, and `get_connection` is the FastAPI
request-scoped dependency that commits on success / rolls back on error. A pool is deliberately
omitted — single-user local app, a connection per unit of work is enough.

Two connection patterns split the stores:

- **Request-transaction stores** take an `AsyncConnection` from the caller and leave the transaction
  boundary to it. [`postgres_repo.py`](../../backend/src/story_forge/adapters/postgres_repo.py) is
  the document tree (project / story / chapter / scene / paragraph CRUD) plus the cross-store
  `entity_mentions` and `mention_suppressions` row functions; rows map straight onto the domain
  models because the column and field names match.
- **Own-connection stores** open a short-lived **autocommit** connection per operation rather than
  sharing the request transaction. This is the non-obvious, load-bearing choice: it makes batch
  ingest **resumable**. Each paragraph's writes (and its `paragraph_processed` resume marker) commit
  as their own atomic unit, so a mid-batch pause (budget/quota) or crash leaves a durable record of
  which paragraphs are already done — sharing the request transaction would roll them all back and
  redo everything on the next run. Idempotent re-writes (`ON CONFLICT (id) DO NOTHING`, deterministic
  ids) make a retry safe.

The own-connection stores:

- [`postgres_candidate_store.py`](../../backend/src/story_forge/adapters/postgres_candidate_store.py)
  — the `candidates` staging table behind intercept-before-write (extraction stages here instead of
  writing the graph; the human review path reads/accepts/rejects through it) plus the
  `candidate_decisions` accept/reject evidence log and the resume checkpoint.
- [`postgres_relation_store.py`](../../backend/src/story_forge/adapters/postgres_relation_store.py)
  — the symmetric sibling for `staged_relations`. Its staging `insert` is a `@staticmethod` that runs
  on the *caller's* connection, so a paragraph's relations commit in the same transaction as its
  candidates and resume marker.
- [`postgres_mention_store.py`](../../backend/src/story_forge/adapters/postgres_mention_store.py)
  — the `entity_mentions` writer (and its manual-correction mutators / suppressions); reuses the
  single INSERT in `postgres_repo`, differing only in the connection.
- [`postgres_edit_store.py`](../../backend/src/story_forge/adapters/postgres_edit_store.py)
  — the `graph_edits` before→after ledger backing reversible human edits and the grouped undo stack
  (single edits and grouped operations like a merge, keyed by a `COALESCE(operation_id, id)` group).
- [`llm/postgres_cost_store.py`](../../backend/src/story_forge/adapters/llm/postgres_cost_store.py)
  — the §6.6 cost ledger (covered under the LLM tier below); it follows the same own-connection rule
  so a failed call's row survives even when the triggering request rolls back.

## The graph store

[`neo4j_repo.py`](../../backend/src/story_forge/adapters/neo4j_repo.py) is the knowledge-graph
store (spec §3.2 / §6.4): an async Neo4j reader/writer, one per process. Its central contract is
**upsert-by-id** — `create_entity` / `create_relation` `MERGE` on the unique deterministic `id` so a
retried human-accept never doubles a node or edge. This is *not* a name-merge: folding two surface
forms into one entity is the human's review act (`add_alias`), never automatic. Under
intercept-before-write the graph is written only by the accept path, never by extraction.

It reads/writes entities and relations, maps the domain `GraphEntity`/`GraphRelation` to/from Neo4j
(UUIDs as strings, `properties` as a serialised JSON string, `aliases` as a native list), and serves
the read paths: `list_entities`, `get_relations`, the project-scoped single-edge read, and
`get_neighbourhood` (the 1-hop ego-graph projection behind the reader side panel). The edit/merge
paths (`update_entity`, `delete_relation`, `delete_entity` via `DETACH DELETE`) sit under the human
gate. One detail worth calling out: an open-world relationship type can't be a bound Cypher
parameter, so it is interpolated through `_escape_rel_type`, which backtick-quotes and doubles
embedded backticks — the Cypher analogue of the prompt-injection-by-structure discipline.

## The LLM tier (`adapters/llm/`)

Implements the three-tier strategy from spec §6.5 (provider order + scope:
[ADR 0003](../decisions/0003-llm-router-provider-order-and-budget.md)). All providers are hand-rolled
over `httpx` — no vendor SDKs — and share an injectable transport so tests run without the network.

- [`base.py`](../../backend/src/story_forge/adapters/llm/base.py) — the seam. The `LLMProvider`
  Protocol (the async chat contract every provider implements) and the `Router` Protocol (the
  tier-picking face an agent calls), plus the shared data types (`Message`, `Usage`,
  `CompletionResult`, the `ModelTier`/`TaskWeight` literals) and the control-flow errors:
  `BudgetExceededError` (a spend ceiling — *pause and ask*, deliberately **not** an HTTP error),
  `QuotaExhaustedError` (free-tier quota spent), and `ProviderResponseError` (HTTP 200 with a
  malformed envelope — fail over, distinct from a schema-invalid body the agent retries).
  `estimate_cost` turns token counts + a per-1k price into a USD figure.
- [`ollama.py`](../../backend/src/story_forge/adapters/llm/ollama.py) — `OllamaProvider`, serving
  **both** the `local_small` and `cloud_free` tiers (same Ollama chat API, differing only by host
  and an optional API key). Free of USD charge; the cloud tier is metered in GPU-time.
- [`openrouter.py`](../../backend/src/story_forge/adapters/llm/openrouter.py) — `OpenRouterProvider`,
  the **only paid route built** (the preferred meta-endpoint reaching Grok/Claude/Gemini/GPT;
  per-vendor adapters deferred — ADR 0003). This is the **paid egress point**; it raises
  `BudgetExceededError` on the provider's HTTP 402 (out of credit) and reports a real USD
  `cost_estimate`.
- [`router.py`](../../backend/src/story_forge/adapters/llm/router.py) — `LLMRouter`, which picks the
  tier per call from the task's `weight`, fails over across a tier's providers with
  **error-discriminated** logic (429/5xx/transport → fail over; 401 → fail over but not "quota"; a
  budget refusal → re-raise, never escalate spend), enforces the fail-closed `DAILY_BUDGET_USD` cap
  *before* dispatch, and writes one ledger row per call (success, refusal, or failure). The
  schema-retry on invalid output stays the agent's job, not the router's.
- [`cost.py`](../../backend/src/story_forge/adapters/llm/cost.py) — the `CostStore` Protocol and its
  records (`LlmCallRecord`, the dashboard aggregates `DailyUsage`/`TaskTypeUsage`, the §8.5
  `LastCall`). Usage is system-derived by the adapter that served the call, never echoed from the
  caller, so the ledger can't be lied to.
- [`postgres_cost_store.py`](../../backend/src/story_forge/adapters/llm/postgres_cost_store.py) — the
  §6.6 cost ledger backed by the `llm_calls` table: appends usage rows, sums today's spend for the
  budget gate, and serves the dashboard / last-call reads.

## Other

- [`upload_storage.py`](../../backend/src/story_forge/adapters/upload_storage.py) — `save_upload`
  sandboxes an original uploaded file to disk (spec §6.7): named by the owning story's UUID (never
  the user-supplied filename, so a crafted name can't traverse paths), with owner-only permissions
  and no execute bit. The parsed text lives in Postgres; this keeps the raw original without trusting
  it as code.
- [`accepted_entity_reader.py`](../../backend/src/story_forge/adapters/accepted_entity_reader.py) —
  `AcceptedEntityReader` assembles the `AcceptedSnapshot` the §3.3 matching cascade runs against, in
  one batched pass per ingest run (one Neo4j read for the entities, two Postgres reads for their
  vectors and recent mention texts), so per-candidate matching is pure in-memory compute. It composes
  the Neo4j and Postgres adapters and returns a domain shape.

## How it connects

Every adapter here implements a `Protocol` defined in `domain/` or `agents/` (the `LLMProvider` /
`Router` Protocols live in `adapters/llm/base.py`, but agents type against them, not the concrete
classes). The inner layers never import a concrete adapter; `main.py`
([`backend/src/story_forge/main.py`](../../backend/src/story_forge/main.py)) constructs each adapter,
hangs it on `app.state`, and injects it into the agents and services. The conventions for this layer
(adapters implement domain Protocols; the three-tier LLM strategy; hand-rolled httpx; the router; the
cost ledger) are in
[`backend/src/story_forge/AGENTS.md`](../../backend/src/story_forge/AGENTS.md).

The sibling reference notes for the layers this one connects to: [`backend-domain.md`](./backend-domain.md)
(the shapes mapped onto storage), [`backend-agents.md`](./backend-agents.md) (the services these
adapters back), and [`backend-api.md`](./backend-api.md) (the HTTP surface).
