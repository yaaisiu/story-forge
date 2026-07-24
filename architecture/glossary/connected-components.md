---
type: glossary-term
slug: connected-components
updated: 2026-07-06
status: living
related:
  - "[[cascade-matching]]"
  - "[[intra-batch-dedup]]"
  - "[[entity-resolution]]"
---

# connected components

**Definition:** in a graph of "these two look like duplicates" edges, a **connected component** is a
maximal set of nodes all reachable from each other — computed by *union-find* (repeatedly union the
two endpoints of every edge, then read off the groups). Turning pairwise similarities into groups.

**Answers:** "the matcher told me A≈B and B≈C — should I treat {A, B, C} as one duplicate cluster,
and what breaks if I do?"

**First encountered in:** [[graph-cluster-dedup]]

Graph-quality S4 suggests duplicate entities by scoring every accepted entity against the others; the
result is a set of *pairwise* similarities. To surface *clusters* (the spec's word), you'd run
union-find over the above-floor pairs — each connected component is a candidate duplicate group. The
trap the note names is **cluster drift**: connected-components chains transitively, so A≈B and B≈C pull
A and C into one component even if A≉C (a common near-name bridges two unrelated identities). The
guard is *star-clustering* — require each member to match the component's representative, not merely
some other member — or stay pairwise (the S4 V1 lean), since the merge is pairwise anyway.
