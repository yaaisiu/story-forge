---
type: glossary-term
slug: model-tier-routing
updated: 2026-06-18
status: living
related: ["[[agent]]"]
---

# model-tier routing

**Definition:** choosing *which* LLM to call per task by **tier** — `local_small` (cheap local)
/ `cloud_free` (free remote) / `cloud_strong` (paid) — behind one provider interface, with
automatic failover within a tier.

**Answers:** "which model should this particular task use, and what happens when it's
unavailable?"

**First encountered in:** [[overview]]

The router sends light tasks to local, medium to cloud-free, heavy to paid, and fails over to
the next provider in a tier on error/rate-limit (§6.5). A key simplification: local-small and
cloud-free *both speak the Ollama API*, so one adapter serves both — a config flip, not a code
fork ([[invariants]] INV-7). **Built in M2.S2** — `adapters/llm/router.py` (`LLMRouter`, satisfying
the `Router` Protocol in `base.py`) and the preferred paid adapter `openrouter.py`
(`OpenRouterProvider`) now exist alongside `ollama.py`; the further direct vendor adapters
(Anthropic/Grok/Google/OpenAI) stay deferred until a heavier task needs them (provider order +
scope: `docs/decisions/0003`; see [[overview]] "as-built").
