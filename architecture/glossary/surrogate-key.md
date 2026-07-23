---
type: glossary-term
slug: surrogate-key
updated: 2026-06-29
status: living
related:
  - "[[referential-integrity]]"
  - "[[idempotency]]"
  - "[[reification]]"
  - "[[graph-curation-surface]]"
---

# surrogate key (klucz zastępczy)

**Definition:** an identifier with **no meaning of its own** — a random/opaque id (a `uuid4`) minted to
name a record, *independent of the record's content*. Its opposite is a **natural key** (klucz
naturalny) — an id *derived from the data itself*, so the id changes whenever the data does. Story
Forge's edges use a natural key today: `relation_edge_id = uuid5(subject, predicate, object)`, so the id
**is** the fact. That is elegant for [[idempotency]] (the same triple always MERGEs to the same id —
automatic dedup, ADR 0005) but fragile for *addressing*: re-point an endpoint or rename the predicate
and the id *changes* — the edge is, identity-wise, a new edge.

**Answers:** "if I clean up this edge (merge an endpoint, consolidate the predicate), is it still the
*same* edge — can something attached to it survive the change?"

**First encountered in:** [[graph-curation-surface]]

The architectural call where the two collide (Graph-quality §4 / DM-GQ-1): a content-addressed
(natural-key) edge cannot carry anything that must *outlive curation*, because curation changes its id.
If a later model wants to attach a qualifier to a specific relationship ([[reification]] — "true only in
ch. 3", "rumoured not certain"), the edge needs a **stable handle** that survives re-pointing — a
surrogate key carried *alongside* the natural key (the natural key stays the dedup/MERGE key; the
surrogate is the addressable handle). The discipline §4 names: it costs one opaque id + a "preserve on
re-point" rule now, and makes the future feature *additive* rather than a re-key migration — but only if
you also answer the **survivor question** (when two edges fold into one, which surrogate handle
survives? — the [[referential-integrity]]-flavoured edge of any identity merge).
