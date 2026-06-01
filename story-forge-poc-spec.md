# Story Forge — PoC Project Specification

**Version:** 0.2 (public-demo revision)
**Date:** May 19, 2026
**Project owner:** Marcin
**Document purpose:** Proof-of-Concept specification for an application that analyzes, annotates, and edits long-form narrative text while building an evolving knowledge graph. This PoC doubles as a public portfolio piece: a working demonstration of clean, modular architecture — agent-based LLM orchestration, multi-model routing across local and cloud providers, secure-by-default container infrastructure, and a strict spec → failing test → minimal implementation workflow.

---

## 1. Executive summary

Story Forge is a local web application that supports a solo author through three phases of working with narrative text:

1. **Ingest & knowledge graph** — upload a raw draft, hierarchically split it (chapters → scenes → paragraphs), extract entities and relations into a Neo4j graph with human-in-the-loop on every decision about new entities
2. **Editing & polishing** — paragraph-by-paragraph work with an LLM in inline/dialog/diff modes, with a full edit history that serves as a training dataset
3. **Style rewriting** — coherence-preserving rewriting in a defined target style (presets, transfer from example, project-level custom prompt)

The PoC starts with phase 1 (graph + viewer). Phases 2 and 3 are subsequent iterations on a solid foundation.

**Key technical traits (and showcase angles):**
- Web app: FastAPI (Python) + React, local backend — clean three-layer architecture (API / domain / adapters), each with its own CLAUDE.md and conventions
- Bilingual (PL/EN) — multilingual NLP and embeddings as first-class concerns
- **Agent-based ingest pipeline:** chunking, extraction, matching, and judgment are modular agents wired by an orchestrator, each with its own prompt template, output schema, preferred model tier, and tests
- **Multi-model routing:** one `LLMProvider` Protocol, multiple swappable adapters — local Ollama, Ollama Cloud free tier, and paid cloud providers (Anthropic, OpenAI, Grok, OpenRouter) — chosen per task by a small router
- Neo4j as single source of truth for the world; per-story graph + optional merge into a "world graph"
- Every edit recorded as a (before, after, intent, accepted) tuple — future training corpus
- **Security-by-default infra:** every container non-root, localhost-bound, on a private network; every dependency pinned and aged; no telemetry; CORS strict; secrets only in `.env`

---

## 2. Context and motivation

### 2.1 Use case

The author writes stories set in a coherent universe (potentially part of a larger world, e.g. "Wody Święte" / "Holy Waters" — a mythic reinterpretation of Polish fishing traditions). The problem to solve: a raw draft is chaos. After writing, the author wants to:

- see which entities (characters, places, objects, concepts) actually appeared in the text
- build a graph of their relations that becomes a living document of the world
- iterate editorially with an LLM as assistant (not replacement)
- ultimately rewrite fragments or the whole in a different stylistic register while preserving factual coherence (the graph as anchor)

### 2.2 Why this is also a portfolio piece

Story Forge is built in the open as a public PoC. Code, ADRs, plan files, and Claude Code conventions are all visible. That changes a few things:

- **Architecture choices are demonstrated, not just made.** ADRs are short and present; CLAUDE.md files document conventions per layer; the three-tier LLM strategy is visible in code, not buried in config.
- **Clean separation matters.** The domain layer is pure (no I/O); adapters are swappable behind protocols; agents are individually unit-testable with mocked providers.
- **Security is the default, not a follow-up.** Containers non-root, localhost-only, private network, no secret leaks, pinned and aged deps. CI enforces every rule.
- **The "vibe coding" workflow is the meta-demo.** Spec → failing test → minimal implementation → refactor, with two living plans (`PLAN_LONG.md`, `PLAN_SHORT.md`) and an opinionated Claude Code interaction style. Visitors should be able to read `CLAUDE.md` + `PLAN_SHORT.md` and immediately understand how the project is built.

### 2.3 What Story Forge is NOT

- **Not a content generator.** The LLM serves analysis and editorial support, not writing from scratch.
- **Not multi-user.** Solo tool, local.
- **Not a shippable product workflow.** The PoC must be useful for the author and clearly showcase architecture; it is not productionable as-is.

---

## 3. Functional requirements — PoC V1 (Ingest + Graph + Viewer)

### 3.1 Upload and text splitting

**Input:**
- Text files: `.txt`, `.md`, `.docx`
- Language: Polish or English (auto-detection via `langdetect` or fasttext, TBD)
- Typical size: 5,000–50,000 words per story

**Splitting workflow (hybrid — this is a key architectural decision):**

1. **Automatic mode:** an LLM (local preferred, to save tokens) analyzes structure and proposes a hierarchical split:
   ```
   Story
   ├── Chapter 1
   │   ├── Scene 1.1
   │   │   ├── Paragraph 1.1.1
   │   │   ├── Paragraph 1.1.2
   │   │   └── ...
   │   └── Scene 1.2
   └── Chapter 2
   ```
2. **Manual mode:** the user gets an editor with `## Chapter`, `### Scene` markers and paragraph separators. Can set the split themselves (saves tokens on predictable formats).
3. **Hybrid mode:** the user inserts anchors where they're certain of splits; the LLM fills in the rest.

**Output:** a document tree in the database (relational, not the graph — see §6) with addressable IDs for every node.

### 3.2 Entity and property extraction

**Philosophy: open-world ontology.** The entity schema is NOT defined upfront. After the first story we'll see what shows up, and the schema grows. Possible early categories (to be confirmed after the first pass):

| Entity type | Examples |
|-------------|----------|
| `Character` | characters, NPCs, mythic beings |
| `Location` | concrete and abstract places (e.g. "Janek's dream") |
| `Object` | story-significant items |
| `Organization` | clans, cults, institutions |
| `Concept` | motifs, worldbuilding concepts (e.g. "Blood of the River") |
| `Event` | events on the world's timeline |
| `Theme` | thematic threads (e.g. "initiation", "betrayal") |
| `SceneType` | scene types (e.g. action, dialogue, introspection, climax) |

Each entity has:
- `id` (UUID)
- `type` (from the taxonomy above, but extensible)
- `canonical_name` (PL and EN)
- `aliases` (list of variants)
- `properties` (free-form JSON — e.g. `{"age": 23, "role_in_cult": "priestess"}`)
- `first_seen` (reference to paragraph)
- `embedding` (vector for semantic match)

**Relations:**
- Typed (`MOTHER_OF`, `LIVES_IN`, `MEMBER_OF`, `APPEARS_IN`, `THINKS_ABOUT`, etc.)
- With attributes (when, where, intensity)
- Open-world: new relation types can be created during work

### 3.3 Cascade dedupe & matching (core mechanism)

When the LLM extracts an entity candidate (e.g. "Janek from the mill"), the system checks whether this entity already exists:

