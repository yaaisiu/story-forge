---
type: glossary-term
slug: entity-resolution
updated: 2026-07-06
status: living
related:
  - "[[cascade-matching]]"
  - "[[intra-batch-dedup]]"
  - "[[connected-components]]"
  - "[[blocking]]"
  - "[[human-in-the-loop]]"
---

# entity resolution

**Definition:** deciding which records refer to the *same real-world thing* and linking or merging
them — the umbrella field that [[cascade-matching]] (match a new candidate against the graph),
[[intra-batch-dedup]] (collapse duplicates within one run), and Graph-quality S4 (dedup the
*already-accepted* graph) are each an instance of.

**Answers:** "are these two names the same character, and who decides — the machine or the human?"

**First encountered in:** [[graph-cluster-dedup]]

Story Forge does entity resolution at three moments on one shared deterministic signal (RapidFuzz name
similarity + embedding cosine): at **intake** the cascade proposes a match before a candidate is
written; **within a run** the re-match collapses same-run duplicates; and at **curation time** (S4) the
same matcher is turned *inward* — every accepted entity scored against the others — to surface
duplicates the author would hunt for by eye. The invariant that unites all three: the machine only ever
*proposes* ([[prefer-deterministic]] scoring, no auto-merge on a diminutive), and a
[[human-in-the-loop|human]] commits (INV-1). S4 is the resolution pass with no auto-merge branch at
all — every suggestion is human-gated.
