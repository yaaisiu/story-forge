---
type: invariants
slug: invariants
updated: 2026-06-11
status: living
related: ["[[overview]]", "[[project]]", "[[open-questions]]", "[[2026-06-11-architecture-review]]", "[[candidate-lifecycle]]"]
---

# Invariants — Story Forge

An **invariant** (**niezmiennik**) is a rule the system must **never** break, across every
edge case, race, and partial failure. It is a design contract: if it can be violated, that is
a bug regardless of what any single feature "intended". This note collects them. Each is
derived from a spec non-negotiable and cites its source of truth — the spec remains
authoritative; this note is the *named, enforceable* projection of it.

Each invariant names **where it is enforced** (the guard) — because an invariant nobody
enforces is just a wish.

---

### INV-1 — Human-in-the-loop on every entity create/merge
No entity is ever created or merged into the graph without an explicit human decision. The
automated cascade may *propose*; only the author *commits*. (**fail-closed** — on any
uncertainty, fall through to the human, never auto-merge.)
- **Source:** §3.3 Stage 4 ("CRITICAL"), §11 reversibility.
- **Enforced at:** the Stage-4 review gate (M3). Guard: a candidate cannot transition to
  `merged`/`created` except via a human action. *Not yet built — this is the contract M3 must
  honour.*
- **Why it matters here:** the graph is the world's source of truth; ceding entity identity to
  a model would make the whole graph untrustworthy. See [[human-in-the-loop]].

### INV-2 — Text leaves the machine only to the chosen provider, only with consent
Story text is never transmitted anywhere except the LLM provider the user explicitly selected
for that call, and the UI makes the crossing explicit ("sending fragment to Anthropic, OK?").
- **Source:** §11 privacy; the machine ↔ provider [[trust-boundary]].
- **Enforced at:** *(as-built, M2.S2)* paid egress now exists — `OpenRouterProvider`
  (`adapters/llm/openrouter.py`), selected by the router (`adapters/llm/router.py`). The **consent
  UI** the invariant demands ("sending fragment to Anthropic, OK?") is **deferred and now unscheduled**
  — its ADR-0003-D5 landing target was M2.S5, but **M2.S5 shipped a *read-only* viewer + panel without
  it** (PR #51), so the gate is re-pointed to the **M3 §3.3 review-queue UI** (the first rich human-gate
  surface; see [[m3-cascade-matching]] DM7). Until then the egress point carries a documented in-code
  marker (ADR 0003 D5), so the actual guard remains "no-telemetry (§6.7) + egress only to the
  router-selected provider", honestly narrower than the rule it will become (same as-built honesty as
  INV-1). No telemetry libraries exist anywhere.
- **Decision (ADR 0003, 2026-06-02; re-dated 2026-06-11):** the consent gate is **deliberately
  deferred**, not forgotten — the PoC handles no security-sensitive data. **As-built reality
  (2026-06-11, `[[2026-06-11-architecture-review]]`):** the M2.S6 smoke **fired real paid egress
  gate-less** (Ollama Cloud + an OpenRouter model) — the OQ-6 "fail-open by sequencing" window is no
  longer hypothetical, it occurred. Accepted at PoC scale, but the deferral's *schedule* is now
  re-pointed to M3 (above) rather than left pointing at a milestone that passed. Read the narrow guard
  as a *considered, re-dated* deferral.
- **Why it matters:** this is the *only* real trust boundary in a single-user local app;
  everything the Security layer protects funnels through it.

### INV-3 — Every automatic decision is manually reversible
No automatic action is final. The human can always undo a merge, a split, an extraction, an
edit. "Never trust the LLM and forget."
- **Source:** §11 reversibility.
- **Enforced at:** `edit_history` (append-only change log) + graph operations designed as
  undoable; the review queue. See [[compliance-audit-layer]].

### INV-4 — Open-world ontology: types are never a closed enum
Entity `type` and relation type are open-world (**ontologia otwarta** — the set of kinds is not
fixed up front and grows as real text demands; see [[open-world-ontology]]). Code must treat
`type` as a free string with examples that *constrain but do not restrict*, never a hard enum.
- **Source:** §3.2 ("the entity schema is NOT defined upfront … extensible").
- **Enforced at:** *(as-built, M2.S3)* the `EntityCandidate.type` / `RelationCandidate.predicate`
  fields (`agents/extraction_agent.py`) are free `str`, **no `Enum`** — a never-before-seen type
  validates. Guard against a future contributor "tidying up" types into an enum.

### INV-5 — Every LLM call is recorded and budget-bounded
Every LLM operation records `model, input_tokens, output_tokens, cost_estimate`; spend is
aggregated per day/project/task-type; an emergency daily cap **hard-stops** further paid calls when
exceeded.
- **Source:** §6.6, §11 observability.
- **Enforced at:** *(as-built, M2.S2)* `LLMRouter.complete` (`adapters/llm/router.py`) checks
  `spend_today_usd() >= DAILY_BUDGET_USD` **before** dispatch (fail-closed), and `PostgresCostStore`
  (`adapters/llm/postgres_cost_store.py`) writes one `llm_calls` row on **every terminal edge the
  router currently handles** — success, refusal, and failure (HTTP `HTTPStatusError`, transport
  `RequestError`, `BudgetExceededError`). Guard: a call that would breach the cap is refused, not
  logged-after.