```
┌────────────────────────────────────────────────────────────────┐
│  STAGE 1: Fuzzy match (RapidFuzz)                              │
│  - Levenshtein/token-set ratio on canonical_name + aliases     │
│  - Threshold: similarity > 85% → merge candidate                │
│  - Threshold: 60-85% → go to Stage 2                            │
│  - Threshold: <60% → new entity (skip to Stage 4)               │
└────────────────────────────────────────────────────────────────┘
           ↓ (ambiguous)
┌────────────────────────────────────────────────────────────────┐
│  STAGE 2: Embedding similarity                                 │
│  - Multilingual embedding (e.g. paraphrase-multilingual-mpnet) │
│  - Compare with embedding of context (source sentence)          │
│  - Threshold: cosine > 0.85 → merge candidate                  │
│  - Otherwise → go to Stage 3                                    │
└────────────────────────────────────────────────────────────────┘
           ↓ (ambiguous)
┌────────────────────────────────────────────────────────────────┐
│  STAGE 3: LLM as judge                                         │
│  - Prompt: "Is [candidate in context] the same entity as       │
│    [existing entity + its properties + recent mentions]?"      │
│  - Strict JSON output: {match: bool, confidence: float,        │
│    reasoning: str}                                             │
│  - Confidence > 0.8 → merge candidate                           │
│  - Otherwise → flagged as "new or uncertain"                    │
└────────────────────────────────────────────────────────────────┘
           ↓ (always)
┌────────────────────────────────────────────────────────────────┐
│  STAGE 4: Human in the loop (CRITICAL)                         │
│  UI shows:                                                     │
│  - Quote from text (with ±200 chars of context)                │
│  - Proposal: "New entity of type X" OR "Merge with existing Y" │
│  - Reasoning from LLM (if it reached Stage 3)                  │
│  - Top-3 alternative existing entities to choose from           │
│  User can:                                                     │
│  - accept the proposal                                         │
│  - change merge target                                         │
│  - create a new entity with custom type                        │
│  - decide on relations (which entities it links to and how)     │
│  - reject (ignore this candidate)                               │
└────────────────────────────────────────────────────────────────┘
```

**Cost optimization:**
- Stage 1 is free (RapidFuzz locally)
- Stage 2 needs an embedding — local model, one-off compute cost
- Stage 3 is the only place we burn LLM tokens, and only on ambiguous cases
- Stage 4 is always human-side — no UI = no graph data

### 3.4 Graph visualization (Viewer)

Visualization requirements:
- **Main graph view** — force-directed, nodes colored by type, edges labeled with relation type
- **Filters:** entity type, story/chapter, connection density
- **Click on entity** → side panel with:
  - canonical_name, aliases, type
  - properties (editable)
  - all occurrences (links to paragraphs)
  - outgoing/incoming relations (editable)
  - timeline (where it appears in the story)
- **Drill-down to text:** click on an "occurrence" → opens the paragraph in the reader with highlight
- **"World" mode:** view aggregating multiple stories (if linked to a shared graph)

**Suggested libraries:** `cytoscape.js` or `vis-network` (simple, proven), or `react-force-graph` (aesthetics). Developer's call, but: must handle 500+ nodes smoothly.

### 3.5 Text reader with highlights

- Full story text in a single column
- Entities highlighted inline (color by type), tooltip shows canonical_name + brief description
- Click on a highlighted entity → opens side panel with a local graph around that entity
- Manual tagging available (select text → "this is an entity of type X" → add to graph)
- Manual correction: right-click on a highlight → "not this entity" / "not an entity" / "change boundaries"

### 3.6 Multi-story workflow

- **Per-story graph**, persisted separately (Neo4j labels or separate databases — see §6)
- **"World graph"** optional: the user can mark a story as belonging to world X → its entities become candidates for merging with world X's entities
- Merge between story and world uses the same cascade (§3.3), but with greater caution and always human review

---

## 4. Functional requirements — V2 (Editing)

*Details to be expanded after V1. Here — the skeleton to factor into architecture.*

### 4.1 Three editing modes

**A. Inline suggestions (Grammarly-style)**
- LLM walks through a paragraph, marks fragments with proposed changes
- Hover shows the suggested alternative + rationale
- Click = accept, alt-click = reject, edit = your own version
- Cheap (local LLM for typical fixes: punctuation, repetition, stiff phrasing)

**B. Dialog mode (chat about the paragraph)**
- Side panel: chat with LLM with context = current paragraph + relevant fragments from the graph (e.g. info about characters present)
- "Is this paragraph consistent with what we know about Janek?"
- "Propose 3 variants of the closing sentence"
- Expensive (bigger model, more context) — use deliberately

**C. Diff mode (proposed rewrite)**
- LLM rewrites the whole paragraph per stated intent
- UI shows side-by-side diff (original vs proposed)
- Granularity: accept/reject individual changes at sentence level
- Most expensive (full rewrite) — for whole paragraphs

### 4.2 Edit history as dataset (CRITICAL)

Every change in the text — regardless of mode — generates a tuple:

```json
{
  "edit_id": "uuid",
  "timestamp": "ISO8601",
  "scope": "paragraph|sentence|span",
  "scope_id": "ref to a node in the document tree",
  "before": "text before",
  "after": "text after",
  "intent": "free description or tag (e.g. 'sharpening', 'repetition', 'style-more-graphic')",
  "source": "llm|human|llm_then_edited",
  "model_used": "grok-4|llama3.1-70b|null",
  "prompt_used": "full prompt if LLM",
  "accepted": true,
  "context": {
    "entities_in_scope": ["entity_id_1", "..."],
    "story_id": "...",
    "chapter_id": "..."
  }
}
```

These land in a separate `edit_history` table and are exportable to a format (JSONL) ready for fine-tuning or DPO. This is the project's long-term asset — not just a log, but a building block for a personal model.

### 4.3 Editing UX

- Comfort > functionality. Keyboard > mouse (shortcuts for accept/reject/next).
- Modes switchable with a single shortcut.
- Undo/redo must work reliably (not LLM-magic, deterministic stack).
- Display session "token budget" (how much remains, cost in USD/PLN).

---

## 5. Functional requirements — V3 (Style rewriting)

*Sketch. To be expanded after V2.*

Three mechanisms for defining target style (can work together):

1. **Presets:** sliders like "more graphic", "clinical", "lyrical", "dialogue-heavy", "first-person POV". Underneath — pre-built prompts.
2. **Style transfer from example:** the user pastes a fragment by another author (or their own earlier text), the LLM extracts a "style feature vector" (sentence length, vocabulary, register, metaphor frequency) and reproduces it.
3. **Per-project system prompt:** each project can have its own "style anchor" — a style instruction the LLM honors across all operations in that project (e.g. style "Wody Święte": archaic register, long sentences, sacred water metaphors).

Critical constraint: the entity graph is the **factual anchor**. Rewriting MUST preserve consistency with the graph (no changing names, relations, places — unless explicitly allowed). This requires injecting graph context into the rewriting prompt.

---

## 6. Technical architecture

