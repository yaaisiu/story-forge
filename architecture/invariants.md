---
type: invariants
slug: invariants
updated: 2026-06-02
status: living
related: ["[[overview]]", "[[project]]", "[[open-questions]]"]
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
- **Enforced at:** the provider adapters + the router; no telemetry libraries exist anywhere
  (§6.7), so there is no other egress path by construction.
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
- **Enforced at:** the `EntityCandidate`/`RelationCandidate` Pydantic schemas (M2.S3) — string
  `type`, no `Enum`. Guard against a future contributor "tidying up" types into an enum.

### INV-5 — Every LLM call is recorded and budget-bounded
Every LLM operation records `model, input_tokens, output_tokens, cost_estimate` (and latency);
spend is aggregated per day/project/task-type; an emergency daily cap **hard-stops** further
paid calls when exceeded.
- **Source:** §6.6, §11 observability.
- **Enforced at:** the cost-tracking write on every router call + the cap check *before*
  dispatch (M2.S2). Guard: a call that would breach the cap is refused, not logged-after.
- **Note:** the cap is **fail-closed** — exceed budget ⇒ deny, never "allow and warn".

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
- **Enforced at:** the adapter layer (`adapters/llm/`) + the router; new providers are added by
  implementing the Protocol, never by branching call sites. See [[model-tier-routing]].

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
