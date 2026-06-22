# AGENTS.md — src/story_forge/

This is the application code. The most important rule: **layering**.

## Layering

```
api/         ← HTTP routes; thin, no business logic
agents/      ← orchestration modules — one logical task per file (chunking, extraction, judging, ...)
domain/      ← business logic, pure, no I/O, no HTTP
adapters/    ← I/O: DBs, LLMs, file system, external HTTP
prompts/     ← Jinja2 prompt templates, PL + EN variants, versioned in git
config.py    ← settings via pydantic-settings; reads .env
main.py      ← FastAPI app construction and wiring
```

**Rules:**
- `domain/` must not import from `api/`, `agents/`, or `adapters/`.
- `domain/` defines protocols (`typing.Protocol`) for what it needs; `adapters/` implements them.
- `agents/` may import from `domain/` and from the `LLMProvider` Protocol — never from a concrete adapter.
- `api/`, `agents/`, and `adapters/` are wired in `main.py` via dependency injection.
- A test of a `domain/` module must not need a database or network. An agent test must not need a real LLM — it gets a mocked `LLMProvider`.

If you find yourself wanting to import `httpx` or `neo4j` in `domain/` or `agents/`: stop. Add a protocol. Implement in `adapters/`.

## API routes

`api/` routes are thin HTTP wrappers around `agents/` and `domain/`. Two rules that
authoring (not just reviewing) needs to hold:

- **Declare every non-2xx outcome.** Every `HTTPException` a route raises (or maps from a
  domain exception) must have a matching entry on the decorator's
  `responses={status: {"model": ErrorResponse, "description": "..."}}` — and there must be
  exactly one shared `ErrorResponse(BaseModel)` (with `detail: str`) that all routes use.
  Without `responses=`, the OpenAPI schema shows only the success status + the
  auto-generated 422 validation error; the typed TypeScript client at
  `frontend/src/lib/api/schema.d.ts` then can't model the failure paths the frontend has
  to handle (the documented 409 re-structure conflict, a 404, a 502 from an unreachable
  LLM, …). After adding or changing a route, walk every `raise HTTPException(...)` in its
  body and confirm the status appears in `responses=`; then regenerate the snapshot
  (`backend/scripts/dump_openapi.py` → `npm run generate:api`) so the contract is visible
  in the next PR diff.
- **The 422 trap.** FastAPI auto-attaches 422 to every route for request-validation
  errors with shape `HTTPValidationError`. If your route *also* raises an explicit
  `HTTPException(status_code=422, ...)` for a domain-level error (e.g. "input too long"),
  declaring 422 in `responses=` would clobber the validation shape with `{detail: str}`
  and break the typed client's discrimination of the two cases. Either (a) remap the
  domain error to a different status code (413 "payload too large" fits "input too long"
  honestly), or (b) leave 422 out of `responses=` and track the overload as a cross-cutting
  follow-up. Don't quietly overwrite the validation shape.

## LLM adapter

`adapters/llm/` follows the three-tier strategy from spec §6.5 (provider order + scope: `docs/decisions/0003`):
- `OllamaProvider` serves both local small (host=localhost:11434) and cloud free (host=ollama.com with API key)
- `OpenRouterProvider` — the **preferred paid route** (one OpenAI-compatible endpoint reaching Grok/Claude/Gemini/GPT); **the only paid adapter built in M2.S2**
- `AnthropicProvider`, `GrokProvider`, `GoogleProvider`, `OpenAIProvider` — direct paid adapters, **built as needed** (deferred past M2.S2)
- all adapters are hand-rolled over `httpx` (no vendor SDKs), mirroring `OllamaProvider`'s injectable-transport shape
- `router.py` decides which tier per call and handles cross-provider failover within a tier

## Agents

`agents/` contains the orchestration modules from spec §6.5. Each agent module owns:

- one logical task (chunking, extraction, judging, ...)
- the Pydantic input/output schemas for that task
- a thin orchestration function: load prompt → call router → parse + validate → retry on failure
- the prompt template lives in `prompts/<agent>.<lang>.j2` (never as f-strings in code)

To add a new agent: copy an existing one, change the prompt + schema, register its preferred tier. No god-class to edit.

**Output-parsing helpers shared across agents live in `agents/json_output.py`, not
duplicated per agent.** `extract_json` (strip a model's markdown code fence before
Pydantic) is used by `ChunkingAgent`, `ExtractionAgent`, and `JudgeAgent`; the moment a
second agent needed it, it moved out of the agent module into the shared helper rather
than being copy-pasted.

**The validate-and-retry loop is shared via `agents/validation.py`
(`validate_with_retry`), folded at the rule-of-three.** The `call → extract_json →
validate-against-schema → retry-on-ValidationError → give-up` loop was copied per-agent
through n=2 (Chunking + Extraction, deliberately left per-copy); `JudgeAgent` was the
third, so the mechanical loop moved into one helper. Each agent still owns the parts that
are genuinely its own — its **schema** (passed as `model`), its **call shape** (the
`call` thunk: a raw provider vs the router, the weight/`task_type`), and its **give-up
error** (`error` + `label`). Only the schema-agnostic loop mechanics are shared. The
router-shaped collaborator each router-driven agent types against is the `Router` Protocol
in `adapters/llm/base.py` (promoted there from a per-agent local mirror at the same n=3),
alongside the `TaskWeight` literal — so an agent stays free of the concrete `router`
module while `LLMRouter` structurally satisfies the Protocol.

