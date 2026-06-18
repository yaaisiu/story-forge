---
type: glossary-term
slug: ego-graph
updated: 2026-06-18
status: living
related:
  - "[[state-machine]]"
  - "[[referential-integrity]]"
  - "[[open-world-ontology]]"
---

# ego-graph (graf egocentryczny)

**Definition:** the subgraph "around" a single focal node (the *ego*) — that node plus its
neighbours and the edges connecting them. A **1-hop** ego-graph keeps only the focal node, the nodes
directly joined to it, and the edges *incident to the focal node*; a 2-hop ego-graph also pulls in
the neighbours' neighbours. It is the standard way to show "this entity and what it relates to"
without rendering the whole graph.

**Answers:** "the spec wants a *local graph around that entity* when I click a highlight — how much
of the graph is 'around', and where do I stop?"

**First encountered in:** [[m4-side-panel]]

Story Forge's reader side panel (M4.S2, spec §3.5) renders a **strict 1-hop** ego-graph for the
clicked entity — the entity, its directly-connected neighbours, and only the edges that touch it
(DM-SP-2). The radius is a deliberate legibility choice: a side panel is narrow, and a 2-hop view of
a busy entity (the protagonist) is a hairball the slice can't yet filter (the §3.4 graph *filters*
are a separate, later concern). Building one means a *neighbourhood* query — "give me the edges
incident to entity E and the nodes on their far end" — which is narrower than the whole-project edge
read the graph viewer uses; a dangling endpoint (a neighbour rejected or merged-away) is **omitted**,
not drawn into the void ([[referential-integrity]], [[fail-closed]]). The neighbour *types* are
open-world strings ([[open-world-ontology]]), so the mini-graph colours them the same
deterministic-palette way the full viewer does, never assuming a fixed type set.
