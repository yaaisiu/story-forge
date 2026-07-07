# ADR 0010 — Persisting duplicate-suggestion dismissals: a staging-side pair store

**Status:** Accepted
**Date:** 2026-07-07
**Related spec section:** `docs/specs/graph-quality.md` §3 S4 (suggest duplicate clusters over the
accepted graph), §8 (invariants carried in: INV-1/INV-9 human gate, INV-4 open-world); main spec §3.3
(the cascade matcher this re-points), §6.4 (the Postgres staging schema this joins).
**Builds on:** the `candidate_decisions` / [[intra-batch-dedup|DM-rej]] precedent (remembering a
human's rejection is a feature, not clutter) and the OQ-1 cross-store seam (a Neo4j id carries no
Postgres FK). Sibling of ADR 0008's `mention_suppressions` — both are "a negative record the read
subtracts", staging-side.
**Scope note:** landed with **graph-quality S4a (backend)** — the pure self-join
(`domain/duplicate_clusters.py`), the read endpoint (`GET …/duplicate-suggestions`), and this
dismissal store + its `POST`/`DELETE` endpoints. The review-list **frontend** is S4b. Decomposed and
resolved with the owner in Session 77 (`architecture/proposals/graph-cluster-dedup.md`, register
DM-CD-1..6); this ADR records the one decision (DM-CD-3) that crosses the data-storage boundary.

## Context

Graph-quality S4 re-points the §3.3 cascade matcher **inward**: it scores each already-accepted entity
against the others (a self-join) and surfaces likely-duplicate pairs the author would otherwise hunt
for by eye. It **suggests, never auto-merges** (INV-1/INV-9): the human commits each merge through the
*existing* merge endpoint.

The suggestions themselves are a **derived view** — recomputed on open from the accepted graph, cheap
at PoC scale, nothing to store. But a **dismissed** pair ("no — these two `Bronek`s are genuinely
different") reappears every time the list opens unless the "no" is recorded. The project already set
the precedent that remembering a human's rejection is a feature: `candidate_decisions` persists rejected
candidates. So the one storage question S4 raises is DM-CD-3: **does a dismissal persist, and where?**

This is the slice's only decision that adds durable state and fills the [[state-machine|Evidence]]
station — hence an ADR.

## Decision

1. **Persist dismissals only, in a new staging-side Postgres pair store (DM-CD-3 → B).** A dismissed
   pair writes one row to a new `duplicate_suggestion_dismissals` table; the suggestion read consults it
   to suppress re-suggestion. **Suggestions stay computed-on-open** — only the *dismissals* are stored.
   *Rejected:* **(A) ephemeral** — recompute each open with no memory, so a dismissed pair recurs
   (annoying, and breaks the DM-rej precedent); **(C) materialize the whole queue** as a `candidates`-like
   table — heavier, and buys nothing when the compute is already cheap (an accepted pair needs no memory
   either: the merge removes one entity, so the pair cannot recur).

2. **A deterministic `uuid5` primary key over the project + the *sorted* entity pair — the repo's
   idempotency idiom.** `dismissal_pair_id(project_id, a, b) = uuid5(ns, "{project}|{lo}|{hi}")` with the
   pair canonicalized to `(lo, hi)` by `domain.duplicate_clusters.canonical_pair` (the single source of
   pair ordering, shared by the id **and** the stored `entity_id_lo/hi` columns so they cannot drift).
   This makes an unordered `{a, b}` one identity, so `INSERT … ON CONFLICT (id) DO NOTHING` is idempotent
   and the read suppresses by recomputing the same id (the same `uuid5`-PK move as `staged_relations.id`).
   *Rejected:* a DB-side `UNIQUE (project_id, LEAST(a,b), GREATEST(a,b))` — it would introduce the repo's
   first `UNIQUE`/generated-column pattern; the `uuid5` idiom already in use is simpler and consistent.

3. **Staging-side — INV-9 holds; no new graph writer (DM-CD-6).** The table is Postgres-only; the two
   entity ids and `project_id` reference Neo4j nodes and so carry **no Postgres FK** (the OQ-1
   cross-store seam), matching `candidates`. The self-join read writes nothing. The merge is the
   *existing* endpoint, reused unchanged. So S4 adds **no** graph-writing symbol — the dismissal store is
   the *staging* side of the line INV-9 draws (like on-accept re-match / the S3c mention mutators).

4. **Reversible; none-at-PoC retention.** A dismissal is un-doable: `DELETE …/duplicate-suggestions/dismiss`
   removes the row (un-dismiss), so a mistaken "no" is not a one-way door. Retention is **none at PoC**
   (OQ-4) — the same posture as the other staging tables; documented, not solved.

## Consequences

- **The suggestion read is `self-join − dismissals`** — a small negative-overlay, the entity-pair twin
  of ADR 0008's `search ∪ manual − suppressions`. The read stays cheap (compute-on-open); only the human's
  "no" is durable.
- **INV-9's grep set is unchanged — no new Neo4j-writing symbol.** The dismissal store writes Postgres
  only; the merge is reused. A reviewer who reads "S4 adds a write" should check *what store*: staging
  (the dismissal) → fine; graph → there is none. Folded into `architecture/invariants.md` as another
  graph-vs-staging witness, not a new graph-writer instance.
- **A dismissal keyed to an entity dangles if that entity is later merged/deleted.** Harmless (it
  suppresses a pair that can no longer be suggested, since one side is gone) but inert data — the same
  none-at-PoC posture as ADR 0008's dangling suppressions (OQ-4). A V1 cleanup refinement, recorded not
  solved.
- **Type never enters the store or the qualification (INV-4).** The self-join uses type only as a soft
  ranking nudge (never a filter); the store records only the pair. Two duplicates the over-extractor
  typed differently are still suggested — the very case S4 exists to catch.
- **O(n²) self-join, named not hidden.** Trivial at Oakhaven scale (~186 nodes); [[blocking]] (LSH /
  candidate blocks) is the named revisit-lever for a future multi-thousand-node graph — a Layer-9 note,
  not built.
- **No spec amendment.** `docs/specs/graph-quality.md` §3 S4 already scopes "suggest duplicate clusters …
  the human commits via the existing merge"; the dismissal store is staging-side plumbing under that
  scope, not a capability change (confirmed by reading §3 S4 at build).
