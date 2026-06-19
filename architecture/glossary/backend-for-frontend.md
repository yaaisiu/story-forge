---
type: glossary-term
slug: backend-for-frontend
updated: 2026-06-19
status: living
related:
  - "[[source-of-truth]]"
  - "[[referential-integrity]]"
  - "[[m4-side-panel]]"
  - "[[m4-entity-editing]]"
---

# backend-for-frontend (BFF)

**Definition:** a server endpoint **purpose-built for one screen's needs** — it assembles exactly the
data that view requires (often joining several stores) and exposes it in the shape the UI consumes,
instead of making the client stitch together general-purpose, store-shaped endpoints. The join, the
filtering, and any cross-store reconciliation live **server-side, in one testable place**, rather than
being re-implemented in the browser.

**Answers:** "the side panel needs an entity's details *and* its 1-hop neighbourhood *and* its
occurrences, spread across Postgres and Neo4j — do I build one endpoint shaped to that screen, or fetch
three general endpoints and join them in TypeScript?"

**First encountered in:** [[m4-side-panel]]

Story Forge reaches for a BFF when a screen's data spans the **cross-store ownership seam** (Postgres
owns paragraphs/mentions story-scoped; Neo4j owns entities/relations project-scoped — there is no
SQL↔Cypher join). The side panel's `GET /stories/{id}/entities/{eid}` (M4.S2a) is the read example: it
joins both stores and resolves the 1-hop [[ego-graph]] in Python, so the neighbour filter and the
dangling-endpoint omission ([[referential-integrity]]) are unit-tested once on the server, not duplicated
untested in the client. M4.S3a proposes the **write** counterpart — a `PATCH …/entities/{eid}` edit
endpoint shaped to the panel's edit affordances. The trade-off a BFF accepts: an endpoint coupled to a
specific screen (it changes when that screen does) in exchange for keeping logic out of the browser and
honouring one home per fact ([[source-of-truth]]).
