# ADR 0003 — LLM router: provider order, hand-rolled adapters, and control-first budget posture

**Status:** Accepted
**Date:** 2026-06-02
**Related spec section:** §6.5 (provider abstraction & router), §6.6 (token budget & cost)
**Supersedes:** the provider-priority and quota-degradation *consequences* of ADR 0001 (the
three-tier strategy itself stands).

## Context

ADR 0001 set the three-tier strategy (`local_small` / `cloud_free` / `cloud_strong`) and named
"Anthropic and OpenAI as primary" with "OpenRouter as meta-provider." Building Milestone 2, Session 2
(the `LLMRouter` + paid adapters + cost tracking + budget cap) forced the concrete decisions ADR 0001
left open, and two facts on the ground reshaped them:

- The dev host is **GPU-less**, so `local_small` is unavailable and ADR 0001's "quota exhausted →
  degrade to local_small" consequence is unreachable (already half-acknowledged in the spec §6.5 GPU-less-host paragraph;
  flagged as stale in `architecture/reports/2026-06-02-architecture-review.md`).
- The owner prioritises **control over convenience** for spend, and the PoC handles no
  security-sensitive data.

This ADR was produced through a meta-architect dogfood pass (`review-architecture` +
`decompose-requirement`, 2026-06-02) whose proposal `architecture/proposals/m2s2-llm-router-budget-cap.md`
enumerated the edge cases and framed the options; the decisions below are the owner's resolutions.

## Decision

1. **Provider preference order:** **Ollama** (local_small / cloud_free) → **OpenRouter** → **Grok** →
   **Anthropic** → **Google (Gemini)** → **OpenAI**. OpenRouter is the *first* paid/meta route because
   one OpenAI-compatible endpoint reaches most vendor models (Grok/Claude/Gemini/GPT) — cost arbitrage
   with far fewer adapters to build and vet.
2. **Adapters are hand-rolled over `httpx`** (mirroring `OllamaProvider`), not per-vendor SDKs: one
   uniform adapter shape, **zero** new dependencies, an injectable transport for tests, and the
   multi-provider swappability stays visible in our own code (a stated portfolio goal, §6.5). The
   accepted cost is hand-writing each provider's request/response + token-usage parsing.
3. **M2.S2 builds only `OllamaProvider` (extended) + `OpenRouterProvider`.** The direct per-vendor
   adapters (Grok/Anthropic/Google/OpenAI) are deferred and built **as needed** — OpenRouter covers
   them in the meantime.
4. **Control-first failover & degrade.** Within-tier failover is error-discriminated: 429/5xx → fail
   over to the next configured provider; 401 bad-key → fail fast (skip, never retry); malformed output
   schema → retry the prompt N times then give up. On a GPU-less host, where `local_small` would be
   used, the router picks the cheapest **cloud_free** model instead. When **cloud_free quota is
   exhausted OR the daily budget cap is reached**, the router **pauses and asks the user** how to
   proceed — it **never** silently escalates to a paid tier.
5. **Budget.** A per-day USD hard ceiling (`DAILY_BUDGET_USD`), **fail-closed** (checked *before*
   dispatch). Usage is one row per call in a single `llm_calls` table, nullable per tier (input/output
   tokens + cost_estimate for paid; GPU-seconds for cloud_free), with daily / project / per-task-type
   aggregation read from it (no parallel counter). Tier/provider/model are **system-derived** from the
   adapter that served the call, never the caller's echoed label. Best-effort under concurrency with a
   bounded one-call overshoot (single-user PoC).
6. **Paid-egress consent gate deferred to M2.S5.** The PoC handles no security-sensitive data, so the
   explicit per-fragment consent UI ("sending fragment to Anthropic, OK?") is *not* built in M2.S2; the
   egress points carry a clear in-code marker noting the deferral. (INV-2's full guard lands with the
   M2.S5 panel.)
7. **Google (Gemini) added** to the provider set (spec §6.5 amended).

## Considered options

- **Keep ADR 0001's "Anthropic/OpenAI primary":** rejected — OpenRouter-first reaches the same models
  through one adapter, and the owner's order is explicit.
- **Official vendor SDKs (anthropic/openai/google-genai/…):** rejected — 5 providers = 5 dependencies
  to pin/soak/scan (§6.7), each a different shape and test story, and the swappability we want to
  *demonstrate* would be buried in vendor libraries. (See `decompose` D2.)
- **Auto-escalate to cheapest paid on free-quota exhaustion (within the cap):** rejected by the owner
  in favour of pause-and-ask — control over unattended spend is the priority, even at the cost of
  interrupting long batches. (See `decompose` G1.)
- **A default-deny paid-egress gate in M2.S2 (proposed temporary INV-9):** rejected — no sensitive
  data; documented deferral instead. (See `decompose` D5.)
- **Two usage tables (paid vs free) / reserve-then-reconcile cap:** rejected for the PoC — one table
  with nullable units and a bounded-overshoot cap is enough at single-user scale. (See `decompose`
  D3/D4.)

## Consequences

- **Cost accepted:** we hand-write per-provider parsing; and making OpenRouter the preferred route
  concentrates the common path on **one external dependency's uptime** — mitigated by the Ollama tiers
  beneath it and the direct adapters we can add later.
- OpenRouter is **pulled forward** from its original M2.S6 slot into M2.S2; the direct vendor adapters
  that were to be scaffolded in M2.S2 are deferred. `docs/PLAN_SHORT.md` Session 2 / Session 6 updated.
- `CompletionResult` + the `LLMProvider` Protocol grow to carry usage (model, tokens, GPU-seconds,
  cost) — `OllamaProvider` stops discarding Ollama's `eval_count`/`prompt_eval_count` (INV-5 / OQ-7).
- A new `llm_calls` Postgres table + migration; a status endpoint surfacing spend + GPU quota.
- **ADR 0001 is superseded in part** (provider priority + quota-degradation); its three-tier strategy
  and one-`OllamaProvider`-for-two-tiers decisions remain in force.
- Spec §6.5 / §6.6 amended (2026-06-02). The architecture vault's INV-2/5/7 notes and OQ-3/6/7/8 are
  reconciled to these decisions.
