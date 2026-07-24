---
type: glossary-term
slug: prefer-deterministic
updated: 2026-06-02
status: living
related: ["[[cascade-matching]]"]
---

# deterministic-first

**Definition:** a design preference to solve with deterministic or user-assisted methods
*before* reaching for an LLM — use the model only where cheaper, repeatable means genuinely fall
short.

**Answers:** "do we actually need an LLM here, or will code/rules do it more cheaply and
predictably?"

**First encountered in:** [[overview]]

Visible across Story Forge: PreNER is pure spaCy (no LLM), the cascade spends tokens only at
Stage 3 after two free stages, and the M2 session order opens with the deterministic PreNER
baseline (smallest blast radius). It pairs with the §11 *determinism-where-possible* principle
(temperature 0 + seed) so results stay repeatable — important when `edit_history` is a dataset.
