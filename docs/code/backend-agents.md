# Agents layer — the ingest pipeline and human-gate services

> **Reference note.** What lives in `backend/src/story_forge/agents/` and what each piece is for.
> The code and [`backend/src/story_forge/AGENTS.md`](../../backend/src/story_forge/AGENTS.md) own
> the details and stay current — this note is a map of the territory, not a copy of it.

## What this layer is responsible for

`agents/` is the orchestration layer: each module owns **one logical task** from spec §6.5 —
chunking, extraction, embedding, matching, judging, staging, human review, manual editing. The
modules compose pure `domain/` logic with I/O that lives behind the `LLMProvider` / `Router`
Protocols (and other store Protocols) declared in `adapters/`. By rule, an agent imports a
*Protocol*, never a concrete adapter, so every module here is unit-testable against fakes — the
seam `main.py` wires the real adapters into. The one sanctioned exception is **deterministic local
NLP**: `prener_agent.py`, `embedding_agent.py`, and `matching_agent.py` import spaCy / RapidFuzz /
sentence-transformers directly, because a single local implementation with no provider to choose
gains nothing from a Protocol (see the `AGENTS.md` "deterministic local NLP" rule).

The LLM-driven agents share one contract — **load prompt → call router/provider → parse + validate
→ retry on schema failure** — factored into [`agents/validation.py`](../../backend/src/story_forge/agents/validation.py)
(`validate_with_retry`) and [`agents/json_output.py`](../../backend/src/story_forge/agents/json_output.py)
(`extract_json`). Each agent keeps only what is genuinely its own: its Pydantic schema, its call
shape, and its give-up error. Prompts are never inlined — they live as Jinja2 templates in
[`prompts/`](../../backend/src/story_forge/prompts/) (PL + EN variants), loaded by `render_messages`.

## The pipeline, in order

1. **chunk** — raw text → outline. `chunking_coordinator.py` dispatches the three §3.1 modes,
   calling `chunking_agent.py` for the LLM paths.
2. **extract** — per-paragraph entity/relation candidates. `extraction_coordinator.py` drives a
   whole story's paragraphs through `extraction_agent.py`, resumably.
3. **embed + match (the §3.3 cascade, Stages 1–3)** — `candidate_staging.py` runs each candidate
   through `embedding_agent.py` (encode context) → `matching_agent.py` (Stage 1 fuzzy, Stage 2
   cosine) → `judge_agent.py` (Stage 3 LLM judge, only when Stages 1–2 stay ambiguous).
4. **stage** — `candidate_staging.py` attaches a *proposal* to each candidate; the coordinator
   persists them. **Nothing here writes the graph** (intercept-before-write).
5. **human review → graph** — `candidate_review.py` (accept/reject entities),
   `candidate_rematch.py` (re-match siblings on accept), `relation_review.py` (decide edges), and
   `entity_edit.py` (edit committed graph) are the **only** code that writes Neo4j, each reached
   only from an explicit human action (INV-1 / INV-9).

## Modules

### `chunking_agent.py` / `chunking_coordinator.py` — raw text → reviewable outline (§3.1, §7 step 2)