### 6.1 Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Backend | FastAPI (Python 3.12) | Python NLP ecosystem, async I/O, OpenAPI out of the box |
| Frontend | React + Vite + TypeScript | Familiar, mature, good libraries for graphs and editor |
| Frontend state | TanStack Query + Zustand | Server state cache + lightweight local state |
| Text editor | Tiptap (ProseMirror) | Structured, easy inline annotations, mature |
| Graph DB | Neo4j Community | Native graph, good visualization |
| Relational DB | PostgreSQL | Document tree, edit_history, project metadata |
| Vector store | pgvector (Postgres extension) | One less DB to maintain than a separate Chroma |
| Local LLM (small) | Ollama, Qwen3.5 9B Q4_K_M | Fits 8GB VRAM (~6.96 GB at 32K ctx), strong multilingual including Polish, ~55 t/s on RTX 3070-class hardware |
| LLM (medium, free) | Ollama Cloud (`gpt-oss:20b-cloud` for chunking, larger variants for heavier tasks) | Free tier with 5h session / 7-day weekly limits, identical API to local Ollama, no local GPU needed |
| Cloud LLM (strong, paid) | Provider-agnostic (see §6.5) | Anthropic / OpenAI / Grok via individual adapters; OpenRouter as meta-provider for model variety and cost arbitrage |
| Embeddings | sentence-transformers (local) | Multilingual PL/EN, no API costs |
| NER baseline | spaCy `pl_core_news_lg` + `en_core_web_lg` | Pre-LLM filter, token savings |

### 6.2 Deployment

**Docker Compose** for infrastructure:

```yaml
services:
  neo4j:        # 7474, 7687, persistent volume
  postgres:     # 5432, persistent volume, pgvector enabled
  ollama:       # 11434, optional GPU passthrough, persistent volume for models
```

**Bare metal** for development:
- `uv run` for backend (hot reload via uvicorn)
- `npm run dev` for frontend (Vite HMR)
- `.env` with secrets (API keys), never committed

Rationale for the mixed approach: backend and frontend iterate faster locally; infrastructure services are stable and better off in Docker.

### 6.3 Project structure (proposed)

```
story-forge/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── pyproject.toml
│   ├── src/story_forge/
│   │   ├── main.py                # FastAPI entry
│   │   ├── api/                   # FastAPI routers
│   │   │   ├── stories.py
│   │   │   ├── entities.py
│   │   │   ├── graph.py
│   │   │   ├── editing.py         # V2
│   │   │   └── llm.py
│   │   ├── domain/                # business logic (I/O-pure)
│   │   │   ├── chunking.py
│   │   │   ├── extraction.py
│   │   │   ├── matching.py        # cascade from §3.3
│   │   │   └── editing.py         # V2
│   │   ├── agents/                # agent modules (prompt + schema + orchestration)
│   │   │   ├── chunking_agent.py
│   │   │   ├── extraction_agent.py
│   │   │   ├── judge_agent.py
│   │   │   └── ...
│   │   ├── adapters/
│   │   │   ├── llm/               # provider abstraction
│   │   │   │   ├── base.py
│   │   │   │   ├── ollama.py
│   │   │   │   ├── anthropic.py
│   │   │   │   ├── openai.py
│   │   │   │   ├── grok.py
│   │   │   │   ├── openrouter.py
│   │   │   │   └── router.py      # tier routing + failover
│   │   │   ├── neo4j_repo.py
│   │   │   ├── postgres_repo.py
│   │   │   └── embeddings.py
│   │   ├── prompts/               # Jinja2 prompt templates, versioned
│   │   └── config.py
│   └── tests/
└── frontend/
    ├── package.json
    ├── src/
    │   ├── app/
    │   ├── features/
    │   │   ├── upload/
    │   │   ├── chunking/
    │   │   ├── extraction-review/  # UI for Stage 4 of cascade
    │   │   ├── graph-viewer/
    │   │   ├── text-reader/
    │   │   └── editor/             # V2
    │   ├── lib/api/                # generated from OpenAPI
    │   └── components/ui/          # shadcn/ui base
    └── ...
```

### 6.4 Data model

**Postgres (document structure + metadata):**

```sql
projects        (id, name, language, world_id, style_anchor, created_at)
stories         (id, project_id, title, raw_text, ingested_at)
chapters        (id, story_id, order_index, title, summary)
scenes          (id, chapter_id, order_index, title, summary)
paragraphs      (id, scene_id, order_index, content, content_normalized, embedding vector(768))
entity_mentions (id, paragraph_id, entity_id, span_start, span_end, confidence)
edit_history    (id, scope, scope_id, before, after, intent, source, model, prompt, accepted, context, timestamp)
worlds          (id, name, description)  -- optional shared graph parent
```

**Neo4j (knowledge graph):**

```cypher
// Nodes
(:Entity {id, type, canonical_name_pl, canonical_name_en, aliases, properties, embedding, project_id, world_id})

// Relations (dynamically typed)
(:Entity)-[:RELATION_TYPE {confidence, source_paragraph_id, attributes}]->(:Entity)

// Project/world markers
(:Project {id, name})
(:World {id, name})
(:Entity)-[:BELONGS_TO]->(:Project)
(:Project)-[:PART_OF]->(:World)
```

**Multi-tenancy strategy:** simple filter via `project_id` / `world_id` property on every node. Neo4j multi-database (separate DB per project) would be cleaner but requires Enterprise. Property-based is sufficient for PoC.

**Naming & ordering conventions:**

- **No SQL reserved words as column names.** Sibling ordering uses `order_index` (not `order`, which is reserved in Postgres and the SQL standard, forcing quoting everywhere). The same name is used end-to-end — DB column, Pydantic field, and JSON — so there is no DB↔API mapping layer to reason about.
- **Ordering is a plain integer ordinal**, renumbered across siblings of one parent on reorder/insert. At PoC scale (dozens of chapters/scenes, hundreds of paragraphs per story) this is cheap. A fractional/lexical rank (float or LexoRank) would avoid sibling renumbers but is speculative complexity we are not adding now; revisit via an ADR only if reordering becomes hot at scale.

### 6.5 LLM provider abstraction & agent orchestration (CRITICAL)

This section defines the most-demonstrated part of the architecture: how the system selects, calls, and falls back between LLMs, and how the ingest/editing logic is decomposed into agents.

**Hardware constraint:** development happens on a machine **without a discrete GPU** (or with 8GB VRAM at most). This is a non-negotiable input to the cascade design — we can't run a 70B local model. We can run a small local model (Qwen3.5 9B Q4_K_M class) for cheap tasks, and we need a remote tier for medium-weight tasks that doesn't burn paid tokens.

On a **fully GPU-less host** the local_small tier is impractical (CPU-only 9B inference is too slow for interactive use), so agents that prefer local_small default to **cloud_free** until a GPU-backed local tier is configured. Because Local Small and Cloud Free both speak the Ollama API, this is a host/config flip in `OllamaProvider`, not a code-path change.

**Three-tier model strategy:**

| Tier | Use case | Provider(s) |
|------|----------|-------------|
| **Local small** | Chunking, summarization, pre-NER assist, simple JSON extraction | Ollama running Qwen3.5 9B Q4_K_M (or fallback Qwen3 8B, Phi-4 Mini) on dev machine |
| **Cloud free / cheap** | Entity extraction batch passes, judge calls, draft suggestions | Ollama Cloud free tier (`gpt-oss:20b-cloud` for structural / JSON tasks like chunking, `gpt-oss:120b-cloud` or Qwen3.5 cloud variants for heavier passes) — identical Ollama API, no local GPU needed; bound by 5h session / 7-day weekly GPU-time quotas |
| **Cloud strong (paid)** | Heavy editing, full rewrites, style transfer, long-context work | Anthropic and OpenAI as primary; Grok (xAI) as alternative; OpenRouter as meta-provider for model variety and cost arbitrage |

