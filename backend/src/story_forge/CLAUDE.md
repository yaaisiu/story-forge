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