**Make an agent's give-up error *total* when a consumer fail-closes on it.** `validate_with_retry`
raises the agent's give-up error only on *schema* give-up; the router's terminal **transport/
envelope** failures (`httpx.HTTPError`, `ProviderResponseError`) and the pause-and-ask control
signals (`BudgetExceededError`/`QuotaExhaustedError`) propagate *past* it, raw. That is correct at
the API boundary (a route maps each to its own status). But when another component **fail-closes**
on the agent — catching its give-up error to route a candidate to the human rather than crash — that
`except` sees only the schema give-up, so a *provider-unreachable* failure escapes the fail-closed
branch. Fix it at the agent: wrap the `validate_with_retry` call so a terminal
`(ProviderResponseError, httpx.HTTPError)` is re-raised as the agent's give-up error (let Budget/
Quota keep propagating — they are the pause signal, not an "I couldn't produce output" signal). Then
the agent's give-up error means "could not produce output, for any reason except pause", and a
consumer fail-closes on one exception type. (M3.S4a / PR #63: the cascade caught only `JudgeError`,
so a judge-provider outage 502'd the whole batch instead of staging the candidate as uncertain;
`JudgeAgent.judge` now converts transport→`JudgeError`. Review-side mirror: `/review-pr` §1.)

**Deterministic local NLP is an exception to "no concrete deps in agents."** The
layering rule above ("agents import the `LLMProvider` Protocol, never a concrete
adapter") targets network/DB I/O and the multi-provider LLM tier. `PreNERAgent`
imports spaCy directly (lazily, in `_pipeline`) because it is deterministic, purely
local compute with no provider choice to abstract — a Protocol would be ceremony for
a single implementation (Karpathy: no abstractions for single-use code). The reusable
logic that *doesn't* need spaCy (`candidates_from_entities`, `map_spacy_label`) is
factored into pure functions so it stays CI-testable without the model. **Revisit
this** if a second NER backend ever appears (e.g. a finetuned model alongside the
stock pipelines) — at that point a `NerPipeline` Protocol earns its place.

## Prompts

Prompts live in `prompts/` as Jinja2 templates (`.j2`). One file per logical prompt. Versioned in git. Loaded via a small helper, not f-strings scattered around the code. Both PL and EN variants per prompt.

**Build a prompt from the spec's Appendix C template, not the §3 prose alone.** Each agent's prompt is described in *two* spec homes: the §3 functional prose (e.g. §3.3 "candidate in context vs existing entity + its properties + recent mentions") and the **Appendix C** concrete template (e.g. C.3 with its exact `[SYSTEM]`/`[USER]` blocks and full field list). Both are spec; **Appendix C is the authoritative, complete field set** — the prose summarises. When authoring or changing a prompt, render every field the Appendix C template lists and cross-check §3, then assert each field reaches the model in a test. (M3.S3 lesson: the judge prompt was built from §3.3's prose and silently dropped C.3's existing-entity `aliases` — the exact diminutive signal Stage 3 exists to use — plus the candidate `type`/`properties`; the single `/review-pr` missed it, the multi-agent `/code-review` caught it. The review-side mirror is in `/review-pr` §2.)

## Common pitfalls to avoid here

- Don't fetch from Neo4j inside an API route handler. Go through the domain.
- Don't accept LLM JSON output without Pydantic validation. Always parse, always retry on parse failure.
- Don't write a "smart" function in `domain/` that has side effects. Side effects belong in adapters.
- Don't inline a prompt in an agent module. It belongs in `prompts/`.
- **When two functions are coupled by a string literal, test the consumer from the
  *producer's real output*, not a hand-built fixture of that string.** A producer that emits a tag
  and a consumer that branches on it (an op-kind written to a row and matched by an inverter; a
  discriminator one side sets and the other dispatches on; an event name; a status string) share a
  contract no type enforces — a typo or rename on one side silently breaks the pair. A unit test
  that *hand-builds* the consumer's input with the literal validates a fiction: it passes whether or
  not the producer actually emits that string. So drive at least one consumer test from the
  producer's genuine output (call the producer, feed its result to the consumer) — that is the only
  test that fails when the two drift. (M4.S3b-be2: the merge writer recorded
  `op="discard_self_loop_relation"` (`_merge_rows`) but `graph_undo.invert_operation` matched
  `"discard_self_loop"`, so a self-loop merge's undo raised `UndoNotInvertible` → 500; the inverter's
  unit test had hand-built a row with the bare name the writer never emits, so CI stayed green until
  the browser smoke hit it. Fixed by matching the real op + a contract test driven from `_merge_rows`
  output. This is the producer/consumer generalisation of the "fabricated fixture validates fiction"
  lesson `/review-pr` §2 records for HTTP-status and LLM-schema fixtures.)