The Local Small and Cloud Free tiers BOTH speak the Ollama API. That's a deliberate architecture choice: one adapter (`OllamaProvider`) handles both, the only difference is the host URL and an optional API key. This drastically reduces the number of code paths.

**Provider protocol:**

```python
class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[Message],
        model_tier: ModelTier,  # local_small | cloud_free | cloud_strong
        json_schema: dict | None = None,
    ) -> CompletionResult: ...

    @property
    def cost_per_1k_tokens(self) -> tuple[float, float]: ...  # input, output (0,0 for free tiers)
    @property
    def rate_limit_kind(self) -> Literal["none", "session_gpu_time", "per_minute_tokens"]: ...
```

Concrete adapters:
- `OllamaProvider(host="http://localhost:11434")` — local small tier
- `OllamaProvider(host="https://ollama.com", api_key=...)` — Ollama Cloud free tier
- `AnthropicProvider` — Claude models, paid
- `OpenAIProvider` — GPT models, paid
- `GrokProvider` — xAI API, paid alternative
- `OpenRouterProvider` — meta-provider, broad model selection at varied price points

**Router (cascade):**

```python
class LLMRouter:
    def route(self, task: Task) -> LLMProvider:
        # Decision order:
        # 1. If task is light (chunking, summary, simple structured extraction) → local_small
        # 2. If task is medium (entity extraction, judge calls) → cloud_free (Ollama Cloud)
        # 3. If task is heavy (editing, rewrite, long context) → cloud_strong (preferred provider)
        # 4. If preferred provider in tier errors/rate-limits → automatic failover to next configured
        # 5. If cloud_free quota exhausted → degrade to local_small with warning OR pause for user
        ...
```

The user must have UI control: a dropdown "which provider/model for this task" + global preferences per task type. The router shows the user which tier was selected and why; quota status (Ollama Cloud time remaining, paid spend so far) is visible at all times.

**Failover (within a tier):** every call has a retry policy for network errors, schema-parse failures, and rate limits. If a provider rate-limits or errors, the router transparently retries against the next configured provider for the same tier, with the swap logged.

**Agent orchestration:**

The ingest pipeline is structured as a small set of **agents** — thin, testable modules that each own one logical task. An agent encapsulates:

- a Jinja2 prompt template (PL + EN variants) in `prompts/`
- a Pydantic output schema (LLM output is parsed, validated, retried on failure)
- a preferred `ModelTier`
- pure orchestration logic that calls the router and the validation helpers

The agent catalog for V1:

| Agent | Input | Output | Preferred tier |
|-------|-------|--------|----------------|
| `ChunkingAgent` | raw story text | hierarchical outline (chapters/scenes/paragraph ranges) | local_small (cloud_free when no local GPU) |
| `PreNERAgent` | paragraph text | candidate spans (no LLM; spaCy) | n/a |
| `ExtractionAgent` | paragraph + known entities + custom types | candidate entities + relations | cloud_free |
| `MatchingAgent` | candidate + graph | Stage 1+2 decision (fuzzy + embedding; no LLM) | n/a |
| `JudgeAgent` | candidate + best existing match | identity verdict + confidence + reasoning | cloud_free |
| `ReviewQueueService` | matching results | items surfaced to the human (no LLM) | n/a |

Editing and rewriting modes (V2/V3) become additional agents (`InlineEditAgent`, `DiffRewriteAgent`, `StyleTransferAgent`) that share the same router.

**Why "agents" and not "functions":**
- Each agent owns its prompt and schema as first-class artifacts (versioned in git, lintable, testable)
- Each is unit-testable in isolation with a mocked `LLMProvider`
- New agents are added by following the pattern, not by editing a god-class
- The structure makes it visible — to a portfolio visitor reading the code — exactly which models do what, and how to swap them

### 6.6 Token budget & cost

- Every LLM operation records: model, input_tokens, output_tokens, cost_estimate
- Dashboard shows: daily/project/per-task-type usage
- Emergency cap: "stop after exceeding X USD per day"
- Ollama Cloud usage tracked as GPU-seconds, not tokens (per their billing model); router shows remaining session quota

### 6.7 Security baseline (day 1)

These are non-negotiables that must be in place from the first commit, not bolted on later:

- **Dependencies pinned and minimum 14 days old.** Every package in `pyproject.toml` / `package.json` pinned to an exact version. No version is selected that was released less than 14 days ago — gives time for malicious-package alerts to surface. CI check enforces this. _(Direct-URL wheel channel, added 2026-05-29 / M2.S1: a few dependencies are not published on PyPI/npm — notably spaCy's pretrained pipeline packages `pl_core_news_lg` and `en_core_web_lg`, distributed only as versioned wheels on GitHub Releases. These are pinned as PEP 508 direct-URL references — `name @ https://github.com/<org>/<repo>/releases/download/<tag>/<name>-<version>-…whl` — which are **exact by construction** (a release-asset URL is immutable and carries the version) and **hash-locked** in `uv.lock` (uv records and verifies a SHA-256 for URL wheels). The 14-day soak still applies, enforced against the **matching release asset's upload timestamp** (its `updated_at`) instead of a PyPI upload date: `check_dependency_age.py` resolves the release through the GitHub API, finds the asset whose filename matches the locked wheel, and applies the same cutoff. Asset timestamp, *not* the tag's publish date — a wheel can be added to or replaced on an older release after the tag was cut, and since uv hash-locks whatever bytes we pin, the tag date would let a freshly-uploaded artifact slip past the soak. The OSV/advisory gate is the one rule that does **not** apply — these artifacts are not indexed by OSV/pip-audit — so the residual supply-chain risk is bounded instead by: (a) the official publisher (Explosion's `spacy-models` org), (b) the locked SHA-256 guaranteeing artifact integrity on every install, and (c) the wheel carrying only the standard spaCy pipeline (model weights + config), not novel network/exec code. This adapts — does not relax — the exact-pin and 14-day rules; see `scripts/check_dependency_age.py` GitHub-release handling and the `/add-dependency` skill.)_
- **Container images pinned, aged, and CVE-scanned.** Every image in `docker-compose.yml` is pinned to an exact tag (no `latest`, no floating majors), the tag is **at least 7 days old** at time of pin, and the image is verified CVE-clean against an OSS scanner (Trivy) before being committed. A CI job re-runs the scan on every push so regressions are caught. _(The image soak is 7 days, shorter than the 14-day package rule, because base images come from known, signed official publishers — the dominant image risk is known CVEs, not a hijacked release, and for CVEs freshness *reduces* exposure (a newer rebuild ships patched OS packages). Trivy CVE-cleanliness is therefore the primary gate; a 7-day soak still leaves room for a compromised-tag alert to surface. Bundled-dependency CVEs that no tag/base variant can fix are waived with per-CVE justification in a scoped `.trivyignore`, dropped when upstream rebuilds.)_
- **Secrets only in `.env`, never committed.** `.env.example` lists required keys with dummy values. `.gitignore` covers `.env`, `.env.local`, `*.env`. Pre-commit hook scans for leaked secrets (`detect-secrets`).
- **Docker services bind to localhost only.** Neo4j, Postgres, Ollama in compose use `127.0.0.1:` prefix on port mappings. No service is reachable from LAN, let alone the internet.
- **No root in containers.** Every service in `docker-compose.yml` runs as a non-root user (`user:` directive with explicit UID/GID, or a thin wrapper image that drops privileges). Images verified to have non-root default users, or overridden.
- **Network isolation.** Compose defines a private bridge network. Only the FastAPI backend (when later containerized) is on the same network as data services. No `network_mode: host`.
- **No exposed admin UIs.** Neo4j Browser (port 7474) is bound to localhost only; for any remote access, use SSH tunnel. Same for any future admin endpoints.
- **Database credentials are random per-environment.** No `postgres/postgres` defaults. Generated on first setup if not set in `.env`.
- **API keys never logged.** Logging middleware strips `Authorization`, `X-API-Key`, and similar headers/fields before emitting any log line.
- **CORS strict by default.** Backend allows only the four loopback origins for the dev frontends: `http://localhost:5173` + `http://127.0.0.1:5173` (Vite dev) and `http://localhost:3000` + `http://127.0.0.1:3000`. No wildcard origins, even in dev. *Why both forms:* the browser-visible Origin header is whatever the URL bar said, not whatever DNS resolved to — and Vite binds the dev server to `127.0.0.1` by default, so contributors who type either form must work without a "your origin is wrong" footgun. Both names point at the same loopback socket; the trust boundary is identical. Amended 2026-05-26 (Session 6 retro) after the original `localhost`-only list silently broke uploads from `127.0.0.1:5173` in the real-browser smoke test.
- **Frontend dependencies audited.** `npm audit` runs in CI; high/critical issues fail the build.
- **No telemetry, no analytics.** No `posthog`, `mixpanel`, `sentry`, or similar phoning home. Tool is solo-use; no need to track anything externally.
- **File uploads sandboxed.** Uploaded documents stored in a dedicated directory outside of webroot; size and MIME type validated; no execution permissions.

