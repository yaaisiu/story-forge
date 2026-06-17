---
type: review
slug: 2026-06-17-architecture-review
updated: 2026-06-17
status: living
related: ["[[overview]]", "[[invariants]]", "[[open-questions]]", "[[candidate-lifecycle]]", "[[m3-relation-write]]", "[[m3s4c-intra-batch-rematch]]", "[[2026-06-15-architecture-review]]"]
---

# Architecture review — 2026-06-17 (M3→M4 roll re-sync)

**Scope.** Full vault sweep at the M3→M4 milestone boundary. Since the last snapshot
([[2026-06-15-architecture-review]], taken entering M3.S4) the cascade finished landing for
**entities** (S4b UI, S4c on-accept re-match, S4d manual handpick) and the whole **relation**
half shipped (S4e relation-write backend, S4f relation-review UI). **M3 is feature-complete.**
No `review-architecture` run has happened since edges + the relation lifecycle landed — the INDEX
was hand-refreshed at S29 but a full as-built diff is overdue. This is that diff, plus a forward
"but what if" over the relation-write path and M4.

**Headline.** No **blockers**. The one **risk** is a single badly-stale note: `overview.md`'s
as-built snapshot describes a backend-only, no-edges, no-UI world that stopped existing five
sessions ago — it still lists the relation graph-write and the review UI as *"planned, not yet
built."* The invariants, the candidate-lifecycle machine, and both ADRs (0004/0005) are honest and
current. The notable **structural gap**: the relation half now has a real status lifecycle in code
(`staged_relations`) with no state-machine note — its entity twin ([[candidate-lifecycle]]) has had
one since S4a. Both are fixes for the M4 step-0 / a drawing pass, not blockers.

---

## 1. Drift — vault vs reality