[`chunking_agent.py`](../../backend/src/story_forge/agents/chunking_agent.py) turns *unmarked* text
into a proposed chapter/scene hierarchy via an `LLMProvider`, and is the canonical example of the
agent pattern. `select_chunking_tier` picks `local_small` only when a local tier is configured and
the text is short enough, else `cloud_free` (the default on a GPU-less host). A malformed-200
envelope becomes a `ChunkingError` (→ the route's 502) rather than being retried, since chunking
holds a raw provider with no router failover.
[`chunking_coordinator.py`](../../backend/src/story_forge/agents/chunking_coordinator.py) is the
seam wired in `main.py`: it dispatches the three §3.1 modes — **manual** (pure domain parser, no
LLM), **hybrid** (parse the author's anchors, LLM-fill only the untitled spans, preserve every
explicit `##`/`###`), and **auto** (LLM over the whole text). It converts a proposal's
paragraph ranges back into an `Outline` and guards over-long input with `ChunkingTooLongError`.
Stop-silent-data-loss (graph-quality §3 S1): the agent folds the paragraph-coverage invariant
(`domain.paragraph_range_problem`) into its retried validation — a gap or an overshoot re-prompts —
and the coordinator re-asserts it as a terminal backstop (`OutlineCoverageError` → 502).

### `extraction_agent.py` — one paragraph → entity & relation candidates (§3.2, §7 step 4)

[`extraction_agent.py`](../../backend/src/story_forge/agents/extraction_agent.py) is the first agent
wired to the **router** (so tier selection, failover, the budget cap, and the cost ledger all live
there). It proposes `EntityCandidate` / `RelationCandidate` lists for one paragraph — *candidates*,
not graph entities: a candidate carries a surface `candidate_name`, never a resolved
`canonical_name`. After validation it drops any `evidence_quote` that is not a whitespace-normalised
substring of the source paragraph (the G5 grounding soft-flag) while keeping the candidate. An empty
result is a legitimate success (a transition paragraph), so it is never retried.

### `extraction_coordinator.py` — the resumable batch driver (§7 steps 4–6, §9 M3)

[`extraction_coordinator.py`](../../backend/src/story_forge/agents/extraction_coordinator.py) drives
a whole story's paragraphs through extraction and then the cascade staging, **intercept-before-write**
(it touches no Neo4j). Two load-bearing properties: it owns **pause-and-ask** — the router's
`BudgetExceededError` / `QuotaExhaustedError` propagate up through the agent and the judge, and this
driver catches them to return a `paused` result *before* persisting the in-flight paragraph; and
resume granularity is the **paragraph**, checkpointed by a marker row (written even for
zero-candidate paragraphs) so a re-run picks up cleanly and idempotently.

### `embedding_agent.py` — the Stage-2 encoder (§3.3, M3.S2)

[`embedding_agent.py`](../../backend/src/story_forge/agents/embedding_agent.py) encodes a
candidate's context sentence to a 768-dim vector with sentence-transformers — deterministic local
compute, no LLM, no network. The heavy torch stack is imported lazily and the model cached, so
importing the module or reading the pin constants costs nothing. The weights are pinned by
**immutable commit revision** (`MODEL_REVISION`, the §6.7 HuggingFace-model channel), so even a cold
cache fetches the exact bytes rather than HEAD.

### `matching_agent.py` — the deterministic cascade, Stages 1 & 2 (§3.3, M3.S1–S2)

[`matching_agent.py`](../../backend/src/story_forge/agents/matching_agent.py) is the cheap
deterministic core of the cascade. **Stage 1** (`stage1`) scores a candidate's surface form against
each existing entity's `canonical_name` + aliases with a RapidFuzz token-set ratio; **Stage 2**
(`stage2`) takes the max cosine of the candidate's context vector against an entity's stored mention
vectors. `classify` maps a fuzzy score to the §3.3 bands and is **fail-closed**: a score exactly on
the merge edge escalates rather than auto-merging (a diminutive like "Bronek"↔"Bronisław" must not
be merged on string distance alone). Pure helpers (`cosine_similarity`, `classify`, the `_rank`
ranking shared by `top_alternatives` and the manual-handpick `search_entities`) are CI-tested
without loading any model. Both stages only *propose* — a human commits at Stage 4 (INV-1).

### `judge_agent.py` — the Stage-3 LLM judge (§3.3, M3.S3)

[`judge_agent.py`](../../backend/src/story_forge/agents/judge_agent.py) is the **only** cascade rung
that burns LLM tokens, reached only on candidates Stages 1–2 left ambiguous. It asks the model one
question — "is this candidate the same entity?" — and validates a strict `{match, confidence,
reasoning}` verdict (a degenerate body fails and retries). Its "couldn't judge" contract is
**total**: it raises `JudgeError` on *any* failure to produce a verdict, including a terminal
transport/envelope failure it converts from the router — so a consumer that fail-closes on
`JudgeError` catches a provider outage too, rather than 502-ing the whole batch. Only the
pause-and-ask signals propagate past it. `classify_verdict` is stricter than the spec's literal
threshold: a self-declared non-match never merges however confident.

### `candidate_staging.py` — the cascade glue, run per paragraph (§3.3, M3.S4a)

[`candidate_staging.py`](../../backend/src/story_forge/agents/candidate_staging.py) (`CandidateStager`)
runs one paragraph's candidates through the whole cascade — derive a ±200-char context window →
`encode` → Stage 1/2 → Stage 3 (only when still ambiguous) — and returns the `StagedCandidate` rows
plus the paragraph's raw relation proposals. It does no I/O itself (the accepted-graph snapshot is
read once per run by the coordinator) and is **fail-closed throughout**: an embedding failure drops
Stage 2 but keeps Stage 1 + Stage 3; a `JudgeError` yields a NEW/"uncertain" proposal; nothing
auto-commits or crashes the batch. Budget/quota signals deliberately propagate (the coordinator
pauses on them).

### `candidate_review.py` — the human-accept write path (§3.3 Stage 4, §7 step 7, M3.S4a)

[`candidate_review.py`](../../backend/src/story_forge/agents/candidate_review.py)
(`CandidateReviewService`) is INV-1's first enforcer: the only code that writes the graph, and only
on an explicit human accept (create a new entity, merge into an existing one, or reject). Two
contracts make the cross-store write safe: the candidate's **status flip is the last write** and all
ids are derived deterministically from the candidate id (MERGE-on-id), so a crash-and-retry
produces no duplicate node, mention, or evidence row; and it **re-validates the merge target** at
accept time, raising `StaleMergeTarget` (→409) rather than aliasing onto a node merged away since
staging. Every terminal leaves a durable, reversible evidence row (INV-3).

### `candidate_rematch.py` — on-accept intra-batch dedup (§3.3, M3.S4c)