---

## 7. Ingest pipeline — step by step

This is the most important flow in V1. I'm spelling it out in detail so the developer knows what to implement and in what order. Each step maps to one or more agents from §6.5.

```
┌──────────────────────────────────────────────────────────────────┐
│ Step 1: Upload                                                   │
│ - Validate format (txt/md/docx), size                            │
│ - Detect language                                                │
│ - Save raw to storage, create Story record in Postgres           │
│ - Response echoes parsed raw_text so the frontend manual editor   │
│   opens pre-seeded (no follow-up GET /stories/{id} needed; the    │
│   browser cannot reliably parse .docx itself). [§7.1 amended      │
│   2026-05-26 — Session 6]                                         │
└──────────────────────────────────────────────────────────────────┘
          ↓
┌──────────────────────────────────────────────────────────────────┐
│ Step 2: Structure (auto/manual/hybrid — user choice)             │
│ - If auto: ChunkingAgent (local_small, or cloud_free on a         │
│   GPU-less host) proposes hierarchy                               │
│ - UI shows proposed outline, user accepts/edits                  │
│ - For manual/hybrid: the frontend POSTs the edited source in a    │
│   raw_text body override; the route uses it AND updates           │
│   stories.raw_text in the same transaction so the edit survives   │
│   a later re-read. [§7.2 amended 2026-05-26 — Session 6]          │
│ - Save chapters/scenes/paragraphs to Postgres                    │
└──────────────────────────────────────────────────────────────────┘
          ↓
┌──────────────────────────────────────────────────────────────────┐
│ Step 3: Pre-NER baseline (per paragraph)                         │
│ - PreNERAgent (spaCy) extracts simple entities                    │
│ - These are low-confidence entity candidates                     │
│ - Cheap operation, done for whole text offline                   │
└──────────────────────────────────────────────────────────────────┘
          ↓
┌──────────────────────────────────────────────────────────────────┐
│ Step 4: LLM extraction (per paragraph or per scene — config)     │
│ - ExtractionAgent (cloud_free by default; cloud_strong on hard    │
│   cases) with prompt: "Extract entities and relations. Here are   │
│   known entities: {existing}. Format JSON: {entities, relations}" │
│ - Structured output validated by Pydantic schema                  │
└──────────────────────────────────────────────────────────────────┘
          ↓
┌──────────────────────────────────────────────────────────────────┐
│ Step 5: Embedding of candidates                                  │
│ - Every new candidate gets a context embedding                   │
│ - Embeddings stored in pgvector for existing entities            │
└──────────────────────────────────────────────────────────────────┘
          ↓
┌──────────────────────────────────────────────────────────────────┐
│ Step 6: Cascade matching (§3.3)                                  │
│ - MatchingAgent runs Stage 1+2; JudgeAgent (cloud_free) runs      │
│   Stage 3 only when ambiguous                                     │
│ - Results queued for human review                                 │
└──────────────────────────────────────────────────────────────────┘
          ↓
┌──────────────────────────────────────────────────────────────────┐
│ Step 7: Human review (Stage 4)                                   │
│ - UI: review queue per scene or per chapter                      │
│ - User accepts/modifies/rejects each decision                    │
│ - Final entities saved to Neo4j with relations                   │
│ - entity_mentions saved to Postgres                              │
└──────────────────────────────────────────────────────────────────┘
          ↓
┌──────────────────────────────────────────────────────────────────┐
│ Step 8: Graph viewer available                                   │
│ - User explores graph, corrects, adds manually                   │
│ - Loop: can return to Step 4 for the next chapter                │
└──────────────────────────────────────────────────────────────────┘
```

**Optimizations:**
- Step 4 can be batched (several paragraphs in one LLM call for context) — trade-off cost vs quality
- Step 4 can be "cheaper" if pre-NER (Step 3) already produced good candidates (LLM only classifies types and detects relations)
- User can pause the pipeline after any step and resume

---

## 8. UI/UX — sketch of key screens

### 8.1 Project list (home)
- Project cards: title, language, story count, entity count, recent progress
- "New project" → choose "standalone" vs "part of world X"

### 8.2 Story view (main V1 screen)
```
┌─────────────────────────────────────────────────────────────────┐
│ [Nav] Project > Story X                       [Token budget]   │
├──────────────┬──────────────────────────────┬───────────────────┤
│              │                              │                   │
│   Outline    │     Text with highlights     │   Side panel      │
│              │                              │                   │
│  Ch. 1       │   Janek entered the mill...  │   [Selected ent.] │
│   Scene 1.1  │   ↑ highlighted              │   Janek           │
│   Scene 1.2  │                              │   - type: Char.   │
│  Ch. 2       │   ...                        │   - aliases: [...]│
│              │                              │   - properties    │
│  [Review     │                              │   [Mini-graph     │
│   queue: 12] │                              │    around entity] │
│              │                              │                   │
└──────────────┴──────────────────────────────┴───────────────────┘
```