- **OQ-10 closed (as-built, M2.S3 / PR #42):** the former coverage gap — a provider returning `200`
  with a *malformed envelope* — is now recorded + failed-over, not crashed. `ProviderResponseError`
  (`adapters/llm/base.py`) is raised by **both** adapters at the envelope-unwrap point (incl. the
  null-`content` case) and caught by the router (`router.py`), which writes a failure row + fails over
  like a 5xx. INV-5 is now **total** over the edges the router handles. (History: `[[open-questions]]`
  OQ-10, `[[m2s3-extraction-agent]]` D2.)
- **Note:** the cap is **fail-closed** — exceed budget ⇒ deny, never "allow and warn".
- **Record durability (as-built):** the ledger commits on its **own short-lived connection**, not the
  request transaction — so a *failure* row survives a request that rolls back on the very failure it
  records (the "explain why a batch stopped" trail must not vanish with the error). Recorded in
  `docs/PLAN_SHORT.md` Decided; see the out-of-band-audit-logging note in `learning-log`.
- **`latency` (OQ-9, resolved 2026-06-11 → option a; built):** a usage row records `latency_ms`
  (elapsed time around `provider.complete`; recorded for every *dispatched* call, null only for a
  pre-dispatch budget refusal that never reached a provider). *(as-built, M2.S5 / PR #51)* — Alembic
  `2026_06_11_0956-…_add_latency_ms_to_llm_calls.py`, captured in `router.py`, recorded by
  `postgres_cost_store.py`, shown in the §8.5 panel. Added to spec §6.6's enumeration. History:
  `[[open-questions]]` OQ-9.
- **Shape decided (ADR 0003, 2026-06-02):** the usage record grows on `CompletionResult`/the Protocol
  (`model`, `input_tokens`, `output_tokens`, nullable `gpu_seconds`, `cost_estimate`); `OllamaProvider`
  stops discarding the eval counts; one `llm_calls` table, nullable per tier; tier/provider/model are
  **system-derived, not caller-echoed** (closes the INV-7 near-miss). On cap reached → pause-and-ask,
  not silent kill. Best-effort under concurrency, bounded one-call overshoot (TOCTOU, documented).

### INV-6 — Secrets only in `.env`; API keys never logged
No secret is ever committed; only `.env.example` with **non-functional** placeholders. Logging
middleware strips `Authorization`, `X-API-Key`, and similar before any log line is emitted.
- **Source:** §6.7.
- **Enforced at:** `.gitignore` + `detect-secrets` pre-commit + CI; the log-redaction
  middleware; a harness `deny` rule even bars the agent from reading `.env`.

### INV-7 — One adapter per provider protocol; tier is config, not a code fork
All providers implement the one `LLMProvider` Protocol. In particular, local-small and
cloud-free **both speak the Ollama API and share one `OllamaProvider`** — the difference is the
host URL + optional key, a config flip, not a second code path.
- **Source:** §6.5 ("drastically reduces the number of code paths").
- **Enforced at:** the adapter layer (`adapters/llm/`) + the router. *(as-built, M2.S2 — near-miss
  closed)* the ledger records the **router's own chosen `tier`**, `provider = type(provider).__name__`,
  and `model` from the provider's response — all **system-derived**, never the caller's echoed
  `model_tier` (which survives on `CompletionResult` only cosmetically; the ledger ignores it). New
  providers are added by implementing the Protocol, never by branching call sites. See
  [[model-tier-routing]].

### INV-8 — [TEMPORARY · M2-scoped] No dedupe yet — every candidate is a new entity
Through Milestone 2, extraction writes **every** candidate as a fresh Neo4j node with **no**
matching/merge. This is a *deliberately temporary* invariant whose purpose is to expose the
duplicate problem that M3's cascade then solves.
- **Source:** §9 Milestone 2 ("save entities to Neo4j without cascade").
- **Lifespan:** holds until M3 begins; at that point it is **superseded by INV-1** (the human
  gate). Flagged temporary so no one mistakes "no dedupe" for a permanent design stance.
- **Why list a temporary rule:** during M2 it *is* a contract the code must hold (two identical
  extractions must produce two nodes — there is even a test for it, §M2.S4); naming it prevents
  a well-meaning early dedupe from sneaking in before M3.
- **Enforced at (as-built, M2.S4 / PR #48):** `Neo4jRepo.create_entity` uses `CREATE`, never
  `MERGE` (the load-bearing keyword — a `MERGE`-on-name would silently violate this), and the
  `ExtractionCoordinator` does no matching. The no-dedupe property is pinned by tests at four
  levels (neo4j_repo, the pure `proposal_to_graph` mapping, the coordinator, and live persistence).
