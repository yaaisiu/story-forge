---
type: glossary-term
slug: compliance-audit-layer
updated: 2026-06-02
status: living
related: ["[[trust-boundary]]"]
---

# compliance / audit layer (warstwa zgodności / audytu)

**Definition:** the architectural axis asking *"can we prove what happened, and that we met our
obligations?"* — the durable evidence trail that remains after the fact. Distinct from Security,
which asks *"can an attacker break in?"*.

**Answers:** "what evidence remains afterward, and can we trust it?"

**First encountered in:** [[overview]]

Story Forge has no external regulator, yet this layer is loud because of a *self-imposed*
requirement: `edit_history` is an append-only `(before, after, intent, source, model, prompt,
accepted)` log meant to become a training dataset (§4.2), every LLM call is logged, and every
automatic decision is reversible. (This layer was split out from Security in the meta-architect's
own ADR 0001 — proof that the framework itself evolves on the record.)
