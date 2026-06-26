# Graph Quality — curate the graph you have

**Status:** Proposed — owner-approved 2026-06-26 (Session 66 preparation gate). The milestone
formally opens in [`PLAN_SHORT.md`](../PLAN_SHORT.md) at the next milestone roll; this document is
the source of truth for *what* it delivers.
**Date:** 2026-06-26
**Related:** [`story-forge-poc-spec.md`](../../story-forge-poc-spec.md) §3.3–§3.6 (cascade, viewer,
reader, multi-story); [`PLAN_LONG.md`](../PLAN_LONG.md) → *Graph quality & cleanliness*;
[`BACKLOG.md`](../BACKLOG.md) (the Session-54/60 findings this milestone resolves);
[`architecture/open-questions.md`](../../architecture/open-questions.md) → OQ-28;
ADRs [0004](../decisions/0004-intercept-before-write.md)–[0008](../decisions/0008-manual-correction-overlay-storage.md)
(the human-gate write paths this work surfaces).

> **Why a separate spec doc.** `story-forge-poc-spec.md` is the frozen record of *what V1 delivered*.
> This milestone is curation work **on top of** that PoC graph, not a new product surface, so it gets
> its own spec rather than amending the PoC spec. V2 Editing (PoC spec §4) remains the next *product*
> phase; this sits between V1 and V2 as a quality pass.

---

## 1. Context

V1 is feature-complete: ingest → extract → human-gated review → graph → viewer (M0–M4). By design the
PoC **over-extracts** — extraction is generous and *every* graph write passes through an explicit human
decision (nothing auto-writes; see [INV-1 / INV-9](../../architecture/invariants.md), ADR 0004/0005).
The result, proven on the real Oakhaven multi-story project (Session 54 smoke), is a dense graph with
many duplicates, near-synonym edges, and spurious nodes — *intentionally*, with curation left to the
human gate.

The owner now has a real graph to work on and wants to **clean it in place** — give the author fluid,
context-rich tools to curate the entities and edges that already exist, rather than re-running or
improving extraction. **Improving extraction is a later, separate pass** (owner steer, Session 66): we
polish the curation tools first; we try improving extraction during a subsequent polishing pass.

