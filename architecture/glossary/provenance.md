---
type: glossary-term
slug: provenance
updated: 2026-07-01
status: living
related:
  - "[[compliance-audit-layer]]"
  - "[[source-of-truth]]"
  - "[[surrogate-key]]"
  - "[[referential-integrity]]"
---

# provenance

**Definition:** the recorded trail of *where a piece of derived data came from* — for a graph edge,
the source paragraph(s) and the model's supporting quote(s) that assert the fact the edge states.

**Answers:** "the graph says `Janek —PASSENGER_ON→ the ship` — *where in the text* did that come from,
so I can verify it before I trust or curate it?"

**First encountered in:** [[graph-edge-evidence]]

Distinct from the [[compliance-audit-layer]] (which records the trail of *human decisions* — who
accepted/edited what, for undo): provenance is the trail back to the *source text*, the evidence a
human reads to judge whether an extracted fact is real. In Story Forge it survives commit but was
unreachable until S3: a committed relation's `staged_relations` row persists as `status='written'`
with its `paragraph_id` + `evidence_quote` intact, keyed by the committed `edge_id`. Because the edge
id is **content-addressed** (`uuid5(subject,predicate,object)`), the *same fact* stated in several
paragraphs collapses to one edge but keeps *several* provenance rows — so an edge's provenance is
**one-to-many** (a list of source sentences, not a single origin). Surfacing it is what makes the
human gate (INV-1) trustworthy: the gate is only as good as the context it shows.
