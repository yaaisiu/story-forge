---
type: glossary-term
slug: fail-closed
updated: 2026-06-02
status: living
related: ["[[human-in-the-loop]]"]
---

# fail-closed (domyślnie zamknięty)

**Definition:** when something fails or is uncertain, **deny / stop and ask** rather than
proceed. Its opposite, *fail-open* (domyślnie otwarty), allows on failure — convenient but
unsafe where the wrong "allow" is costly.

**Answers:** "when in doubt, do we proceed or stop?"

**First encountered in:** [[overview]]

Story Forge is fail-closed by design at its two riskiest points: the cascade falls through to a
human on any low-confidence match ([[cascade-matching]]), and the budget cap *refuses* a call
that would breach the limit rather than allowing-and-warning ([[invariants]] INV-5).
