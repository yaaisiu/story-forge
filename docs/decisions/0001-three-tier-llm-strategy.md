# ADR 0001 — Three-tier LLM strategy

**Status:** Accepted — **provider-priority and quota-degradation consequences superseded by [ADR 0003](0003-llm-router-provider-order-and-budget.md) (2026-06-02)**; the three-tier model and the one-`OllamaProvider`-for-two-tiers decision stand.
**Date:** 2026-05-19
**Related spec section:** §6.5

## Context

The project requires LLM access for chunking, entity extraction, judge calls, and editing/rewriting. Constraints:

- Development machine has no discrete GPU (or 8GB VRAM at most), so 70B local models are off the table.
- The PoC doubles as a public portfolio demonstrator, so the LLM layer must clearly model swappability across providers and cost tiers — not bury the choice in a single provider SDK.
- Free options are preferred where they exist (chunking, batch extraction, judge calls add up fast at paid rates).
- The system must remain useful when any single provider is degraded or rate-limited.

## Decision

We use three tiers of LLM access:

1. **Local small** — Ollama running Qwen3.5 9B Q4_K_M on the dev machine. Used for chunking, summaries, simple structured extraction.
2. **Cloud free** — Ollama Cloud free tier, identical API to local Ollama, no local GPU needed. Used for medium tasks (entity extraction batches, judge calls). Bound by 5h session / 7-day weekly GPU-time quotas.
3. **Cloud strong** — Anthropic and OpenAI as primary paid providers; Grok (xAI) as an alternative; OpenRouter as a meta-provider for additional model variety and cost arbitrage. Used for heavy editing, rewrites, and long-context work.

A single `OllamaProvider` adapter serves both tier 1 and tier 2 (only host URL differs). Router (`adapters/llm/router.py`) selects tier per call and performs cross-provider failover within a tier (network error, rate-limit, schema-parse failure → next configured provider, swap logged).

The ingest pipeline is structured as **agents** (spec §6.5) — `ChunkingAgent`, `ExtractionAgent`, `JudgeAgent`, etc. — each declaring a preferred tier and owning its prompt template + Pydantic output schema. Agents consume the router; the router consumes adapters.

## Alternatives considered

- **Single strong cloud provider only:** simpler, but burns money for chunking/judge calls and creates a single point of failure.
- **Single local model:** impossible on 8GB VRAM for medium-weight tasks where the small model underperforms.
- **OpenAI-compatible API everywhere:** Ollama already exposes one; in principle everything could go through that shim, but providers' rate-limit semantics and quirks are worth surfacing in distinct adapters.
- **Adopt an agent framework (LangGraph, Pydantic AI, smolagents, OpenAI Agents SDK):** would give us tracing and abstractions for free, but adds dependencies and obscures the pattern we want to demonstrate. Open question — see spec §10 item 5.

## Consequences

- Two `OllamaProvider` instances configured in DI, differing only by host/API key.
- Quota tracking handles GPU-time (Ollama Cloud) and per-token (paid providers) in parallel.
- User-visible UI must show which tier was used and why, plus current quota state (see §8.5 — agent activity panel).
- When Ollama Cloud quota is exhausted, the router degrades to local_small with a warning. Pausing for user input is acceptable too.
- Prompts must be tested against all three tiers; output schemas are enforced via Pydantic with retry on parse failure.
- Adding a new provider = one adapter class + a router config entry. Adding a new agent = one prompt template + one Pydantic schema + one orchestration function.
