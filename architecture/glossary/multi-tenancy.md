---
type: glossary-term
slug: multi-tenancy
updated: 2026-06-24
status: living
related:
  - "[[source-of-truth]]"
  - "[[materialization]]"
  - "[[referential-integrity]]"
  - "[[m4-multi-story]]"
---

# multi-tenancy / tenancy key (wielodostępność / klucz dzierżawy)

**Definition:** a single shared store serves many isolated logical owners (*tenants*), and every row/
node carries a **tenancy key** — the column or property that says which tenant it belongs to — so a
query scopes to one tenant by filtering on that key. The alternative (a separate database per tenant)
is cleaner isolation but heavier to run. Story Forge uses the property-based form: `project_id` on
every Neo4j `:Entity` is the tenancy key (spec §6.4 — "simple filter via `project_id` … sufficient
for PoC"; Neo4j multi-database would need Enterprise).

**Answers:** "many owners' data lives in one graph — how do I make sure a query only ever sees *one*
owner's slice, and what is the single field that decides ownership?"

**First encountered in:** [[m4-multi-story]]

The distinction the multi-story slice forces into the open: a **project** is the tenant (the
[[source-of-truth|authoritative]] scope key on every graph node), and a **story** is a *sub-scope
within* a tenant — not a second tenant. One-story-per-project let us blur the two; multi-story
separates them. Two scopes now coexist and must not be confused: the **tenancy key** (`project_id`,
*stored* on every node — hard isolation) versus **per-story membership** ("which entities appear in
this story", *derived* from mention data, not stored — [[materialization]]). A new story shares the
tenant's graph (so known entities seed its extraction) while still answering "what belongs to *this*
story" as a derived filter — tenant-wide reuse and sub-scope views from the same nodes.