### 8.3 "Review queue" screen (key for cascade)
- List of candidates for decision, sorted by certainty (ambiguous first)
- Each item: quote with context, proposal, alternatives, action buttons
- Keyboard: J/K navigation, A = accept proposal, N = new entity, M = merge with..., R = reject
- Bulk actions (select multiple "these are all the same, merge all")

### 8.4 Graph view (fullscreen)
- Force-directed, colored by type
- Sidebar: filters, search by canonical_name
- Click on node = highlight + details panel
- Toggle: "this story only" / "whole world"

### 8.5 Agent activity panel (portfolio-visible)
- Small persistent panel: which agent ran most recently, which model/tier was chosen, latency, cost, quota state
- Makes the multi-model + agent architecture legible to anyone browsing the UI

---

## 9. Roadmap and milestones

### Milestone 0 — Setup (2-3 dev days)
- Docker Compose runs (Neo4j, Postgres, Ollama) — bound to localhost only, non-root containers, private network
- FastAPI + React builds, ping-pong endpoint
- Postgres migrations (Alembic harness, no migrations yet); Neo4j init script applied automatically by a one-shot `neo4j-init` compose service that runs `cypher-shell -f init.cypher` once `neo4j`'s healthcheck passes
- CI: lint, format, basic tests, dependency age check (≥14 days), `npm audit`, secret scan, container-image CVE scan (Trivy) against the images in `docker-compose.yml`
- `.env.example` with all required keys (Anthropic, OpenAI, Grok, Ollama Cloud, OpenRouter), pre-commit hooks installed
- Ollama Cloud connectivity test: hit `https://ollama.com/api/chat` with API key, verify free-tier quota status
- Project plan files initialized: `PLAN_LONG.md` (V1/V2/V3 roadmap) and `PLAN_SHORT.md` (current milestone breakdown)

### Milestone 1 — Upload & structure (3-5 days)
- Upload endpoint
- Language detection, docx/md/txt parsing
- ChunkingAgent: auto-chunking with local Ollama (Qwen3.5 9B Q4_K_M) for cheap cases, Ollama Cloud (`gpt-oss:20b-cloud` or similar level-1 model) for longer texts
- Manual chunking UI (markdown editor with preview)
- Outline view, save to Postgres

**Outcome:** ability to upload text and see its structure.

### Milestone 2 — Basic extraction (5-7 days)
- LLM provider abstraction with three tiers (local_small via Ollama, cloud_free via Ollama Cloud, cloud_strong via Anthropic/OpenAI/Grok)
- OpenRouter adapter scaffolded as a meta-provider for additional model variety
- ExtractionAgent: prompt engineering, JSON schema, Pydantic validation with retry
- PreNERAgent: spaCy baseline
- Save entities to Neo4j without cascade (everything = new entity for now)
- Basic graph viewer (cytoscape)
- Token/GPU-time budget tracking visible in UI
- Agent activity panel visible

**Outcome:** I see the entity graph extracted from text, but with many duplicates.

### Milestone 3 — Cascade matching (5-7 days)
- MatchingAgent: fuzzy match (RapidFuzz), embeddings (sentence-transformers, pgvector)
- JudgeAgent: LLM as judge with strict schema
- Review queue UI with keyboard nav

**Outcome:** dedupe works, I control every decision, the graph is clean.

### Milestone 4 — V1 polish (5-7 days)
- Text reader with inline highlights
- Side panel with entity details
- Manual annotation (select text → entity)
- Edit properties and relations in UI
- Multi-story in one project
- Optional world graph parent

**Outcome:** V1 PoC complete. I can actually use it for worldbuilding, and a visitor can read the code + UI and understand the agent/multi-model architecture.

### Milestone 5+ — V2 Editing, V3 Rewriting
Plan outlined in §4 and §5. Concrete timelines after V1.

**Total V1 time: ~3-4 weeks of solo full-time dev work, or ~6-8 weeks at 50% load.**

---

## 10. Open questions and decisions to refine

These need a conversation with the developer at the start, or a conscious "decide as we go":

1. **LLM extraction granularity:** per-paragraph, per-scene, or per-chapter? Trade-off: accuracy (smaller = better) vs token cost (larger = better).
2. **Graph versioning strategies:** do we want rollback at the graph level, snapshots per story, or just an append-only log of changes?
3. **Conflict in shared world graph:** how to resolve when two stories give the same entity contradictory properties? Dialog UI, or soft "both versions coexist"?
4. **Export:** which format for the final "world bible"? Markdown, JSON, Obsidian-native format?
5. **Agent framework:** roll our own minimal Protocol+Router pattern, or adopt a small framework (Pydantic AI, LangGraph, smolagents, OpenAI Agents SDK)? Trade-off: minimal surface vs. familiar abstractions and built-in tracing.
6. **Backup strategy:** Neo4j and Postgres backups to filesystem, to Obsidian project, to separate git repo?
7. **Edit_history export:** target format? JSONL ready for SFT? DPO format (chosen/rejected)? Custom?
8. **Multilingualism within an entity:** are `canonical_name_pl` and `canonical_name_en` peers, or is one "main"? What happens when a character appears in both languages?
9. **Keyboard shortcuts:** vim-style or normal (J/K/A/N) — preference?
10. **Should V1 already have a "world summary" export (markdown from graph) to Obsidian?** That would close the loop "from draft to world bible".

---

## 11. Non-functional requirements and principles

- **Privacy:** everything local except calls to the cloud LLM. API keys never in code, only in `.env`. Text is not sent anywhere except the selected LLM provider — this must be explicit in UI ("sending fragment to Anthropic, OK?").
- **Reversibility:** every automatic decision must be manually undoable. Never "trust the LLM and forget".
- **Performance:** UI does not block on LLM operations. Everything async, progress visible, interruptible.
- **Determinism where possible:** the same LLM calls with `temperature=0` and a seed produce (roughly) the same result — important for edit_history as a dataset.
- **Observability:** every LLM call logged (prompt, response, tokens, cost, latency) — also training material.
- **Codebase quality:** clear separation of domain from adapters, unit tests on cascade matching (deterministic for Stage 1-2, mock for Stage 3), e2e for main flows. Each agent has its own test file with a mocked `LLMProvider`.
- **No premature scaling:** don't build for 1000 users. Solo, local, you can cut corners that would be critical in production.
- **Spec- and test-driven development.** Order of work per feature is strict: (1) update this spec or write a new design note → (2) write the failing tests that encode the spec → (3) implement until tests pass → (4) refactor. No production code is written before tests for it exist. The spec is the source of truth; if implementation reveals the spec is wrong, the spec is amended first and the affected downstream plan items are re-evaluated.
- **Two-horizon planning.** The project maintains two living plan documents at the root: `PLAN_LONG.md` (strategic, V1/V2/V3 milestones, kept stable) and `PLAN_SHORT.md` (tactical, current milestone broken into tasks, updated every working session). When implementation forces a spec change, both plans are reviewed: short-term reshuffled, long-term checked for cascading impact, both updated explicitly before continuing.
- **Public-portfolio hygiene.** The repo is public from day one. README, ADRs, plans, CLAUDE.md files, and inline comments are written assuming a stranger is reading them. No "TODO: explain later", no secrets-by-accident, no half-merged experiments on `main`.

---

## 12. What we bring from previous projects

