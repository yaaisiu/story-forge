# ADR 0005 — Relation edges are written under an explicit human gate

**Status:** Accepted
**Date:** 2026-06-16
**Related spec section:** §3.3 Stage 4 (the 5th human action, *"decide on relations (which entities
it links to and how)"*), §3.2 (entity/relation data model), §9 M3 ("the graph is clean"), §11 (reversibility)
**Builds on:** ADR 0004 (intercept-before-write) — this is its natural completion for *edges*.

## Context

ADR 0004 made the cascade *stage* candidates and the human *commit* nodes (INV-1 + INV-9). It
explicitly deferred **relations**: a relation can be written only once *both* its endpoints are
accepted entities, so S4a staged the raw relation proposals (as JSONB on `paragraph_processed`) and
wrote no edge. The result through S4d: a graph with correct, human-gated **nodes** but **zero
edges** — `Neo4jRepo.create_relation` existed with no callers. §9 M3's "the graph is clean" was true
for entities and unmet for relations.

This ADR records how M3.S4e closes that gap. It was produced through a meta-architect dogfood pass —
`decompose-requirement` → `architecture/proposals/m3-relation-write.md` (register DM-Rel-1..7) — whose
central decision the owner resolved on 2026-06-16, with the remaining register entries confirmed at
build (the S4a pattern). The key reframe the decompose surfaced: under intercept-before-write the
feared "re-point edges on a merge" largely **dissolves** — endpoints are surface strings with no
entity id until accept, so an edge is written *lazily* by resolving each string to its candidate's
*committed* id, and is born already pointing at the merge survivor.

## Decision

1. **An explicit human gate for edges (DM-Rel-1 = option b).** A relation edge is written only on an
   explicit human `decide` action (the §3.3 5th action), **not** auto-written once both endpoints are
   accepted. *Why:* an auto-write would commit a hallucinated *predicate/direction* even when both
   nodes are right — the exact LLM error the human gate exists to catch. The *resolution* of endpoints
   stays fully deterministic, so the human's act is a thin confirm/prune, not data entry. This
   **broadens INV-1** to cover edges (rather than minting a near-duplicate INV-10) and gives INV-9 its
   second witnessed instance — `RelationReviewService` is now the sole edge writer, reached only from
   the human decide endpoint.

2. **Endpoint resolution is deterministic, same-paragraph, normalised-exact (DM-Rel-2).** A surface
   endpoint resolves to the **committed** entity id of the same-paragraph accepted candidate whose
   `candidate_name` matches it casefold+strip (`created` → the deterministic accept id; `merged` →
   the target id). The create-id derivation is promoted to one shared pure helper
   (`domain.candidates.committed_entity_id`) so the accept path and resolution cannot drift. An
   endpoint that matches no same-paragraph candidate, or whose paragraph has an ambiguous same-name
   pair, is **held**, never fuzzy-bound (DM-Rel-7).

3. **A `staged_relations` table gives relations a lifecycle (DM-Rel-4).** Mirroring `candidates`: a
   per-paragraph-occurrence row (deterministic id = `uuid5` of the surface triple in its paragraph) with
   `staged → written | rejected` status, the endpoint ids resolved at commit, and the committed
   `edge_id` — the audit home a relation commit needs (INV-3) that the entity-keyed
   `candidate_decisions` could not provide. Relations are staged here at extraction time (atomically
   with candidates, in the same `persist` transaction); the old `paragraph_processed.relations` JSONB
   is left vestigial (`DEFAULT '[]'`), a deferred drop.

4. **Idempotent MERGE-by-edge-id (DM-Rel-6).** `create_relation` changes from `CREATE` to
   `MATCH … MERGE (s)-[r:TYPE {id:$id}]->(o) ON CREATE SET r=$props`, with the edge id = `uuid5` of the
   **resolved** `(subject_id, predicate, object_id)` triple. So a retried decide writes no second edge,
   and the *same fact stated in two paragraphs collapses to one edge*. The commit re-resolves both
   endpoints (TOCTOU) and writes the edge before flipping the row status (status-last), so a crash
   before the flip re-commits cleanly.

## Consequences

- **§9 M3 is now literally true for relations:** the graph has human-gated nodes *and* edges. The
  edge write leaves only a human-reachable endpoint (INV-1/INV-9 shape preserved).

- **A heavier slice + a UI follow-on (the accepted cost of the gate).** The explicit gate needs a new
  endpoint set and a React relation-review surface (S4f), where an auto-write would have needed neither.
  The owner accepted this for the spec-faithful, graph-as-source-of-truth posture; the hybrid
  (auto-resolve / bulk-confirm) is kept as a fallback if the explicit gate proves heavy in practice.

- **Per-mention provenance is traded for a clean graph (owner-flagged follow-up).** Edge-id-from-triple
  means two paragraphs asserting the same fact MERGE to one edge — the graph stays clean (§9 M3) but
  the single edge can carry only one `source_paragraph_id`. The `staged_relations` rows *do* retain
  per-paragraph provenance, so the data isn't lost; **post-PoC we need a way to enumerate all
  occurrences of a relationship** from the graph side. Recorded as the accepted cost here and as a
  cross-cutting follow-up.

- **Held relations never expire (Expiry gap, none-at-PoC).** A relation whose endpoint is never accepted
  (or is rejected) stays `staged` forever — the same posture as DM-S4a-5's unreviewed backlog, now with a
  concrete second instance. A reject-prunes-held rule and an age-based cleanup are the obvious V1 refinements.

- **Re-point stays an M4 concern (DM-Rel-5).** M3 *writes* edges; re-pointing an already-written edge
  when two *already-accepted* entities are merged is the spec's "edit relations in UI" (M4), explicitly
  out of scope. When it lands it must re-point or `DETACH`-rewrite incident edges.

## Alternatives considered

- **Auto-write on both-endpoints-accepted (DM-Rel-1 option a):** lightest, no new UI — but commits a
  plausible-but-wrong predicate with no human in the loop on the *meaning* of the edge. Rejected.
- **Hybrid auto-resolve / bulk-confirm (option c):** keeps a human veto with one batch action. Kept as
  the fallback if the explicit per-edge gate proves heavy, not the build target.
- **Keep relations in the `paragraph_processed.relations` JSONB + a deterministic edge id for idempotency
  (DM-Rel-4 option b):** minimal, no migration — but JSONB cannot carry per-relation `held/written/rejected`
  status or a reversible audit row without rewriting the whole array on each decide. Rejected for the
  explicit-gate design.
- **Edge id from the staged-relation row id (DM-Rel-6 alt):** preserves a distinct edge per mention, but
  shows two parallel edges for what a reader sees as one fact — against §9 M3's clean graph. Rejected in
  favour of the triple-keyed id (with the provenance follow-up noted above).
