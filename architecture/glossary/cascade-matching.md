---
type: glossary-term
slug: cascade-matching
updated: 2026-06-02
status: living
related: ["[[model-tier-routing]]", "[[human-in-the-loop]]", "[[open-world-ontology]]"]
---

# cascade matching (kaskadowe dopasowanie)

**Definition:** Story Forge's multi-stage decision for "is this extracted candidate a *new*
entity or one that already exists?" — cheap deterministic checks first, expensive ones only when
needed, a human always last.

**Answers:** "is this the same entity we already know, and how little can we spend to be sure?"

**First encountered in:** [[overview]]

The contract — the four stages, their methods, and the similarity thresholds — lives in spec
§3.3; the vault does not restate it. The *architectural force* worth naming: the stages are
ordered **cheapest-first** (free deterministic checks before any token spend) and **fail-closed**
— anything the automated stages can't resolve with confidence falls through to the human,
never auto-merges. That makes it the product's loudest [[fail-closed]] + [[human-in-the-loop]]
surface. Lands in M3; until then [[invariants]] INV-8 holds (no dedupe at all).