- **Multi-layer PL/EN NLP pipeline patterns** from prior work — docker compose patterns, prompt engineering for structured extraction
- **Neo4j patterns** from prior graph work — schema design, synthetic data generation (useful for cascade tests)
- **Worldbuilding mental model** from work on "Wody Święte" — factions, sacred geography — serves as a test case for extraction
- **Lean docs + on-demand reference philosophy** from prior `CLAUDE.md` experiments — may have an analogue in "lean main prompt + on-demand entity context from graph"

---

## Appendix A: Glossary

- **Entity** — any identifiable being in the text (character, place, object, concept, motif, event)
- **Agent** — a thin module that owns one logical task (chunking, extraction, judging, ...), with its own prompt template, output schema, and preferred model tier
- **Cascade matching** — multi-stage decision process whether a candidate is a new entity or an existing one (§3.3)
- **Edit history** — append-only log of all text changes, serving as a dataset
- **World graph** — optional shared parent graph for multiple stories in the same universe
- **Style anchor** — project-level stylistic instruction injected into rewriting prompts
- **Review queue** — queue of decisions for a human, generated by the cascade
- **Tier** — one of `local_small`, `cloud_free`, `cloud_strong`; agents declare a preferred tier and the router picks a concrete provider

---

## Appendix B: Test case "Wody Święte" (Holy Waters)

This appendix gives the developer a concrete example of what the world should look like after ingesting one story. It serves as:
- **Sanity check** during implementation — does our pipeline extract these things?
- **Test fixture** for e2e extraction tests
- **Taxonomy reference** — shows that default NER categories (PER/LOC/ORG) are insufficient

### B.1 Worldbuilding context

"Wody Święte" ("Holy Waters") is an alternative mythology in which Polish fishing associations (PZW) are reinterpreted as ancient, partially-forgotten religions. Each fishing ground has a guardian spirit, every fishing technique has a ritual core, and the hierarchy in clubs is a hidden priestly hierarchy.

### B.2 Sample text fragment (PL)

> Stary Bronek siedział nad Czarną Hańczą od świtu. Wiedział, że Pani Wód nie lubi pośpiechu — kij musi leżeć cierpliwie, jak ofiarny nóż na ołtarzu. Pamiętał słowa stryja Kazimierza, który nauczył go pierwszej Modlitwy Zarzutu: "Nie biorę ryby. Ryba daje mi się sama, jeśli jestem godzien". Trzy karpie tego ranka — to znak. Loża z Augustowa dawno czekała na taki dowód.

(English gloss: Old Bronek had been sitting by the Czarna Hańcza river since dawn. He knew the Lady of the Waters dislikes haste — the rod must lie patiently, like a sacrificial knife on an altar. He remembered the words of uncle Kazimierz, who taught him the first Casting Prayer: "I do not take the fish. The fish gives itself to me if I am worthy." Three carp this morning — a sign. The Lodge of Augustów had long waited for such proof.)

### B.3 What should be extracted

**Entities:**

| Candidate | Type | Aliases | Properties | Confidence |
|-----------|------|---------|------------|-----------|
| Stary Bronek | Character | Bronek | approx_age: elderly, role: initiate | high |
| Czarna Hańcza | Location | — | type: river, region: Augustów | high |
| Pani Wód | Character/Deity | Lady of the Waters | type: deity/spirit, attribute: patience | high |
| stryj Kazimierz | Character | Kazimierz | role: Bronek's mentor, status: likely deceased | medium |
| Modlitwa Zarzutu | Concept/Ritual | Casting Prayer | type: ritual, function: opening a fishing session | high |
| Loża z Augustowa | Organization | The Lodge, Lodge of Augustów | type: hidden priestly hierarchy, location: Augustów | high |
| three carp | Object/Symbol | — | meaning: sign, context: offering/proof | low — may not be worth it |

**Relations:**

```
(Stary Bronek)-[:WORSHIPS]->(Pani Wód)
(Stary Bronek)-[:MENTORED_BY]->(stryj Kazimierz)
(Stary Bronek)-[:MEMBER_OF]->(Loża z Augustowa)
(Stary Bronek)-[:FISHES_AT]->(Czarna Hańcza)
(stryj Kazimierz)-[:TAUGHT {what: "Modlitwa Zarzutu"}]->(Stary Bronek)
(Pani Wód)-[:PATRON_OF]->(Czarna Hańcza)
(Modlitwa Zarzutu)-[:DEDICATED_TO]->(Pani Wód)
(Loża z Augustowa)-[:LOCATED_IN]->(Augustów)
```

**What standard NER will NOT extract (but we must):**

- **"Pani Wód"** — not a classic persona; spaCy may tag this as PER or miss it entirely. Our pipeline must extract mythic/spiritual beings as `Character` with subtype `Deity` or a separate `Spirit` type.
- **"Modlitwa Zarzutu"** — a ritual concept, not in the NER taxonomy. This is `Concept` or a new `Ritual` type.
- **"Loża z Augustowa"** — spaCy may tag as ORG, but it's actually a hidden hierarchy, not a regular organization. Properties must capture this.
- **The `WORSHIPS` relation** — no out-of-the-box system will extract this; it requires an LLM with worldbuilding context.

### B.4 What changes after the second story (incrementality test)

Assume the second story also mentions:
- "Bronisław" (same Bronek? — Stage 1 fuzzy: medium, Stage 2 context embedding: high → merge candidate, but human review)
- "Pani Czarnej Wody" ("Lady of the Black Water" — variant of Pani Wód? — fuzzy: medium, LLM judge should say yes based on context)
- A new character "Lucyna, the priestess from beneath the weir" → new entity, candidate for relation with the Lodge

This is exactly the flow that must work in the cascade. The test case is a fixture for e2e tests: two fixture texts + expected graph state after both.

### B.5 Recommended custom entity types for "Wody Święte"

Extension of the default taxonomy (§3.2):

| Type | Description |
|------|-------------|
| `Deity` | Deity, guardian spirit |
| `Ritual` | Cultic practice, prayer, ceremony |
| `SacredSite` | Fishing ground with ritual status (subtype of Location) |
| `Cult` | Lodge, brotherhood (subtype of Organization) |
| `Initiate` | Initiated person (subtype of Character — flag, not separate type) |
| `SacredObject` | Cultic attribute (rod, net, knife) |

---

## Appendix C: Prompt template skeletons

**Note:** these are placeholders for iteration. The developer should test them, measure (output quality, cost, latency), and refine. Each prompt has a PL and EN variant — language detection decides which is used.

### C.1 Auto-chunking (document structure)

**Goal:** split raw text into chapters → scenes → paragraphs.

```
[SYSTEM]
You are an assistant for analyzing the structure of narrative text. Your
task is to identify the hierarchical structure of a document: chapters,
scenes, paragraphs. You do not modify content, only mark divisions.

[USER]
Here is the raw text of a story. Split it hierarchically:
- Chapters (larger story units, often with shift of time/place)
- Scenes (narrative units within a chapter — one place, one time, one interaction)
- Paragraphs (already exist in text as blocks separated by blank lines)

Return the result as JSON matching the schema:
{
  "chapters": [
    {
      "title": "<string or null>",
      "summary": "<one sentence>",
      "scenes": [
        {
          "title": "<string or null>",
          "summary": "<one sentence>",
          "paragraph_range": [start_index, end_index]
        }
      ]
    }
  ]
}

Paragraphs are numbered from 0 in their order of occurrence. Skip no paragraph.

TEXT:
{raw_text}
```

