# ADR 0011 — A stable surrogate handle for edges, and atomic server-side edge re-key

**Status:** Accepted
**Date:** 2026-07-10
**Related spec section:** `docs/specs/graph-quality.md` §3 S5 (the graph as an in-place editing
surface) + §4 (the reserved edge handle); §8 (invariants carried in: INV-1/INV-9 human gate, INV-3
reversible, INV-4 open-world). Main spec §3.4 (manual graph correction), §6.4 (the Neo4j edge model).
**Builds on:** ADR 0005 (relation edges written under the human gate — the content-addressed
`relation_edge_id = uuid5(subject, predicate, object)` established there), ADR 0006 (committed graph
edited under human-reached handlers — INV-9's grep guard), ADR 0007 (grouped, reversible `graph_edits`
operations — the before-image + undo machinery this re-key reuses).
**Scope note:** landed with **graph-quality S5b-be (backend)** — the `edge_uid` handle + the atomic
edit-predicate / re-target op + the endpoint. The canvas edge affordances are **S5b-fe**. Decomposed
and resolved with the owner in Session 80 (`architecture/proposals/graph-canvas-editing.md`, register
DM-S5-1..6); this ADR records the two decisions (DM-S5-2, DM-S5-3) that cross the data-model identity
boundary. It is the standing ADR obligation §4 reserved back at S0 (DM-GQ-1), drafted now — at the
first slice that consumes the handle — on the owner's confirmation, not before.

## Context

A Story Forge relation edge is **content-addressed**: `relation_edge_id = uuid5(subject_id, predicate,
object_id)` (`domain/candidates.py`). That is a deliberate and load-bearing choice (ADR 0005): the same
fact stated in two paragraphs MERGE-dedups to one edge, and a retried human-gated commit never doubles
an edge. The cost is the flip side of the same coin: **the id *is* the content, so it changes the moment
any of subject / predicate / object changes.** Re-predicating an edge (`PASSENGER_ON` → `ON_SHIP`) or
re-targeting an endpoint yields a *different* edge id — identity-wise a new edge.

Until now that was invisible, because there was no in-place edge edit: `add_relation` and
`delete_relation` exist atomically, but "edit a predicate" was faked client-side as *remove-old +
add-new* — two independent calls, two `graph_edits` rows, a brief window where the edge does not exist.
Graph-quality S5 makes edge editing a first-class canvas action, and S6 (graph-wide predicate rename)
will re-key edges *in bulk*. So two problems become real at once:

1. **Nothing durable can ride on an edge.** A future relation qualifier / [[reification]] (a property, a
   confidence, a provenance note attached to *this specific edge*) would be severed by an ordinary
   re-predicate, because the edge it was attached to no longer exists under that id. Spec §4 foresaw this
   and **reserved** a fix — a stable handle — without building it.
2. **A client-side remove+add cannot own that handle.** Two independent calls mint two identities; the
   old handle is dropped on the floor. Handle preservation has to be a *server* guarantee, or it is no
   guarantee at all.

This ADR crosses the **data-model identity boundary** (it adds a second key to every edge and defines
how it survives mutation), so per the ADR form-escalation rule it carries decision drivers + per-option
trade-offs, not just the lean form.

**Decision drivers.** (a) A durable edge identity that survives curation — the whole point of §4. (b)
Keep the content-addressed dedup/idempotency of ADR 0005 intact — the handle must be *additive*, not a
replacement. (c) No premature machinery — nothing reads the handle yet (YAGNI). (d) Preserve INV-1
(human gate), INV-3 (reversible), INV-9 (only human-reached handlers write the graph). (e) A re-key must
be atomic and reversible as one unit.

## Decision

1. **Add an opaque `edge_uid` (a `uuid4`) alongside the content id — a surrogate key, not a replacement
   (DM-S5-3).** The content `id` stays the MERGE / dedup key exactly as ADR 0005 defined; `edge_uid` is a
   second, *stable* identity stored as a Neo4j edge property and carried on the `GraphRelation` domain
   model (nullable). The two coexist: `id` answers "is this the same fact?"; `edge_uid` answers "is this
   the same edge across edits?"
   *Rejected:* **making the id itself stable** (e.g. a `uuid4` primary id, content as a lookup) — it would
   discard ADR 0005's free MERGE-dedup + retry-idempotency, a much larger blast radius than the problem
   warrants.

2. **Mint forward on every edge write; never back-fill (DM-S5-3, mint scope → a).** Every writer that
   *creates* an edge stamps a fresh `edge_uid`: the human-gated relation-decide commit
   (`RelationReviewService`), the manual `add_relation`, and the new re-key. A legacy edge written before
   this ADR has **no** handle and is **not** back-filled — it gets one lazily if it is ever re-keyed, or
   never (nothing reads the handle yet, so universal coverage buys nothing today).
   *Rejected:* **a one-shot back-fill migration** stamping every existing edge now — a migration for an
   attribute with zero consumers; a future reification pass can back-fill if it ever needs universal
   coverage. **Keeping it a recorded constraint** with no enforcer — S5b *builds* the enforcer, so the
   constraint graduates to a real invariant (INV-10) rather than staying a wish.