- **`overview.md` is ~5 sessions stale — `risk`.** `updated: 2026-06-15`. Its "Built and merged"
  list stops at M2.S6; its M3 section says "Stages 1–3 built, proposal-only" + "M3.S4a — the backend
  milestone close"; and **"Planned, not yet built"** still names **M3.S4b (the review-queue UI)** and
  **"the relation graph-write + re-point-on-merge (S4a stages relation data but writes no edge)."**
  All of that shipped: S4b (PR #65), S4c (#67), S4d (#70), **S4e relation edges (#76)**, S4f relation
  UI (#78). The closing prose ("the graph is empty until reviewed; the §3.3 dedupe is now the human's
  gated decision") is still *true* but partial — it never mentions edges, intra-batch re-match, or
  handpick. This is the **doc-freshness-as-a-state-machine** failure again (an update-in-place note
  drifts exactly when nobody re-reads it); the fix is a single update-in-place refresh of the as-built
  block to "M3 feature-complete; M4 = V1 polish next." *Do at the roll* (it is decision-independent
  honesty, the same class the 2026-06-11 sweep folded for INV-2/latency).

- **`invariants.md` frontmatter date lags its body — `watch`.** `updated: 2026-06-15`, but INV-1 and
  INV-9 carry correct **2026-06-16 (M3.S4e)** broadening text + the ADR-0005 edge references. Content
  is honest; only the freshness stamp is a day stale. Bump `updated` on the next in-place touch.

- **INDEX priority queue stale — `watch` (self-healing).** "Next steps" item 15 ends "Next: M3.S4f";
  S4f shipped and M3 is feature-complete. INDEX is a **regenerated** note — this sweep regenerates it,
  so no manual fix is owed; flagged only so the reader knows the pre-regen INDEX lied by one slice.

## 2. Source-of-truth conflicts

- **None found.** The vault correctly *references* the spec/PLAN/code throughout. ADR 0004 and 0005
  live in `docs/decisions/` (product home); the vault folder stays empty by design. The candidate
  state enum, thresholds, and edge-id rule are referenced, not copied. No note claims authority over a
  fact another note also owns.

## 3. Missing decision records

- **None.** Every code-visible major call has a record: intercept-before-write → ADR 0004;
  relation-write-under-human-gate → ADR 0005; on-accept re-match (S4c) and handpick (S4d) were
  **deliberately ADR-declined** as contained changes, recorded in `docs/PLAN_SHORT.md` Decided + the
  INV-9 graph-vs-staging clarification. The "automated writer of a staged proposal" novelty (S4c) is
  named in [[invariants]] and [[candidate-lifecycle]]. Decision coverage is clean.

## 4. Invariant violations & near-misses

- **INV-1 / INV-9 hold for edges (S4e) — verified.** `RelationReviewService` (`agents/relation_review.py`)
  is the *sole* edge writer, reached only from the human decide endpoint; the coordinator writes zero
  edges. The guards are real: deterministic edge id (`uuid5(subject, predicate, object)`) + status-last
  + **re-resolve at commit** (a candidate retargeted/rejected between list-time and decide-time → 409,
  never a stale edge). This is the [[toctou]] guard done right — list-time resolution is advisory, the
  commit re-checks.
- **INV-3 reversibility for edges — gap now closed.** OQ-19 had flagged that `candidate_decisions` is
  entity-keyed, so an edge decision had no evidence row. `staged_relations` (status `staged|written|rejected`
  + resolved ids + committed edge id) is that home. The reversibility *trail* exists; an explicit
  un-write *endpoint* does not (same posture as entities — "designed undoable," no undo UI yet).
- **Near-miss — provenance collapse in the edge id (`watch`).** `uuid5(subject_id, predicate, object_id)`
  makes the same fact across N paragraphs **one** edge (clean graph, the §9 M3 goal) — but the graph
  edge then cannot enumerate its N mentions. The `staged_relations` rows retain per-paragraph provenance;
  the edge does not. Already a **carried follow-up** (ADR 0005, post-PoC). Not a violation — a documented
  tradeoff — but it is the kind of "clean now, lossy later" call worth re-reading before any
  provenance-dependent M-N feature (e.g. "show every passage where X betrays Y").

## 5. Structural rot

- **Relation lifecycle has no state-machine note — `risk` (the real gap this sweep found).** S4e/S4f
  shipped a genuine lifecycle — a staged relation rests in one of: *held* (an endpoint never accepted,
  or a self-loop after merges → never committable, no fuzzy fallback), *committable* (both endpoints
  resolve), and the terminals *written* / *rejected*, with the re-resolve-at-commit TOCTOU guard and the
  idempotent-by-edge-id effect. That is exactly a [[state-machine]], and its entity twin
  [[candidate-lifecycle]] has had a drawn note since S4a. The edge twin has none, and INDEX's "Awaiting
  content" still lists only *ingest-job* + *LLM-call* as "still to draw" — it does not even name the
  relation lifecycle as a gap. **Recommend** drawing `state-machines/relation-lifecycle.md` (a
  `decompose`/drawing task — out of this report-only sweep's remit) so the symmetric edge gate is
  modelled the way the node gate is. Filed as OQ-20.
- **Orphans / ghost links — none.** All recently-touched notes carry `related` edges; no dangling
  `[[wikilinks]]` found in the core notes or the new proposal.
- **Stale ADRs — none.** ADR 0004/0005 status matches reality; INV-8 is correctly `RETIRED` with its
  history preserved.

## 6. Fresh "but what if" — relation-write path + M4 boundary

- **A held relation is silently absent from the queue — `watch`.** Held endpoints and post-merge
  self-loops are "simply never committable; no fuzzy fallback." Correct for graph integrity — but does
  the author ever learn *why* a relation they saw extracted never became an edge? If `list_committable`
  just omits them, the evidence trail (INV-3) records the *written/rejected* ones but a *held* relation
  is an invisible non-decision. Low stakes at PoC; worth a surfacing decision when the relation UX is
  next tightened (ties the Evidence/Expiry stations for edges).
- **Relation Expiry — accepted none-at-PoC, but unbounded.** Every paragraph with an unresolvable
  relation leaves a `staged` row forever (ADR 0005, accepted). Bounded by one author's ingest; the same
  Expiry-station gap as OQ-4. Re-confirm, don't re-open.
- **M4 forward flags (milestone-boundary "what if"):**
  - **§3.4 graph story-vs-project scoping graduates from deferred to *live* — `risk` for M4.**
    `GET /stories/{id}/graph` (and `/entities?q=`) return **project**-scoped data; today one
    story = one project, so it is correct. The first M4 multi-story project makes `/stories/A/graph`
    and `/stories/B/graph` return **identical** graphs, and §3.4's "this story / whole world" toggle
    has no backend. This is the single biggest forward risk in M4's stated scope (multi-story + world
    graph) — it must be resolved *with* the multi-story slice, not after.
  - **DM-Rel-5's deferred edge re-point becomes live in M4.** S4e writes edges lazily so re-point
    "mostly dissolved" — *except* an accepted-entity↔entity merge (which doesn't exist in M3) re-points
    an already-*written* edge. M4's "properties/relations edit" + multi-story is where that merge
    arrives, so the one re-point case the relation design deferred is now real work.
  - **OQ-14 model-override dropdown** (INV-7 reconciliation) and **OQ-15 operational logging /
    INV-6 vacuity** remain open and unscheduled — carry into M4's cross-cutting, not resolved here.

---

## Concepts worth studying

- **State-machine symmetry.** When two features are duals (node gate / edge gate), their *models*
  should be too. The missing `relation-lifecycle` note (§5) is what an asymmetric vault looks like —
  the code grew a twin lifecycle, the projection layer didn't. Reading: any treatment of "modelling
  state explicitly" (e.g. Hillel Wayne on state machines) — the payoff is that a drawn machine makes
  the *held / never-committable* resting state a named box instead of an implicit gap.
- **Provenance vs deduplication.** The edge-id collapse (§4) is a clean instance of a recurring
  tradeoff: a content-derived id deduplicates (one fact = one edge) but erases multiplicity (how many
  times, where). Worth knowing the standard escape hatch — keep the dedup key on the *node/edge* and a
  separate *occurrence/mention* table for the N:1 provenance (which is exactly what `staged_relations`
  already is, un-promoted to the graph).
- **TOCTOU re-validation as a pattern, not a patch.** `RelationReviewService` re-resolves at commit
  rather than trusting list-time resolution — the general form of "check at use, not only at offer."
  Reading: [[toctou]] + optimistic-concurrency write paths.
- **The Expiry station.** Three sweeps running, the weakest station is still Expiry (OQ-4): no
  retention for held relations, uploads, or prompt logs. Not urgent at PoC — but "what accumulates
  forever?" is the question a single-user tool is structurally bad at asking itself.

---

_Report-only. No code or config was touched. Trail updated: OQ-20 added to [[open-questions]];
[[learning-log]] + [[changelog]] appended; INDEX regenerated._
