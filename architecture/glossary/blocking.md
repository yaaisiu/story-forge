---
type: glossary-term
slug: blocking
updated: 2026-07-06
status: living
related:
  - "[[entity-resolution]]"
  - "[[connected-components]]"
  - "[[cascade-matching]]"
---

# blocking

**Definition:** the standard way to make entity-resolution affordable: instead of comparing every
record against every other (**O(n²)**), first partition records into *blocks* by a cheap key (a name
prefix, a phonetic code, an LSH bucket over embeddings) and only score pairs *within* a block.

**Answers:** "deduplicating N entities is N² comparisons — how do I avoid that when N gets large,
without missing the real duplicates?"

**First encountered in:** [[graph-cluster-dedup]]

Graph-quality S4's self-join (each accepted entity scored against the others) is O(n²) — trivial at
PoC scale (~186 Oakhaven nodes → ~17k pairs, sub-second), so S4 does *not* block. The term is recorded
as the named revisit-lever (Layer 9): a future multi-thousand-node graph would partition into blocks —
e.g. LSH (locality-sensitive hashing) buckets over the mention embeddings, so only semantically-near
pairs are ever scored — trading a small recall risk (a true duplicate split across blocks is never
compared) for a large speed-up. Naming it keeps the O(n²) cost an explicit, deferred decision rather
than a silent surprise.