3. **Coalesce on MERGE via `ON CREATE SET` only — never `ON MATCH` (DM-S5-3).** `create_relation` keeps
   its `MERGE (…) ON CREATE SET r = $props` with **no** `ON MATCH` clause. This *is* the coalesce rule: a
   MERGE that matches an existing edge sets nothing, so a duplicate / retried write carrying a fresh
   handle **never overwrites** the edge's existing `edge_uid`. Verified by an integration test that writes
   the same edge twice with different handles and asserts the first survives.
   *Rejected:* an explicit `ON MATCH SET r.edge_uid = coalesce(r.edge_uid, $new)` — it would opportunistically
   stamp legacy edges on any duplicate write (a creeping back-fill, contra decision 2) and is redundant:
   ON-CREATE-only already gives exactly the coalesce we want.

4. **A re-key is an atomic server-side op preserving the handle, recorded as one reversible operation
   (DM-S5-2).** `EntityEditService.retarget_relation` (behind `PATCH …/relations/{edge_id}`) does
   delete-old + create-new **server-side**, carrying the old edge's `edge_uid` (or a freshly-minted one
   for a legacy edge) onto the new edge, and records it as one grouped `graph_edits` operation — reusing
   the merge writer's per-edge op strings (`repoint_relation` / `fold_relation`), so the existing undo
   inverter reverses it with no new arm. The pure re-key plan lives in `domain/relation_rekey.py`,
   mirroring `plan_merge`'s re-point.
   *Rejected:* **the client-side remove+add compose** (DM-S5-2 → A) — it splits one edit into two undo
   steps, opens a partial-failure window where the edge briefly does not exist, and structurally cannot
   preserve the handle (two independent calls, two identities).

5. **On a fold, the survivor keeps its own handle (DM-S5-3, survivor rule).** A re-key whose new id
   already exists (a MERGE-collision) **folds** onto that edge; the surviving edge keeps its own
   `edge_uid` (the ON-CREATE coalesce drops the incoming one), and the folded edge's handle rides the
   before-image so undo un-folds it. Identical to the merge re-point fold semantics.

These make **INV-10** ("an edge's `edge_uid` survives re-point / re-predicate / merge") a real,
enforced contract as of this slice — its enforcer and tests exist now (`architecture/invariants.md`).

## Consequences

- **Every edge now carries two identities.** The content `id` (dedup / MERGE key, ADR 0005) and the
  surrogate `edge_uid` (stable handle). A reviewer must not conflate them: the cytoscape element id and
  the `staged_relations.edge_id` provenance link are the *content* id and still re-key on an edit — the
  handle does **not** rescue a stale canvas click or the provenance link (below). The handle is
  forward-compat plumbing for a *future* consumer, not a fix for staleness.
- **A re-key severs the edge↔`staged_relations` provenance link.** The S3b evidence read keys on the
  *content* `edge_id`; after a re-key the `staged_relations` rows written with the old id no longer match
  the new edge, so its evidence read returns 200 + empty ("added manually"). This is consistent with
  S3b's already-documented behaviour for manually-added edges and is **not** fixed here — migrating
  provenance across a re-key is out of this slice's scope (recorded, not solved; the handle is a Neo4j
  concern, `staged_relations` is unchanged — no migration).
- **No database migration.** `edge_uid` lives on the Neo4j edge, the `GraphRelation` model, and the
  `graph_edits` before-image (schemaless jsonb). Postgres `staged_relations` (content-`edge_id`-keyed) is
  untouched.
- **INV-9's grep set is unchanged.** The re-key reuses `create_relation` / `delete_relation` — no new
  graph-writing symbol. It is the *seventh* witnessed instance under INV-9: the enumeration grows by a
  *path* (the new `PATCH` handler), not a writer class, exactly as merge / undo / tag-new-entity did. See
  `architecture/invariants.md` INV-9.
- **Legacy edges stay handle-less until curated.** "Why doesn't this old edge have a handle?" is an
  answered question, not a surprise: mint-forward, no back-fill. A re-key mints one on the new edge; a
  never-touched legacy edge simply never needs one until a consumer appears.
- **A re-key is best-effort-reversible, last-write-wins at PoC.** Like `add_relation` / `remove_relation`,
  a relation-only op carries no entity drift guard; the only post-completion crash window is a missing
  audit row (the edit landed, unlogged) — the accepted DM-S3a-6 / DM-S5-6 posture for one local author.
- **No spec amendment.** `docs/specs/graph-quality.md` §3 S5 already scopes edit-predicate / re-target /
  delete, and §4 already reserved the handle (confirmed by reading §3 S5 + §4 at build). This ADR records
  *how* the reserved handle is built, under that scope.
