# ADR 0006 — Committed graph state is edited under explicit human-reached handlers (INV-9 broadened)

**Status:** Accepted
**Date:** 2026-06-19
**Related spec section:** §3.4 ("properties editable", "relations editable"), §3.5 (manual correction
in the reader), §3.2 (open-world `properties` / extensible `type`, INV-4), §11 (reversibility)
**Builds on:** ADR 0004 (intercept-before-write) + ADR 0005 (relation edges under a human gate) — this
is the *post-commit edit* counterpart, and reuses ADR 0005's broaden-don't-mint move on INV-9.

## Context

ADR 0004/0005 made the cascade *stage* proposals and the human *commit* them: `CandidateReviewService`
writes nodes and `RelationReviewService` commits staged edges, and INV-9 read **"the graph is written
by exactly two human-decision code paths."** Both are *staging→commit gates* keyed on Postgres rows
(`candidates` / `staged_relations`).

M4.S3a is the first slice that **edits already-committed graph state** (spec §3.4/§3.5 manual
correction): change an accepted entity's `canonical_name`/`aliases`/`type`/`properties`, and add/
remove relations between accepted entities. There is no staged row for an already-committed node/edge,
so this is a *new* kind of write. The question this ADR records: where does that write land, and what
does it do to INV-9's "exactly two writers"?

Produced through a meta-architect dogfood pass — `decompose-requirement` →
`architecture/proposals/m4-entity-editing.md` (register DM-S3a-1..8) — resolved with the owner on
2026-06-19, with one entry (DM-S3a-3) resolved at build (see Decision 2).

## Decision

1. **New, explicitly-named edit handlers; reword INV-9 (DM-S3a-1).** Edits land in a new
   `EntityEditService` reached only from explicit edit endpoints (`PATCH /stories/{id}/entities/{eid}`,
   `POST`/`DELETE /stories/{id}/relations`) — the [[backend-for-frontend]] *write* counterpart to the
   M4.S2a read endpoint. INV-9's writer-set grows from two to three, all human-reached, so INV-9 is
   **reworded "exactly two writers" → "only human-reached handlers — accept, decide, edit"**. *This
   broadens an existing invariant rather than minting a near-duplicate INV-10* — the **same
   broaden-don't-mint move ADR 0005 made** (INV-1 to edges). The guarded property is unchanged: no
   *automated* stage writes the graph; every writer is reachable only from a human action. *Rejected:*
   reusing the review services (conflates the stage→commit gate with a post-commit edit, and hides a
   graph-writer inside a service named "review").

2. **Manual relation add/remove write Neo4j directly (DM-S3a-3, resolved at build).** The register's
   first preference was to keep `RelationReviewService` the *sole* edge-writer by routing a manual add
   through its `decide` path. A build-time check falsified that: `decide` resolves an edge's endpoints
   by **surface-name within a single paragraph** (`_resolve` keys on `(paragraph_id, normalized_name)`),
   which a hand-picked edge between two arbitrary accepted entities has neither of. Synthesising a fake
   `staged_relations` row would require fabricating a paragraph and names that round-trip to the chosen
   ids — fragile and dishonest. So the owner approved the register's **pre-authorized fallback: a direct
   edge-writer** in `EntityEditService` (`create_relation` reused for add, a new `delete_relation` for
   remove). The edge-writer set therefore grows too — covered by the same INV-9 rewording. Re-predicate
   = delete-old + add-new (the edge id is `uuid5` of the resolved triple, so a new predicate is a new
   edge); a duplicate add MERGEs onto the existing edge and is **surfaced** (`merged_into_existing`)
   rather than erroring; a manual **self-loop** is **allowed** (intentional, unlike the extraction
   path's dropped merge artifacts).

3. **A before→after `graph_edits` log satisfies INV-3 (DM-S3a-2).** Every edit records an append-only
   `(target_id, target_kind, op, before, after)` row — the graph-edit twin of `candidate_decisions`,
   and the substrate for undo + the correction-as-training-data flywheel. One table covers both
   node-field edits and edge add/remove (`target_kind` discriminates). Write order mirrors the accept/
   decide services: **graph mutation first, evidence row last**; a retry of the same edit re-reads the
   now-updated state, diffs empty, and is a clean no-op (nothing double-applied).

4. **Open-world `properties` stays open; typed values; last-write-wins (DM-S3a-5/6).** `properties`
   editing keeps free keys (INV-4 — never a fixed enum) and preserves JSON value types; a non-object
   `properties` is rejected at the request boundary (422). Concurrency is **last-write-wins** at PoC
   (one local author; the [[lost-update]] anomaly named and accepted) — optimistic concurrency is a V1
   refinement.

## Consequences

- **§3.4/§3.5 manual correction is now real for the backend:** an accepted entity's fields and its
  relations are editable under a human handler, with a reversible audit trail (INV-3).
- **A corrected name/alias re-highlights for free (DM-S3a-4).** Because reader highlighting is
  *render-time search* over name+aliases (DM-IH-1, no stored spans), a renamed entity re-highlights once
  the reader catalog refetches — no span migration. Flip side: a name absent from the prose stops
  highlighting (correct; aliases are the lever to restore coverage).
- **Two direct graph-writers per store now exist** (accept + edit for nodes; decide + edit for edges).
  The INV-9 grep guard widens accordingly: `create_entity` / `add_alias` / `create_relation` /
  `update_entity` / `delete_relation` must each be reachable only from a human-reached handler.
- **Undo is enabled, not yet shipped.** S3a-be *records* the before-image; a built undo endpoint/UI is
  a later slice (undo-merge lands in S3b) — consistent with `candidate_decisions` recording evidence
  without a shipped "un-accept".
- **Edit-vs-edit / edit-vs-stale-read race accepted at PoC** (LWW). The sharper edit-vs-*delete* race
  arrives with S3b/S3c (whole-entity delete + merge).

## Alternatives considered

- **Reuse/extend the review services for edits (DM-S3a-1 option b):** no new service, but overloads a
  stage→commit gate (there is no staged row for a committed node) and hides a graph-writer behind a
  "review" name. Rejected.
- **Route manual edges through the decide path to keep one edge-writer (DM-S3a-3 option a):** the
  cleanest INV-9 story for edges *in principle*, but it doesn't compose (surface+paragraph-keyed
  resolution vs an id-keyed manual edge). Rejected at build for the direct edge-writer.
- **No before-image / "undo = re-edit" (DM-S3a-2 option b):** cheapest, but loses the prior value — an
  INV-3 gap. Rejected; the minimal before→after log is the honest INV-3 satisfaction.
- **String-only `properties` values / raw-JSON textarea (DM-S3a-5 alts):** lose JSON typing, or invite
  malformed input. Rejected for typed key/value with boundary validation.
- **Optimistic concurrency now (DM-S3a-6 option b):** ceremony for one local author. Deferred to V1.