### C.2 Entity & relation extraction

**Goal:** extract entities and relations from a text fragment, aware of the existing graph.

```
[SYSTEM]
You are an assistant for knowledge extraction from narrative text. You
extract entities (worldbuilding-relevant beings) and relations between
them. The world may be fictional or mythic — remain an accurate extractor
regardless of register.

Entities are NOT ONLY persons/places/organizations. Also:
- mythic beings, deities, spirits
- concepts, rituals, motifs
- story-significant objects
- events on the world's timeline
- scene types and dynamics (when explicitly named)

[USER]
Extract entities and relations from the fragment below.

KNOWN ENTITIES IN THIS PROJECT (to avoid duplicates):
{existing_entities_json}  // list: [{id, type, canonical_name, aliases, brief_desc}]

CUSTOM ENTITY TYPES FOR THIS PROJECT:
{custom_entity_types}  // e.g. ["Deity", "Ritual", "Cult"] for Wody Święte

FRAGMENT:
{paragraph_text}

CONTEXT (neighboring paragraphs, for disambiguation):
{neighbor_paragraphs}

Return JSON:
{
  "entities": [
    {
      "candidate_name": "<as named in the text>",
      "type": "<one of allowed types or 'OTHER:name'>",
      "match_hint": "<existing entity id if probable match, else null>",
      "match_confidence": <0.0-1.0>,
      "properties": {<any properties found in text>},
      "evidence_quote": "<literal quote from text, max 100 chars>"
    }
  ],
  "relations": [
    {
      "subject": "<candidate_name or existing entity id>",
      "predicate": "<e.g. WORSHIPS, LIVES_IN, MEMBER_OF>",
      "object": "<candidate_name or existing entity id>",
      "evidence_quote": "<quote>",
      "confidence": <0.0-1.0>
    }
  ]
}

Be conservative — if something is uncertain, set low confidence;
do not invent relations not in the text.
```

### C.3 LLM as judge (Stage 3 of cascade)

**Goal:** decide whether a candidate is the same entity as an existing one.

```
[SYSTEM]
You are an assistant for entity identity adjudication. You receive a
candidate from a new text fragment and an existing entity in the
graph. You decide whether they are the same entity or different.

Criteria:
- same canonical name or a natural inflection of it (Janek = Jan = Janek Kowalski)
- consistent context (same role, location, relations)
- no contradiction in properties

If the candidate is an obvious name variant + consistent context → match.
If the name matches but context is contradictory → different entities (homonyms).
If uncertain → low confidence, let the human decide.

[USER]
CANDIDATE:
- name in text: {candidate_name}
- context (quote): {candidate_context}
- proposed type: {candidate_type}
- detected properties: {candidate_properties}

EXISTING ENTITY (match candidate):
- id: {existing_id}
- canonical_name: {existing_name}
- aliases: {existing_aliases}
- type: {existing_type}
- properties: {existing_properties}
- last 3 mentions in texts: {existing_mention_excerpts}

Return JSON:
{
  "match": <true|false>,
  "confidence": <0.0-1.0>,
  "reasoning": "<one or two sentences>"
}
```

### C.4 Editing — inline suggestions (V2)

**Goal:** propose minor fixes in a paragraph (Mode A from §4.1).

```
[SYSTEM]
You are a stylistic editor. You do NOT rewrite — you point out spots to
improve. You focus on:
- word/phrase repetitions
- stiff phrasings
- illogical transitions
- punctuation
- overuse (adverbs, modals)

You do NOT change meaning. You do NOT propose tonal alternatives
(that's another mode). Your role = point-by-point editor.

[USER]
Paragraph to review:
"{paragraph}"

Worldbuilding context (entities present in this paragraph):
{entity_summaries}

Project style (if defined):
{style_anchor or "default"}

Return JSON with a list of suggestions:
{
  "suggestions": [
    {
      "span_start": <char index>,
      "span_end": <char index>,
      "original": "<original fragment>",
      "suggested": "<proposal>",
      "category": "<repetition|stiffness|punctuation|...>",
      "rationale": "<short rationale>"
    }
  ]
}

Maximum 8 suggestions. Fewer but well-aimed is better.
```

### C.5 Editing — diff mode (V2)

**Goal:** rewrite a paragraph per the user's intent.

```
[SYSTEM]
You rewrite a paragraph per the author's intent, PRESERVING:
- all facts (characters, places, events)
- consistency with the world graph
- POV and tense of the original (unless intent says otherwise)
- length ±30% (unless intent says "shorter"/"longer")

[USER]
ORIGINAL PARAGRAPH:
"{paragraph}"

AUTHOR'S INTENT:
"{user_intent}"  // e.g. "more sensual", "halve the length", "more dialogue"

ENTITIES AND FACTS THAT MUST REMAIN:
{entity_facts_json}

PROJECT STYLE:
{style_anchor}

Return JSON:
{
  "rewritten": "<new version of the paragraph>",
  "preserved_facts": [<list of preserved entities/facts>],
  "changes_summary": "<one sentence on what changed>"
}
```

### C.6 Style transfer (V3)

**Goal:** rewrite text in the style derived from an example.

```
[SYSTEM]
You rewrite text preserving the content but changing the style to match
the provided example. You first analyze the example's style features
(sentence length, vocabulary, register, metaphor frequency, pace, POV),
then apply them to the original.

[USER]
STYLE EXAMPLE (to emulate):
"""
{style_example}
"""

ORIGINAL TEXT (to rewrite in that style):
"""
{original_text}
"""

ENTITIES AND FACTS TO PRESERVE:
{entity_facts_json}

Return JSON:
{
  "style_analysis": {
    "sentence_length": "<short|medium|long|mixed>",
    "register": "<formal|colloquial|archaic|...>",
    "vocabulary_features": ["<feature>", ...],
    "rhythm": "<description>",
    "notable_devices": ["<metaphor|alliteration|...>", ...]
  },
  "rewritten": "<text in new style>"
}
```

### C.7 Developer notes on prompts

- **Language:** every prompt must be in the language of the input text. PL prompt → PL output. Auto-detection via `langdetect` or flags in request.
- **Schema validation:** JSON outputs must pass validation (Pydantic). Retry with corrected instruction on parse failure.
- **Temperature:**
  - Extraction, matching judge: `temperature=0.0` (deterministic)
  - Editing suggestions: `temperature=0.3`
  - Rewriting, style transfer: `temperature=0.7-0.9` (creative)
- **Token budget:** every prompt must have estimated cost and be tested on a typical paragraph (300-600 words). Emergency cap per request.
- **Failover:** every call has a retry policy for network errors, rate limits, and schema-parse failures. The router transparently swaps providers within a tier and logs the swap.
- **Prompts are code.** Keep in `backend/src/story_forge/prompts/` as `.j2` (Jinja2) files, version in git, test like any other code.
