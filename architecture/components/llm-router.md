---
type: component
slug: llm-router
updated: 2026-07-24
status: living
related: ["[[overview]]", "[[invariants]]", "[[model-tier-routing]]", "[[failover]]", "[[trust-boundary]]", "[[fail-closed]]", "[[provenance]]"]
---

# LLMRouter

Component-altitude note ([[c4-model]]) for `backend/src/story_forge/adapters/llm/router.py`
(`class LLMRouter`). The one piece of code that stands on the system's only real
[[trust-boundary]] — machine ↔ external LLM provider — and the one that spends money. Spec §6.5/§6.6,
ADR 0003.

## Responsibility

Route a task to the model tier its *weight* implies, try that tier's providers in order with
error-discriminated **failover**, enforce a fail-closed daily USD budget, and record one cost-ledger
row per call. (The several verbs share one reason to change — "how a task's LLM call is dispatched
and accounted for" — so this is one component, not several.)

## Source of truth

Owns the **transport-and-spend** concerns no single agent should re-implement: the weight→tier map
(`tier_for_weight`), the cross-provider failover *policy* within a tier, the `DAILY_BUDGET_USD` gate,
and the shape of each `llm_calls` ledger row (via `CostStore`). It does **not** own: the provider
*preference order* (wired as the per-tier list in `main.py` per ADR 0003 — the router stays
provider-agnostic), schema validation + its retry (the agent's job — the ChunkingAgent pattern), or
the wall-clock `created_at` on a ledger row (the store's).

## Interfaces

- **Exposes:** a single `async complete(messages, *, weight, task_type, json_schema)` →
  `CompletionResult`. Called by the router-driven agents (`ExtractionAgent`, `MatchingAgent`,
  `JudgeAgent`, `ChunkingAgent`) through the `Router` Protocol (`adapters/llm/base.py`) — they type
  against the Protocol, never this module, and `LLMRouter` structurally satisfies it.
- **Consumes:** the per-tier `list[LLMProvider]` adapters (`OllamaProvider`, `OpenRouterProvider`, …)
  and a `CostStore` (the ledger). Injected at construction in `main.py`.

## Invariants

- **Fail-closed budget** ([[fail-closed]]): on a paid tier, if today's spend has reached the cap the
  router refuses **before dispatch** (records a `refusal` row, raises `BudgetExceededError`) — a free
  tier is never blocked by the paid cap. A bounded one-call overshoot is accepted (single-user PoC,
  spec §6.6). Related to **INV-2** (the consent-before-paid-egress gate), which is *deferred past M3*
  and persona-justified — the budget cap is the spend ceiling that stands in for it today.
- **Error-discriminated failover** ([[failover]]): 429 / 5xx / 401 / transport error → try the next
  provider; other 4xx → re-raise (failover won't fix a bad request); a paid adapter's
  `BudgetExceededError` (402) → re-raise, never escalate to the next provider. Only a `cloud_free`
  tier exhausted **purely** by quota (429, no other failure) raises `QuotaExhaustedError` (pause and
  ask) — a bad key or outage surfaces the *real* error instead, never a false "quota" cry.
- **One ledger row per call** (the [[provenance]] guarantee): every dispatch — success, refusal, or
  failure, including a malformed-envelope `ProviderResponseError` — writes exactly one `llm_calls`
  row. This is the invariant OQ-10 closed (an uncaught envelope error used to leave the row gap open).
- **Keys never logged (INV-6, vacuously today).** The router handles no key material directly (the
  adapters own auth headers); the backend emits no operational logs yet, so redaction holds vacuously
  — the manual key-leak smoke is the regression guard for when logging lands.

## State

**Stateless per call.** The router holds only its injected collaborators + an injectable monotonic
`clock`; all mutable spend state lives in the `CostStore`, not here (which is why `spend_today_usd()`
is read fresh at each budget check). The **LLM-call lifecycle** it drives (`dispatched → {success |
refusal | failure}`, with failover as an intra-call retry loop) is *sketched* in
[[m2s2-llm-router-budget-cap]] but not yet drawn as a formal `state-machines/` note — a deliberate
deferral (the failure/fallback behaviour is fully captured here + in the code's control-first
docstring; no forcing need to formalise it).

## Layer fingerprint

- **Security** — sits on the system's **only** real [[trust-boundary]] (machine ↔ external provider):
  the moment the author's text is dispatched to a cloud tier it leaves the fully-trusted local
  context. No inter-user authz (single full-trust persona); auth headers are the adapters' concern and
  are never logged (INV-6). The abuse surface is a compromised/misconfigured provider — hence
  error-discriminated failover that refuses to *silently* escalate spend on a bad key.
- **Data sensitivity** — dispatches the author's **prose** to a third party on the cloud tiers (the
  sensitive crossing). The ledger rows it writes carry only **metadata** — tier, provider class name,
  model, token counts, cost estimate, latency — never the prompt/response content and never keys.
- **Errors** — **fail-closed** on budget (refuse before dispatch); error-discriminated failover within
  a tier; the two pause-and-ask control signals (`QuotaExhaustedError`, `BudgetExceededError`)
  propagate *raw* past the agent to the API boundary, where a route maps each to its own status.
- **Compliance / Audit** — the `llm_calls` ledger is the durable "what remains after the fact": one
  row per call, the spend audit trail *and* the **data-flywheel substrate** (accumulating finetuning
  signal — distinct from operational logging, which does not exist yet; see `backend/AGENTS.md`).
- **Operations** — `latency_ms` is captured per call (spec §6.6 / OQ-9) and surfaced in the §8.5
  agent-activity panel; a budget-status read answers "how much spend is left today?". No operational
  logs today (the observable signal is the ledger, not stdout).