The enabling insight (owner's own observation, recorded across the Session-54/60 findings): **the human
gate is only as good as the context it shows you.** Today the matcher offers a name and a score but not
the source text needed to judge "is this the same one?", so correctness leans entirely on the author
already knowing the prose. Almost everything that makes the existing graph cleanable-by-hand is *bringing
the source text to the decision point* — and that is mostly **cheap, because the data already exists**
(every staged relation already carries its `paragraph_id`; every entity already has its mentions). The
write plumbing also already exists — edit-entity, merge-two-entities, delete, add/re-target/delete-relation,
all behind the human gate with a full undo log (ADR 0006/0007). So this milestone is **largely a
UX-surfacing job, not net-new write plumbing.**

## 2. What a clean, proper graph means here

Drawn from the owner's principles across the backlog findings. Granularity is **purpose-dependent** —
*not* "coarser is always better."

1. **No silent data loss on ingest** — every input paragraph is accounted for.
2. **Entities at the right granularity** — stable identity separated from transient modifiers
   ("desperate smuggler" → entity *Elara*, alias *smuggler*, state *desperate*); one node per real
   referent (don't fuse two different "crew"s; don't leave the two Vance sisters split-then-mis-merged).
3. **Merges you can trust because you could verify them** — the source context for each decision is
   visible, so correctness doesn't depend on the author holding the whole text in their head.
4. **Relations that reflect the prose** — the right predicate (not `ON_SHIP` *and* `PASSENGER_ON` as two
   edges), with the source sentence visible so nothing is committed blind. *(Right arity / modality /
   tense are extraction-side modelling concerns — deferred; see §5.)*
5. **Curatable in place and iteratively** — the author fixes problems where they see them; one pass is a
   starting point, not a finished graph.

## 3. Scope — in

Curation of the **existing** graph, working from the text and graph we already have:

- **S0 — Decompose the graph-curation surface** *(architecture, no build)*. Run
  `meta-architect:decompose-requirement` on "the graph view as a direct in-place curation surface." It is
  branchy (canvas interactions × the existing write paths × the human gate × undo) and the backlog note
  flags it as needing a design pass before any build. Output: data-flow, decision register (including the
  forward-compat edge-addressability call, §4), edge-case enumeration, and the slice boundaries for S3.
  **Milestone opener.**

- **S1 — Stop silent data loss** *(correctness; standalone, cheap)*. The auto-chunker can drop trailing
  paragraphs and report success — silent data loss (the worst failure class). Add a **completeness check**
  after `proposal_to_outline` (assert scene ranges cover every paragraph `[0, count)` — no gaps, no
  unassigned trailing paragraphs) and **fold the existing range-overflow check into the agent's retried
  validation** so a one-off LLM off-by-one re-prompts instead of 500ing. Failing test first. Independent
  of the curation surface — can land early. *(OQ-28 hazard #1; the single most serious finding.)*

- **S2 — Edge evidence + verifiable merges** *(the enabler; data already exists)*.
  - Click an edge in the viewer → show the predicate + the source sentence(s) (`staged_relations` keeps
    the per-paragraph provenance, ADR 0005).
  - Each entity-merge option (the graph panel + any merge target list) shows a **context quote + type +
    aliases**, so identity is verifiable before merging.
  - Cheap safeguards ride here: **gate exact-name duplicate creation** (warn / offer the merge); **don't
    present a score-100 exact-name match as self-evidently correct for common-noun / group types** (the
    two-different-"crew"s trap); **fix the amber "merge target" highlight** that makes a *New* card read
    as if Accept will merge.

- **S3 — The graph as an in-place editing surface** *(the spine; sliced per S0)*. Bring the existing
  write paths onto the canvas with the human gate and undo intact (INV-1 / INV-9 / INV-3): click a node →
  edit name/type/aliases/properties, merge with another node, or delete; click an edge → edit / re-target
  / delete the predicate; **consolidate two synonym predicates into one** (the relation analogue of entity
  merge — distinct from ADR 0005's exact-triple dedup, which only collapses *identical* triples). The
  owner's emphasis: **accessibility + fluid in-place editing** — a dense graph is only curatable if
  editing is easy and where you see the problem.

- **S4 — Navigate density** *(so curation is possible at scale)*. The spec §3.4 **filters** (by entity
  type / story / connection density) + node search by name. A hairball is only curatable if you can focus
  it.

- **S5 — Reader as a correction surface for existing entities** *(close the loop)*. Verify and fill gaps
  so the reader's click → side panel + right-click correction (mostly built in M4.S3c, spec §3.5) works
  against existing entities — so corrections that only surface while *reading* flow back to the graph.

**Backlog ride-alongs** (cheap, fold in where natural per the owner's "easy fixes along the way"):
review-queue "X of N remaining" count; empty-queue → onward navigation instead of a dead end.

## 4. Forward-compatibility call (decide in S0/S2, don't build the feature)

Relation deep-modelling (modality, arity, aspect, temporal validity) is deferred (§5). But the owner's
standing constraint is **design-constraint-now, feature-later**: don't bake in a bare, un-addressable
triple that a later temporal/modality model has to unpick. So S0 must make one explicit decision — does
an edge get enough **addressability** now (a stable id / handle) that a later model can hang a qualifier
on it — and S2's edge surface must respect it. This is a modelling-discipline decision, not scheduled
feature work.

## 5. Scope — out (deferred to the later extraction pass)

Everything extraction-side, to be picked up in a subsequent polishing pass once the curation tools are
good — **except S1** (kept in as a data-integrity fix, owner's call):

- Re-extraction; extraction-time granularity normalisation (separating stable identity from transient
  modifiers *at extraction*); open-world type/predicate auto-suggestion at extraction time.
- The **extraction + cascade eval baseline** (hand-authored reference graph, precision/recall scoring
  across model tiers) and the **spaCy-PreNER-without-LLM eval** (BACKLOG; PoC spec §7 Step 3).
- **Relation deep-modelling features** — modality / irrealis, n-ary arity (reification), eventive-vs-
  stative aspect + narrative-timeline ordering, temporal validity intervals — *beyond* the S0/S2
  forward-compat addressability call.
- Bulk-accept and other **intake review-queue** polish (this milestone curates the *existing* graph, not
  the intake path), except where entity-merge context naturally overlaps S2.

## 6. Success criteria

Working from the Oakhaven graph + its prose, the author can:

1. Trust that no content was silently lost on ingest (S1).
2. Merge / edit / delete entities and edges **on the graph canvas**, with the source context visible to
   verify each decision (S2 + S3).
3. Consolidate near-synonym predicates into one (S3).
4. Focus a dense graph via filters and search (S4).
5. Round-trip corrections through the reader (S5).

— ending with a **hand-cleaned Oakhaven graph** good enough to serve as the baseline you compare future
models and changes against.

## 7. The fork (owner decision after the sprint)

With a hand-cleanable graph in place, decide: **go deeper into extraction improvement** (the §5 deferred
work — re-extraction, eval baseline, relation deep-modelling, predicate auto-suggestion) **or move on to
V2 Editing** (PoC spec §4). The clean baseline this milestone produces is what makes that comparison
possible either way.

## 8. Invariants and constraints carried in

- **INV-1 / INV-9** — every entity and edge mutation stays an explicit human action; nothing auto-writes
  the graph. Curation actions are new *surfaces* for existing human-gated writers, not new automated
  writers.
- **INV-3** — every change is reversible; curation actions ride the existing `graph_edits` undo log
  (ADR 0007).
- **INV-4** — open-world types/predicates stay free strings; predicate consolidation is human-gated
  normalisation, never a closed enum.
