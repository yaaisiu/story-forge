---
type: glossary-term
slug: controlled-vocabulary
updated: 2026-07-13
status: living
related:
  - "[[open-world-ontology]]"
  - "[[entity-resolution]]"
  - "[[prefer-deterministic]]"
  - "[[human-in-the-loop]]"
  - "[[graph-name-normalisation]]"
---

# controlled vocabulary

**Definition:** a **curated, deliberately-small set of preferred labels** for a category of thing, that
different surface forms are normalised *toward* — so one concept isn't split across `PERSON`/`Person` or a
relationship across `PASSENGER_ON`/`ON_SHIP`. It is the middle ground between a **closed enum** (a fixed
list fixed up front — rejected here by [[open-world-ontology]] / INV-4) and a **fully free-for-all** label
space (every extraction invents its own spelling — the over-extraction Graph-quality exists to curate).

**Answers:** "how do I reduce the *noise* of near-synonymous type/predicate names without *closing* the set
— keeping it open-world (a genuinely new kind can still appear) while converging the accidental synonyms?"

**First encountered in:** [[graph-name-normalisation]]

The distinction that matters for Story Forge (Graph-quality S6): a controlled vocabulary is reached **by
human choice, never enforced by code.** INV-4 keeps types/predicates free strings; S6 *suggests* which
labels look synonymous (deterministic fuzzy + local embedding — [[prefer-deterministic]]) and the author
*renames* them graph-wide, but the machine never auto-collapses two labels ([[human-in-the-loop]]). So the
vocabulary is "controlled" the way a copy-editor controls house style — a convergence the human drives —
not the way a database `CHECK (type IN (...))` constraint controls a column. Contrast [[entity-resolution]]:
that dedupes *entities* (two nodes that are the same thing); vocabulary normalisation dedupes *labels* (two
names for the same kind of thing), a strictly smaller and cheaper set (tens of labels, not hundreds of
entities). The forward-compat cost is asymmetric — normalising a *predicate* re-keys edges (it is part of
the content-addressed id) and rides the [[surrogate-key]] handle; normalising a *type* is a plain
property relabel.
