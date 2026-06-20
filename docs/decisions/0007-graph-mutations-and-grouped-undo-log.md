# ADR 0007 — Entity merge/delete/undo are grouped, reversible operations under the human gate

**Status:** Accepted
**Date:** 2026-06-20
**Related spec section:** §3.4 (merge + delete in the detail panel, amended 2026-06-20), §3.5 (manual
correction in the reader), §10 q2 (graph versioning/rollback — resolved as "append-only log of
changes, executed"), §11 / §4.3 (reversibility / deterministic undo stack), §3.2 (open-world
`properties` / `type`, INV-4)
**Builds on:** ADR 0004 (intercept-before-write) + ADR 0005 (relation edges under a human gate) +
ADR 0006 (edit committed graph under human-reached handlers) — this is the *destructive, multi-write*
counterpart, and reuses ADR 0005/0006's **broaden-don't-mint** move on INV-9.
**Scope note:** this ADR is landed with **M4.S3b-be1 (merge)**. Whole-entity **delete** and the
**undo executor** are **M4.S3b-be2**; the schema, the grouped-log contract, and the invariant
framing below are written once here for the whole S3b slice, but only *merge* writes grouped rows in
be1 (the log is the substrate be2 consumes).

## Context

ADR 0006 made committed graph state *editable* under a third human-reached writer
(`EntityEditService`), recording each change as a per-row `graph_edits` before→after image. Those
edits are **one action = one write** (a field change, an edge add/remove), so a per-row log suffices.

M4.S3b is the first slice whose operations are **one author action = many writes across both
stores**, and the first to **re-point already-committed identity**:

- **merge B into A** — fold B's aliases/properties into A (author-resolved property conflicts);
  re-point every edge incident to B onto A; re-point B's `entity_mentions` rows; `DETACH DELETE` B.
- **delete B** (be2) — `DETACH DELETE` the node + delete its mentions, from a full snapshot.
- **undo** (be2) — reverse the last operation, newest-first.

Because `relation_edge_id = uuid5(subject, predicate, object)` is *content-addressed*, re-pointing an
endpoint **changes the edge id** → re-point is delete-old + create-new, with MERGE-collision folding.
And because §11 demands reversibility, undo must replay the inverse of a *compound* operation — which
the per-row, ungrouped S3a log cannot express.

Produced through a meta-architect dogfood pass — `decompose-requirement` →
`architecture/proposals/m4-s3b-graph-mutations.md` (register DM-S3b-1..8) — resolved with the owner on
2026-06-20, with the spec amended first (§3.4 merge+delete, §10 q2 undo) via the stop-and-amend flow.

## Decision

1. **Merge/delete/undo land in the existing `EntityEditService`; INV-9 enumeration is unchanged
   (DM-S3b-7).** They are new *operations* on the existing human-reached "edit" handler, not a new
   writer class — so INV-9 ("only human-reached handlers — accept, decide, edit") already covers
   them. The grep guard **widens** to include `delete_entity` (and the Postgres mention
   re-point/delete) alongside the ADR 0006 set. No automated stage performs a merge/delete/undo.

2. **Undo is general, via a grouped append-only log = a compensating transaction (DM-S3b-1; resolves
   §10 q2).** `graph_edits` gains `operation_id` + `seq` (the rows of one action share an id and an
   order), `op_kind` (`merge`/`delete`/`undo`), `description` (a human-readable label), and
   `undone_at` (the `applied → undone` state). Any edit/merge/delete is reversible newest-first; undo
   pops the latest not-yet-undone operation and applies each row's inverse in reverse `seq`. This is
   the spec's own §10 q2 answer ("append-only log of changes"), *executed* — **not** snapshots-per-
   story or full versioning (recorded as the post-PoC V1 path). *Rejected:* undo-merge-only
   (inconsistent INV-3); full version history (post-PoC).

3. **Undo previews what it reverses (DM-S3b-1, owner-added).** Each operation carries a human-readable
   `description` ("merged *Broniek* into *Bronisław*"); the undo affordance shows it and **confirms**
   before acting — never a blind pop. (be2 builds the executor + preview; be1 writes the
   `description`.)

4. **Merge consolidation: author picks the survivor and resolves property conflicts by hand
   (DM-S3b-2; §3.4 amended).** B's `canonical_name` + aliases union into A as aliases. Non-conflicting
   property keys union automatically; where both set a key differently, the backend **detects the
   conflict** and the merge commits only with the author's chosen value (a missing one → 400). Nothing
   is silently overwritten. *Rejected:* survivor-wins-on-conflict (less control — the owner chose more).

5. **Edge re-point is delete-old + create-new, collisions folded-and-reported, post-merge self-loops
   dropped (DM-S3b-3; DM-Rel-5/6 executed).** A re-pointed edge whose new id already exists on A
   MERGE-collapses — the count is **reported** (`folded_count`), not silently lost. A B↔A or B↔B edge
   becomes an A↔A self-loop and is dropped as an artifact (consistent with the extraction path).