[`candidate_rematch.py`](../../backend/src/story_forge/agents/candidate_rematch.py)
(`ReMatchService`) closes the gap that the cascade only matches against the graph as it stood at
*extraction* time, so within-batch duplicates (the canonical "Janek" ×3 against an empty graph)
stage as independent NEW proposals. On a human accept it re-runs the **deterministic** matcher
(Stages 1–2 only, never the judge) over still-pending candidates against the just-accepted entity
and flips a strong match's staged proposal `new → merge`. It is **staging-only** (writes the
Postgres `candidates` table, never Neo4j — INV-9 holds), **monotone** (only ever upgrades, so a
re-run is a no-op), and adds no reads beyond its own `list_pending`. It is invoked best-effort and
fail-closed *after* an accept commits, so a re-match failure never rolls back the human's accept.

### `relation_review.py` — the human-gated edge write path (§3.3 Stage 4, M3.S4e)

[`relation_review.py`](../../backend/src/story_forge/agents/relation_review.py)
(`RelationReviewService`) is the symmetric gate for *edges* that `candidate_review.py` is for nodes
— the only code that writes a graph edge, on an explicit human decide. A staged relation's endpoints
are surface strings; the edge is written **lazily**, resolving each string to the *committed* id of
the same-paragraph accepted candidate it names (a merged candidate resolves to its target, so a
merge needs no edge re-point). The edge id is a deterministic function of the resolved triple
(idempotent, status-flip last), and it **re-resolves at commit** (TOCTOU), refusing a stale/held
edge (→409). Held endpoints and self-loops are simply never committable.

### `entity_edit.py` — the human edit handler for committed graph state (M4.S3a–c)

[`entity_edit.py`](../../backend/src/story_forge/agents/entity_edit.py) (`EntityEditService`) is the
first slice that *edits* already-committed graph objects, the third human-reached writer alongside
accept and decide. One service grows operations rather than minting writer classes (broaden-don't-
mint, ADR 0006): edit an entity's fields, add/remove relations, merge/delete entities, tag/un-tag/
re-bound occurrences, and **undo the last operation**. Write order mirrors the other handlers —
**graph mutation first, evidence row last** (INV-3) — so a crash leaves the edit applied but
unlogged and a retry re-reads, diffs empty, and is a clean no-op. The undo path inverts a recorded
operation through the `domain/graph_undo` inverse-action model with a drift check.

### `prener_agent.py` — spaCy PreNER baseline (built, **dormant** in the PoC) (§7 step 3)

[`prener_agent.py`](../../backend/src/story_forge/agents/prener_agent.py) (`PreNERAgent`) is the
deterministic spaCy NER baseline: it runs `pl_core_news_lg` / `en_core_web_lg` over a paragraph and
emits low-confidence `CandidateSpan`s mapped to the §3.2 taxonomy (`map_spacy_label`,
`candidates_from_entities` are pure and CI-tested without the ~950 MB models). **It is not wired
into the live ingest path** — the PoC's `/extract` is LLM-only (spec §7 Step 3); PreNER-hint
injection into the extraction prompt is a recorded deferral, not a shipped feature. It is documented
here as built-but-dormant, the deterministic-local exception that lets it import spaCy directly.

### Shared helpers — `validation.py`, `json_output.py`

[`validation.py`](../../backend/src/story_forge/agents/validation.py) (`validate_with_retry`) is the
shared call → parse → validate → retry loop, folded at the rule-of-three (Chunking + Extraction +
Judge). It retries *schema* failures and a failed optional post-parse `check` (a semantic invariant
the schema can't express — e.g. chunking's paragraph coverage), both surfacing as a `ValueError`;
transport failover and the pause-and-ask budget/quota signals propagate past it untouched. [`json_output.py`](../../backend/src/story_forge/agents/json_output.py)
(`extract_json`) strips a model's markdown code fence before Pydantic — the text-cleanup step
`validate_with_retry` calls, shared rather than copied per agent.

## How it connects

Agents sit between the API and the domain/adapter seams. They consume **`domain/` shapes and
Protocols** — pure value objects (`GraphEntity`, `Paragraph`, `StagedCandidate`, `Outline`) and the
business rules over them (`domain/candidates`, `domain/graph_undo`, `domain/entity_edits`) — and
never reach a concrete adapter directly: they type against Protocols (`LLMProvider`, `Router`, and
the store Protocols each module declares) that **`adapters/`** implements and `main.py` wires in via
dependency injection. The **`api/`** routes are thin HTTP wrappers that call these agents and map
their typed exceptions (`StaleMergeTarget` →409, `JudgeError`-fed fail-close, `ChunkingTooLongError`
→413, …) onto declared responses.

For the conventions that own the details, see
[`backend/src/story_forge/AGENTS.md`](../../backend/src/story_forge/AGENTS.md) (the agent pattern,
the shared-helper folds, the give-up-error-total rule, the local-NLP exception) and the spec's
[§6.5 / §3.3 / §7](../../story-forge-poc-spec.md). The neighbouring layers each have a reference
note: [`backend-domain.md`](./backend-domain.md) (the shapes consumed here),
[`backend-adapters.md`](./backend-adapters.md) (the Protocols implemented), and
[`backend-api.md`](./backend-api.md) (the routes that call these services).
