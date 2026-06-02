---
type: glossary-term
slug: model-tier-routing
updated: 2026-06-02
status: living
related: ["[[agent]]"]
---

# model-tier routing (routing po poziomach modeli)

**Definition:** choosing *which* LLM to call per task by **tier** — `local_small` (cheap local)
/ `cloud_free` (free remote) / `cloud_strong` (paid) — behind one provider interface, with
automatic failover within a tier.

**Answers:** "which model should this particular task use, and what happens when it's
unavailable?"

**First encountered in:** [[overview]]

The router sends light tasks to local, medium to cloud-free, heavy to paid, and fails over to
the next provider in a tier on error/rate-limit (§6.5). A key simplification: local-small and
cloud-free *both speak the Ollama API*, so one adapter serves both — a config flip, not a code
fork ([[invariants]] INV-7). **Planned for M2.S2** — today only `adapters/llm/{base,ollama}.py`
exist; the `LLMRouter` and the paid adapters are not yet built (see [[overview]] "as-built").
