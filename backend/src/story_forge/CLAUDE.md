# CLAUDE.md — src/story_forge/

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

`adapters/llm/` follows the three-tier strategy from spec §6.5:
- `OllamaProvider` serves both local small (host=localhost:11434) and cloud free (host=ollama.com with API key)
- `AnthropicProvider`, `OpenAIProvider`, `GrokProvider` — paid cloud tier
- `OpenRouterProvider` — meta-provider for additional model variety and cost arbitrage
- `router.py` decides which tier per call and handles cross-provider failover within a tier

## Agents

`agents/` contains the orchestration modules from spec §6.5. Each agent module owns:

- one logical task (chunking, extraction, judging, ...)
- the Pydantic input/output schemas for that task
- a thin orchestration function: load prompt → call router → parse + validate → retry on failure
- the prompt template lives in `prompts/<agent>.<lang>.j2` (never as f-strings in code)

To add a new agent: copy an existing one, change the prompt + schema, register its preferred tier. No god-class to edit.

## Prompts

Prompts live in `prompts/` as Jinja2 templates (`.j2`). One file per logical prompt. Versioned in git. Loaded via a small helper, not f-strings scattered around the code. Both PL and EN variants per prompt.

## Common pitfalls to avoid here

- Don't fetch from Neo4j inside an API route handler. Go through the domain.
- Don't accept LLM JSON output without Pydantic validation. Always parse, always retry on parse failure.
- Don't write a "smart" function in `domain/` that has side effects. Side effects belong in adapters.
- Don't inline a prompt in an agent module. It belongs in `prompts/`.
