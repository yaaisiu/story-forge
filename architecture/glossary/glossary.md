---
type: glossary
slug: glossary
updated: 2026-07-24
status: living
related: []
---

# Glossary index

The glossary is a **knowledge graph**, not a flat list: each term is its own note (a node) in
`glossary/`, cross-linked via `related` so concepts form a web you can wander in Obsidian. This
index is **regenerated** each run; the term notes are the source. Terms are added *organically* —
only when real work first surfaces them — and deduped by slug. **English-only** as of Session 103
(the Polish glosses were stripped — owner calibration, `PROJECT.md`). Count today: **36**.

| Term | Answers | Note |
|---|---|---|
| trust boundary | where does control change hands? | [[trust-boundary]] |
| invariant | what must stay true no matter what? | [[invariant]] |
| state machine | what states, which transitions? | [[state-machine]] |
| fail-closed | proceed or stop on doubt? | [[fail-closed]] |
| human-in-the-loop | who has the final say? | [[human-in-the-loop]] |
| idempotency | what if it runs twice? | [[idempotency]] |
| open-world ontology | must I know every category up front? | [[open-world-ontology]] |
| source of truth | which copy is right? | [[source-of-truth]] |
| C4 model | at what zoom level am I reasoning? | [[c4-model]] |
| agent (Story Forge sense) | the unit the LLM pipeline composes from | [[agent]] |
| cascade matching | same entity, for how little spend? | [[cascade-matching]] |
| model-tier routing | which model, and failover to what? | [[model-tier-routing]] |
| compliance / audit layer | what evidence remains afterward? | [[compliance-audit-layer]] |
| deterministic-first | do we actually need an LLM here? | [[prefer-deterministic]] |
| failover | what happens when the provider is unavailable? | [[failover]] |
| TOCTOU | is this guard safe if two things run at once? | [[toctou]] |
| prompt injection | can untrusted text act as instructions? | [[prompt-injection]] |
| poison message | what about input that fails every retry? | [[poison-message]] |
| software composition analysis (SCA) | do any of our deps have a known vuln? | [[software-composition-analysis]] |
| defense in depth | if one control misses, does another catch it? | [[defense-in-depth]] |
| intra-batch deduplication | why can't the queue merge dupes from one pass? | [[intra-batch-dedup]] |
| referential integrity | why not write the edge the moment we see it? | [[referential-integrity]] |
| ego-graph | how much of the graph is "around" this entity? | [[ego-graph]] |
| backend-for-frontend (BFF) | one endpoint per screen, or stitch in the client? | [[backend-for-frontend]] |
| lost update | what stops one edit silently erasing another? | [[lost-update]] |
| compensating transaction (saga undo) | how to undo across two stores with no shared transaction? | [[compensating-transaction]] |
| materialization | derived-on-read or stored-and-addressable? | [[materialization]] |
| multi-tenancy / tenancy key | which owner's slice does this query see? | [[multi-tenancy]] |
| surrogate key | is this the same edge after I curate it? | [[surrogate-key]] |
| reification | how do I say something *about* a relationship? | [[reification]] |
| provenance | where in the text did this fact come from? | [[provenance]] |
| entity resolution | are these two names the same thing, and who decides? | [[entity-resolution]] |
| connected components | A≈B and B≈C — is {A,B,C} one duplicate cluster? | [[connected-components]] |
| blocking | dedup is O(n²) — how to avoid comparing everything? | [[blocking]] |
| direct manipulation | edit the object in place, or in a separate pane? | [[direct-manipulation]] |
| controlled vocabulary | curate the labels without closing the set? | [[controlled-vocabulary]] |