6. **Real `DETACH DELETE`, not soft-delete (DM-S3b-5; §3.4 amended).** Merge deletes B; whole-entity
   delete (be2) removes the node + its mentions. Undo restores from a full before-image snapshot.
   *Rejected:* a `deleted` tombstone flag — it would force every read path (reader, graph, panel,
   search, cascade) to learn to filter; the append-only-log undo already carries the snapshot.

7. **Write order keeps B alive until the last graph write; deterministic ids for idempotent retry
   (DM-S3b-4, refined at build).** The two stores cannot share a transaction (OQ-1), so the order is
   chosen to leave a **retryable** state, never a half-merge: fold A + re-point edges → re-point B's
   mentions → **delete B last** → evidence. Moving the mentions *before* deleting B means a mention
   never references an already-gone node, and a crash anywhere up to the delete is cleanly retryable
   (the retry re-reads B — still present — sees the edges + mentions already moved as no-ops, and
   finishes). The operation + row ids are `uuid5` of the (absorbed, survivor) pair, so a retried merge
   re-derives the same ids and `ON CONFLICT (id) DO NOTHING` never doubles the evidence; the
   before-image is captured in memory before the writes. **Accepted window:** a crash *after* the B
   delete but *before* the evidence write strands a **completed** merge whose audit row was not
   written — the same last-write-wins posture as ADR 0006 / DM-S3a-6, accepted for one local author at
   PoC. *(Build note: the resolved register said "Neo4j-then-Postgres-then-evidence"; the build defers
   the B-delete to last — still serving DM-S3b-4's retryable-not-half-merge intent — because deleting B
   first opened a window where its mentions were orphaned and the retry could not recover.)*

## Consequences

- **§3.4 merge + delete are real for the backend (be1: merge):** an accepted entity absorbs another
  under a human handler, re-pointing its edges and mentions, with a grouped reversible trail (INV-3).
- **INV-3 moves from *substrate* to *executed* — but only in be2.** be1 *writes* the grouped log;
  be2's undo *consumes* it. The honest risk INV-3 now guards is **before-image completeness**: a merge
  re-points N edges + M mentions, so the snapshot must capture all of them or undo would restore a
  stale graph (a non-reversible action masquerading as reversible). The mention re-point therefore
  returns the moved row ids, recorded in the before-image, so undo moves back *exactly* those rows.
- **The INV-9 grep guard widens** to `create_entity` / `add_alias` / `create_relation` /
  `update_entity` / `delete_relation` / **`delete_entity`** + the mention re-point/delete SQL — each
  reachable only from a human-reached handler. The edge-writer set is still the same two services.
- **`graph_edits` gained a `project_id` column** (build refinement, not in the resolved register): the
  undo stack is scoped per project, so "undo last" reads the latest live operation *in this project*.
- **Two build refinements recorded:** `project_id` on the log (above), and the mention re-point
  returning the moved ids (above) — both surfaced by the build design pass, both serving undo
  completeness.
- **`graph_edits` retention is unbounded at PoC (DM-S3b-7, Expiry):** the same none-at-PoC posture as
  `candidate_decisions` / `staged_relations`; an undo depth cap is the noted V1 refinement.
- **Edit-vs-delete race accepted at PoC (LWW).** Undo of an operation whose state has since drifted is
  refused by be2's drift check (a [[lost-update]] in reverse); the executor + its drift mechanism land
  in be2.
- **be2 must handle re-merging the same pair after an undo (deterministic-id collision).** Because the
  merge `operation_id`/row ids are `uuid5(merge:B:A)` — keyed only on the pair, for crash-retry
  idempotency — a *second, genuinely-new* merge of the same B→A (only possible once be2's undo has
  recreated B) would re-derive the **same** row ids and be silently dropped by `ON CONFLICT (id) DO
  NOTHING`, losing the new operation's evidence. This cannot occur in be1 (no undo → B stays deleted →
  the pair can't be re-merged). be2's undo must therefore either **delete** an undone operation's
  `graph_edits` rows (not just stamp `undone_at`) or fold a generation/nonce into the id derivation.
  Recorded here so the be2 build treats it as a known design point, not a surprise.

## Alternatives considered

- **Undo-merge only (DM-S3b-1 option a):** narrowest, but leaves edits/deletes permanent — an
  inconsistent INV-3. Rejected for the uniform grouped log.
- **Full graph versioning / snapshots-per-story (DM-S3b-1 option c):** the heavier §10 q2 options;
  real but far past PoC. Recorded as the V1 path.
- **Survivor-wins on property conflict (DM-S3b-2 option i):** fewer clicks, but the owner chose
  by-hand resolution for control. Rejected.
- **Soft-delete / tombstone (DM-S3b-5 option b):** a cleaner trash/restore UX, but threads a read
  filter through every screen. Rejected for hard delete + snapshot undo.
- **Evidence-first "pending" operation (write order):** fully crash-safe audit, but violates the
  evidence-last order shared with accept/decide/edit. Rejected for evidence-last + the accepted narrow
  crash-without-audit window.
- **A dedicated `operations` header table (grouping shape):** referential cleanliness, but a second
  write per operation and a join per read — over-engineered for one local author. Rejected for nullable
  grouping columns on `graph_edits` (a NULL `operation_id` row is its own singleton operation).
