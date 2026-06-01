---
type: glossary-term
slug: idempotency
updated: 2026-06-02
status: living
related: ["[[state-machine]]"]
---

# idempotency (idempotentność)

**Definition:** a property where doing an operation twice has the same effect as doing it once —
re-running is safe.

**Answers:** "what happens if this runs twice?" (a retry, a resumed job, a double-click).

**First encountered in:** [[open-questions]]

It is the backbone of safe recovery: if ingest dies halfway, idempotent per-paragraph writes let
it resume from the last done paragraph instead of duplicating work (see [[open-questions]] OQ-2).
Stable ids (paragraphs already have them) are what make a write idempotent.
