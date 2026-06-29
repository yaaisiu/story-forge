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

Curation of the **existing** graph, working from the text and graph we already have. **Slices reshaped
2026-06-26 (Session 69)** after the S0 decompose + owner resolutions (register DM-GQ-1..7 in the vault
proposal `architecture/proposals/graph-curation-surface.md`): navigation pulled early (you cannot curate
a hairball you cannot see), two human-gated **"suggest, then you decide"** passes added (duplicate
*entities*, synonymous *predicate names*), and the predicate work reframed as *naming normalisation*, not
edge-joining.

- **S0 — Decompose the graph-curation surface** *(architecture, no build; ✅ DONE Session 69)*. Ran
  `meta-architect:decompose-requirement` → the `graph-curation-surface` proposal: data-flow, register
  DM-GQ-1..7, edge-case enumeration, and the slice boundaries below. The defining finding: the
  edit/merge/delete/undo write plumbing already ships (`EntityEditService`, M4.S3a/S3b) but only on the
  *reader's* panel — so the editing slices are largely UX-surfacing onto the canvas. **§4 resolved here**
  (see §4).

- **S1 — Stop silent data loss** *(correctness; standalone, cheap)* — ✅ **DONE Session 71 (PR #164)**.
  The auto-chunker can drop trailing paragraphs and report success — silent data loss (the worst failure
  class). Add a **completeness check** after `proposal_to_outline` (assert scene ranges cover every
  paragraph `[0, count)` — no gaps, no unassigned trailing paragraphs) and **fold the range check into the
  agent's retried validation** so a one-off LLM off-by-one re-prompts instead of 500ing. Failing test
  first. Independent of the curation surface — can land early. *(OQ-28 hazard #1; the single most serious
  finding.)* **As built (owner option B, Session 71):** one canonical rule `domain.paragraph_range_problem`
  (overshoot **and** coverage-hole; overlap allowed — duplication, not loss, partition-check deferred to
  `docs/BACKLOG.md`) is folded into the agent's retried `check` so **both** a coverage gap and an overshoot
  re-prompt (symmetric recovery); the `proposal_to_outline`/coordinator completeness assertion remains as a
  terminal `OutlineCoverageError` backstop. Both surviving-after-retry failures map to the route's 502.

- **S2 — Navigate the graph** *(pulled early — the foundation curation sits on)*. The §3.4 **filters**
  (by entity type / story / connection density) + **node search by name**, **and a better layout
  algorithm** to spread a dense graph (today's force-directed `cose` is an unnavigable hairball at
  Oakhaven scale). A hairball is only curatable if you can focus and read it — so this lands *before* the
  curation slices, not after. *(Was S4; promoted ahead of curation + the layout-algorithm dimension added,
  owner Session 69 — the planned filters alone don't fix the hairball.)*

- **S3 — Edge evidence + verifiable merges** *(the enabler; data already exists)*.
  - Click an edge in the viewer → show the predicate + the source sentence(s) (`staged_relations` keeps
    the per-paragraph provenance, ADR 0005).
  - Each entity-merge option (the graph panel + any merge target list) shows a **context quote + type +
    aliases**, so identity is verifiable before merging.
  - Cheap safeguards ride here: **gate exact-name duplicate creation** (warn / offer the merge); **don't
    present a score-100 exact-name match as self-evidently correct for common-noun / group types** (the
    two-different-"crew"s trap); **fix the amber "merge target" highlight** that makes a *New* card read
    as if Accept will merge.

- **S4 — Suggest duplicate clusters over the accepted graph** *(NEW — proactive entity dedup; human-gated)*.
  Re-point the §3.3 cascade matcher at the **already-accepted** entities (not just intake candidates) to
  **surface likely-duplicate clusters** the author would otherwise hunt for by eye — then the human
  reviews and commits each merge through the existing merge path (INV-1 / INV-9 hold; this *suggests*, it
  never auto-merges). Promoted from `docs/BACKLOG.md` (graph-traversal connection discovery) into scope,
  owner Session 69 — a solid step toward a cleaner graph. Feeds S3/S5's merge surface; likely its own
  `meta-architect:decompose-requirement` step-0 (it re-points the matcher over committed state).

- **S5 — The graph as an in-place editing surface** *(the spine; sliced S5a node / S5b edge per S0,
  DM-GQ-6)*. Bring the existing write paths onto the canvas with the human gate and undo intact (INV-1 /
  INV-9 / INV-3): click a node → edit name/type/aliases/properties, merge with another node, or delete;
  click an edge → edit / re-target / delete the predicate. Interaction model = **a selection-driven
  editable panel + a right-click shortcut**, reusing the reader's edit panel (DM-GQ-3). The owner's
  emphasis: **accessibility + fluid in-place editing** — a dense graph is only curatable if editing is
  easy and where you see the problem. Reserves the **§4 edge handle** at the first edge-write path.

- **S6 — Predicate-name normalisation + synonym suggestion** *(the reframed "consolidate"; naming
  consistency, not edge-joining)*. Reduce the *vocabulary* of relationship names that mean the same thing
  (e.g. rename `PASSENGER_ON` → `ON_SHIP` graph-wide), with an **NLP / embedding layer that *suggests***
  which predicate names look synonymous so the author isn't hunting the list. Renaming inevitably collapses
  any edges that become identical triples — that is a **reported side-effect** ("2 edges merged"), never
  the goal. Human-gated; predicates stay open-world free strings (INV-4). The relation twin of S4's entity
  dedup-suggest; carries the §4 edge handle (DM-GQ-1). Promoted from `docs/BACKLOG.md` (predicate
  proliferation), owner Session 69. Distinct from ADR 0005's exact-triple dedup, which only collapses
  *identical* triples.

- **S7 — Reader as a correction surface for existing entities** *(close the loop)*. Verify and fill gaps
  so the reader's click → side panel + right-click correction (mostly built in M4.S3c, spec §3.5) works
  against existing entities — so corrections that only surface while *reading* flow back to the graph.

**Ride-alongs** (cheap, fold in where natural per the owner's "easy fixes along the way"):
review-queue "X of N remaining" count; empty-queue → onward navigation instead of a dead end.

## 4. Forward-compatibility call (decide in S0/S2, don't build the feature)

> **✅ Resolved 2026-06-26 (Session 69, owner): YES — reserve a stable edge handle now.** Each edge gets
> an opaque surrogate id (a `uuid4`) carried *alongside* the content-addressed
> `relation_edge_id = uuid5(subject, predicate, object)`: the content id stays the MERGE/dedup key (ADR
> 0005 unbroken), the surrogate is the addressable handle a future temporal/modality qualifier can hang on,
> **preserved through re-point / merge / predicate-rename**. **We build no qualifier feature** — only
> reserve the hook. It lands with the first slice that opens the edge-write paths (S5/S6, register DM-GQ-1)
> and is **ADR-worthy** (it crosses the data-model identity boundary — draft the ADR at build). Fold rule
> (which handle survives when two edges collapse): the survivor keeps its handle; the folded edge's handle
> goes to the undo before-image. See [[surrogate-key]] / [[reification]] in the vault.

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
  modifiers *at extraction*); type/predicate auto-suggestion **at extraction time**. *(Boundary clarified
  Session 69: **curation-time** suggestion over the **already-accepted** graph is now IN scope — S4 suggests
  duplicate entities, S6 suggests synonymous predicate names, both human-gated. What stays deferred is
  suggestion baked into the *extraction/intake* path.)*
- The **extraction + cascade eval baseline** (hand-authored reference graph, precision/recall scoring
  across model tiers) and the **spaCy-PreNER-without-LLM eval** (BACKLOG; PoC spec §7 Step 3).
- **Relation deep-modelling features** — modality / irrealis, n-ary arity (reification), eventive-vs-
  stative aspect + narrative-timeline ordering, temporal validity intervals — *beyond* the **§4
  edge-addressability handle** (resolved Session 69 — reserve the hook, build no feature).
- **Bulk / multi-select** merge-delete-consolidate (DM-GQ-7 → `docs/BACKLOG.md`; S4/S6 already deliver the
  highest-value bulk need — proactive duplicate-cluster and predicate-name suggestion — without a generic
  multi-select) and other **intake review-queue** polish (this milestone curates the *existing* graph, not
  the intake path), except where entity-merge context naturally overlaps S3.

## 6. Success criteria

Working from the Oakhaven graph + its prose, the author can:

1. Trust that no content was silently lost on ingest (S1).
2. **Focus and read** a dense graph — filters, node search, and a layout that isn't a hairball (S2).
3. Merge / edit / delete entities and edges **on the graph canvas**, with the source context visible to
   verify each decision (S3 + S5).
4. Be **shown** likely-duplicate entities and synonymous predicate names to review — not hunt for them
   (S4 + S6).
5. Normalise relationship naming so one relationship isn't split across synonyms (S6).
6. Round-trip corrections through the reader (S7).

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
  writers. **The S4/S6 suggest passes *propose* (duplicate entities / synonymous predicate names) and
  never commit** — the human reviews and merges/renames through the existing gated path, exactly as the
  §3.3 cascade *proposes* and the human accepts.
- **INV-3** — every change is reversible; curation actions ride the existing `graph_edits` undo log
  (ADR 0007).
- **INV-4** — open-world types/predicates stay free strings; predicate-name normalisation (S6) is
  human-gated naming consistency, never a closed enum — it folds *instances*, never constrains the *type*.
