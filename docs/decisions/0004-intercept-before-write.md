# ADR 0004 — Intercept-before-write: the cascade stages, the human commits

**Status:** Accepted
**Date:** 2026-06-15
**Related spec section:** §3.3 (the four-stage cascade), §7 steps 6–7 (cascade runs in the pipeline;
human review writes Neo4j), §4.2 (`edit_history`), §11 (reversibility / privacy)
**Supersedes:** the temporary INV-8 "no dedupe — every candidate is a fresh `CREATE`" contract (M2).

## Context

Through Milestone 2 extraction wrote **every** candidate straight to Neo4j with `CREATE` (the
deliberately temporary INV-8 contract), so the graph accumulated duplicates that M3's §3.3 cascade
was meant to resolve. M3 builds that cascade (RapidFuzz → embedding cosine → LLM judge → human
review). The milestone-defining decision (DM6, owner 2026-06-11) was **how** the cascade relates to
the write: dedupe a dirty graph *after* the fact, or **gate the write** so duplicates never land.

This ADR records the intercept-before-write design and the costs accepted with it. It was produced
through a meta-architect dogfood pass — `decompose-requirement` →
`architecture/proposals/m3s4a-intercept-write-path.md` (register DM-S4a-1..5) +
`architecture/state-machines/candidate-lifecycle.md` — whose options the owner resolved in
`docs/PLAN_SHORT.md` Decided 2026-06-15 (S23). It is implemented in M3.S4a (this PR).

## Decision

1. **Intercept-before-write (DM6 = option A).** Extraction *stages* each candidate into a new Postgres
   `candidates` table carrying the cascade's proposal (NEW vs a MERGE `target_entity_id`, the stage
   reached, confidence, the judge's reasoning, and the top-3 alternatives). **Nothing is written to
   Neo4j** until a human accepts at the review queue. This makes INV-1 (human-in-the-loop) enforceable
   in code and lands **INV-9** ("no automated stage writes the graph") — the coordinator is constructed
   with no graph writer at all; the single writer is `CandidateReviewService`. INV-8 is retired.

2. **The cascade runs synchronously in the ingest pipeline** (§7 step 6), per paragraph, against the
   already-**accepted** graph (read once per run — `AcceptedSnapshot`). Fail-closed throughout: an
   embedding/judge failure routes the candidate toward the human as NEW/"uncertain", never auto-merges,
   never crashes the batch; a store-connectivity blip surfaces as **503**, never a silent NEW.

3. **A focused, append-only `candidate_decisions` evidence table now (DM-S4a-4)** — *not* the §4.2
   `edit_history`. An entity accept/merge/reject is a *graph* decision; §4.2's `edit_history` is the
   *text-edit* dataset (different columns, different export, §10 q7) and genuinely belongs to the
   editing milestone. Building it now would front-load a text-shaped schema onto a graph decision.
   The two names are deliberately distinct so the future `edit_history` does not collide.

4. **Resume checkpoint moves to a `paragraph_processed` marker (DM-S4a-3).** A paragraph is "done" when
   its candidates are staged; a zero-candidate paragraph still writes a marker (fixing M2's reprocess
   wart). Mentions move to accept-time, written against the now-committed entity with the candidate's
   context vector copied onto them.

5. **The accept path is idempotent and status-flip-last.** Order: Neo4j → `entity_mention`(+vector) →
   `candidate_decisions` → flip `candidates.status`. Accept-path ids (entity, mention, decision) are
   derived deterministically from the candidate id and the writes are MERGE-on-id / `ON CONFLICT DO
   NOTHING`, so a crash before the flip is safely retryable with no duplicate node/mention/evidence.
   The merge target is re-validated on accept (TOCTOU → 409 if it vanished).

6. **No retention policy at PoC (DM-S4a-5).** Rejected candidates are kept on purpose (the matcher
   consults them — DM-rej); unreviewed backlog is the only growth risk and is bounded by how much the
   single author ingests. An age-based cleanup is the obvious V1 refinement.

## Consequences

- **The graph is empty until the author reviews.** Accepted cost: extraction now produces a *review
  queue*, not a populated graph; `GET /graph` shows only what a human has committed. This is the point
  (§9 M3: "I control every decision, the graph is clean"), but it is a visible behaviour change from M2.

- **Stage-3 egress is ungated (INV-2 deferred past M3).** The judge fires a cloud call at extraction
  time with **no consent prompt** (DM7, owner 2026-06-15 — see `architecture/invariants.md` INV-2). It
  stays observable via the `llm_calls` ledger (INV-5) and is persona-justified (single local user, full
  trust). Named here as an accepted cost, not an oversight.

- **Relations are staged but not written in S4a.** A relation can be committed only once *both*
  endpoints are accepted (which entity each resolves to is a post-review fact), so S4a persists the raw
  relation proposals (JSONB on `paragraph_processed`) and defers the relation write + re-point-on-merge
  to S4b. The extract path stops writing relations until then; the data is preserved (no LLM re-run).

- **`canonical_name_pl/en` peering (§10 q8) becomes concrete at accept-create.** S4a reuses the M2
  provisional rule (surface form → project-language slot, peer null) and does **not** invent a peering
  rule — §10 q8 stays the spec's open question, surfaced here as deferred.

- **The cascade is store-chattier** (per-run accepted-graph read + per-paragraph staging write). Read
  once per run mitigates it; observable via the §8.5 panel. Single-user-local, so no new alerting.

## Alternatives considered

- **Dedupe-after-write (DM6 option B):** let extraction write, then a background merge pass cleans
  duplicates. Rejected: it makes the graph transiently untrustworthy (the thing INV-1 protects) and
  needs reliable un-merge; gating the write is simpler and stronger.
- **Build §4.2 `edit_history` now (DM-S4a-4 option a):** one audit home, but forces a text-edit schema
  onto a graph decision and front-loads a table the editing feature owns. Deferred.
- **Status-on-`candidates` only, no evidence table (option c):** lightest, but a single mutable status
  row is weak evidence for an "always reversible" invariant (no immutable before-state). Rejected.
