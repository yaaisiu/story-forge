# BACKLOG.md — Post-PoC backlog

> Concrete items surfaced **during** PoC work (mostly live smoke tests) that are real but
> **deliberately out of PoC scope** — features, UX polish, bugs, and design refinements to
> revisit after V1 ships. Kept here, not in `PLAN_LONG.md`, so the strategic plan stays
> milestone-level and stable rather than accreting a pile of tactical prose nobody re-reads.

## Where a follow-up goes (the routing rule)

This file is one home in the project's knowledge map (root `AGENTS.md` → *Where knowledge lives*):

| The item is… | It goes in… |
|---|---|
| a **strategic milestone / roadmap shift** | `docs/PLAN_LONG.md` |
| a **current-milestone** deferral (do as the milestone touches it) | `docs/PLAN_SHORT.md` → *Cross-cutting* |
| a **decision** made | `docs/PLAN_SHORT.md` → *Decided* / an ADR |
| a **convention** | the relevant `AGENTS.md` |
| a **post-PoC** feature / UX nit / bug / refinement | **this file** |

Nothing here is scheduled. The list is **reviewed at milestone rolls** (especially the PoC→V2
roll); when an item is picked up, **promote it to `PLAN_SHORT.md`** (and strike it here with a
pointer). Add items as a bullet under the right heading, citing the session/source so the
rationale survives.

---

## LLM task evaluation baselines (chunking, extraction, cascade)

A recurring need surfaced across the Session-33 smoke test: **every LLM-backed task needs a
model-vs-ground-truth benchmark**, not a one-off eyeball, so we can compare how different
models/providers cope before relying on any of them. The concrete instances:

### Chunking modes (auto / hybrid)

Three chunking modes ship (spec §3.1, `domain/chunking.py` + `ChunkingAgent`): **manual**
(deterministic `##`/`###` parsing, no LLM), **auto** (the LLM proposes the whole
chapter/scene structure), and **hybrid** (the human marks the boundaries they're sure of,
the LLM fills the rest). Only **manual** has ever been exercised end-to-end — every browser
smoke to date (incl. the Session-33 Oakhaven run) went through it. **Auto and hybrid are
untested in practice.**

Post-PoC, before relying on the LLM-backed modes, stand up an **evaluation baseline**: a
small set of real drafts (e.g. "Wody Święte" excerpts, the Oakhaven sample) each paired with
a hand-authored *reference* chapter/scene structure ("ground truth"), plus a harness that
runs auto/hybrid across the different model tiers (local Ollama, cloud-free, paid) and scores
each model's output against the reference. The questions to answer: does a given model detect
chapter/scene breaks sensibly, how does it handle ambiguous breaks (a scene shift with no
heading), how does hybrid merge human + LLM boundaries, and what does each run cost per model.
The point is a *comparable* benchmark — "how do different models cope with this task" — not a
one-off eyeball. Pairs with the data-flywheel section in `PLAN_LONG.md`.

### Extraction + cascade (entities, relations, matching, judge)

Same shape, one layer down: a set of drafts each paired with a hand-authored *reference* set
of entities + relations (and the expected dedupe outcome — which surface forms collapse to one
entity, which near-duplicates must stay separate, e.g. the Oakhaven `Elara Vance` vs `Elira
Vance`), plus a harness that runs the extraction + four-stage cascade across the model tiers and
scores precision/recall against the reference. Distinct from the **data flywheel** in
`PLAN_LONG.md` (which *finetunes* a custom NER model on accepted corrections): this is
*evaluation* — comparing models on the task — not training. The two share the corrected-corpus
substrate. **One dimension to score explicitly: surface fidelity** — are extracted entity
*names* grounded verbatim in the source, or paraphrased/hallucinated? (Session 33: the extractor
staged "broken table" where the source says "the overturned table.") This matters twice — it's an
extraction-precision signal, *and* a paraphrased name **won't highlight in the reader**, whose
render-time search (DM-IH-1) needs the canonical_name/aliases to actually occur in the prose.

## Entity-resolution limitations surfaced in testing (context, coreference, re-match ordering)

Session 33's live smoke test exposed several related gaps — all rooted in the matcher working on
*words* (RapidFuzz + embeddings), not *meaning/context*. The human gate handles each at PoC scale
(the author corrects in the review queue); noting them as post-PoC refinements.

- **Cross-story / world-graph identity is context-dependent.** Extraction stages generic
  role/common-noun candidates (`magistrate` TITLE, `harbor` PLACE). Within one story the gate
  filters them, but **once multiple stories exist, identity across stories is context-dependent** —
  story B's "magistrate" may be the same person as story A's, a *different* person, or really an
  *epithet for a named character*. Similarity will wrongly fuse two different magistrates and miss
  the epithet link. So **cross-story / world-graph merge cannot be similarity-only; it needs context
  and must stay human-reviewed** — exactly why spec §3.6 runs world-merge "with greater caution and
  always human review." Relates to the M4 §3.4 story-vs-project scoping + world-graph cross-cutting.
- **Intra-story coreference.** Even within one story, generic references — "the artifact"/"the
  device" → **Sunstone Compass**, "the magistrate" → **Garret Locke** — aren't linked by the matcher
  (lexically "artifact" ≠ "Sunstone Compass"), so they stage as separate entities and the author
  must handpick the merge by searching. The link is derivable from context (coreference), which
  lexical/vector matching can't do. Argues for coref/context-aware resolution.
- **Monotone re-match is order-sensitive — accept-the-decoy-first poisons the real target.**
  `ReMatchService` is monotone (DM-S4c-4, `candidate_rematch.py`): it only upgrades a `new` proposal
  to `merge`, never re-points an existing one. Concrete failure (the near-identical sisters):
  accepting **Elara Vance** first flips every pending `Elira Vance` mention to "merge → Elara (0.91)";
  then creating the correct **Elira Vance** entity does *not* re-target them (already `merge`, so the
  monotone guard skips them) — they keep proposing the wrong sister, fixable only by manual handpick
  (search → Elira Vance → merge). The order of acceptance matters. Monotone was chosen for
  idempotency/simplicity; a refinement would let re-match re-point to a *strictly-better* target (an
  exact 1.0 over an existing 0.91) or at least surface it in the card's alternatives, at the cost of
  re-match complexity. The human gate catches it, but it adds manual work on near-duplicate clusters.
- **Graph-traversal connection discovery (a possible mechanism for the above).** The "smuggler" =
  Elara link only became obvious *after* accepting both — the author didn't know at the start she's
  the smuggler; it emerged from reading, not from the words. Post-PoC, the accepted graph itself
  could *suggest* such links: traverse it for entities that are subjects of the same actions, share
  relations, or co-occur, and surface likely-same-entity / coreference candidates the lexical
  matcher missed — still human-confirmed. Turns the graph into an aid for *discovering* connections,
  not just storing them. (Owner idea, Session 33.)
- **One mention may refer to more than one entity.** The whole pipeline assumes *one mention → one
  entity*, but some references are plural or ambiguous: "his newest passenger" (Session 33) could be
  Elara, Elira, or both; "the sisters" is two entities at once. Such a mention has nowhere to land
  today. A post-PoC model would allow a mention→{entities} mapping (or an explicit "group/plural"
  resolution). Out of PoC scope.
- **One surface name → different entities by context (homonymy / name collision).** The mirror image
  of the merge problem: the *same* surface string legitimately denotes *different* entities depending
  on context, so it must **not** be fused. Examples (owner, 2026-06-20): "**Vance**" → *Elara* Vance
  or *Elira* Vance (shared surname); "**the Magistrate**" → Garret Locke (his office) *or* the
  magistracy *as an institution* *or* a different magistrate; "**smuggler**" → Elara Vance (in one
  passage she is the smuggler) *or* a generic/unnamed smuggler elsewhere. This bites in two places:
  (1) **matching** must allow a surface form to have *more than one* valid target and disambiguate by
  context, not collapse to one — the human gate handles it at PoC, but Stage-1/2 will keep proposing a
  single best target; (2) **the reader's render-time highlight search (DM-IH-1)** is purely
  name+alias string-matching, so every occurrence of "Vance" highlights as the *same* entity — it
  has no way to render two same-named entities differently, or to know which "the Magistrate" is the
  person vs the institution. A real fix needs **per-occurrence disambiguation** (a mention bound to a
  *specific* entity id, with stored spans — reopening DM-IH-1 span storage, S3c's territory) rather
  than name-search highlighting, plus context-aware matching. Closely tied to the coreference +
  context-dependent-identity bullets above and to the "entity-level properties + embeddings" direction.
  Out of PoC scope; recorded so the baseline graph + reader don't bake in a one-name-one-entity
  assumption a later disambiguation model has to unpick. (Owner note, 2026-06-20.)
- **Gate exact-name duplicate creation.** Accepting a candidate as *New* whose canonical_name
  *exactly* matches an existing accepted entity should be **gated** (warn, or auto-offer the merge),
  not silently create a second identical node — especially because M3 has no entity↔entity merge to
  undo it (that's M4 / DM-Rel-5). A cheap safeguard at the accept gate. (Owner idea, Session 33.)
- **Future direction — entity-level properties + embeddings enable richer matching.** Matching today
  is name-fuzz (Stage 1) + *mention*-context vectors (Stage 2). Once accepted entities carry
  **properties and an entity-level embedding** on the graph node, matching can compare *meaning and
  attributes*, not just surface strings — the mechanism most likely to close the coreference/context
  gaps above (smuggler→Elara, the magistrate→Locke). (Owner observation, Session 33.)

## Ingest & review UX feedback

Several "where am I / how much is left" gaps surfaced in the Session-33 smoke test. All
V1-polish-adjacent; could become M4 slices if they bother the author enough.

- **Extraction progress bar.** The extract trigger is one synchronous call: the button shows
  "Extracting…" and the user waits with no per-paragraph feedback (the Oakhaven run took a
  noticeable while). The extract result already carries `paragraphs_done`/`paragraphs_total`, so
  a real progress bar is feasible but needs the backend to *report progress mid-run*
  (SSE/streaming, or a poll-able job record) rather than returning only on completion — a small
  feature, not just a frontend spinner.
- **Review-queue count / position.** The review queue shows one card at a time with no "X of N
  remaining" indicator, so the reviewer can't tell how much work is left or where they are. A
  simple count (and maybe a position) would orient the author through a long queue.
- **Bulk accept (keep the human gate).** Confirming every obvious high-confidence duplicate
  one-by-one (the Oakhaven run had many confidence-1.00 stage-1 merge proposals) is tedious. The
  aligned fix is a **bulk "accept all confident merges"** action (or multi-select → accept), or
  **grouping duplicate mentions into one card** so an entity is accepted once, not per-mention —
  both keep INV-1/INV-9 (a human still explicitly decides; we've just collapsed N clicks to one).
  **Considered and advised against: threshold-based *auto-commit*** (the machine writing to the
  graph without a human click). That crosses the milestone's central human-gate invariant
  (INV-1/INV-9, ADR 0004) and weakens the "I control every decision" portfolio narrative; it would
  require the stop-and-amend-spec flow, not a quiet feature add. (Owner raised this Session 33.)
  **Concrete counter-example from the same session:** the matcher scored `Elira Vance` ↔ `Elara
  Vance` (two *different* characters — sisters, one letter apart) at **0.91**, above the 0.85
  re-match flip line — so any auto-commit threshold ≤0.91 would have *silently fused two distinct
  entities*. The human gate caught it (the distinguisher is meaning — "her younger sister" — not
  lexical/vector distance). This is the case-in-point for keeping the gate and adding a bulk lever
  rather than auto-committing. The human's create-new override is also a persisted hard-negative
  (`candidate_decisions` row) — the data-flywheel substrate, captured today.
- **Accepted-entities reference during review (orientation).** The reviewer can't see *what's
  already in the graph* while working the queue, so when a name recurs or a new surface form should
  fold into an existing entity, they search blind (and the quick "merge with instead" list is
  impoverished — see the entity-resolution note). A visible **panel of already-accepted entities**
  (ideally click-to-merge-into) would make orientation + handpick far easier on a long queue.
  Mechanism TBD. (Owner idea, Session 33.)
- **Empty-queue dead-end.** When the review queue is drained it shows nothing and offers **no
  onward navigation** (no "done → graph / relations" link, no back button) — the reviewer is
  stranded and has to edit the URL. The drained state should route on to the graph / relations.
  (Session 33.)
- **Edge evidence on click (graph viewer).** A node opens a details panel, but an **edge does not** —
  so the author can't see *what a relationship means* or *how it was stated in the text*. The
  provenance exists (`staged_relations` keeps the per-paragraph source even though the graph edge id
  collapses multiple mentions — ADR 0005), so an edge-click panel could show the predicate + the
  source sentence(s). Pairs with the §3.4 "drill-down to text" the spec already calls for. (Session 33.)
- **Graph navigation at density.** With many nodes the force-directed graph is hard to read (the
  Session-33 run, accepting generously, made a hairball). Spec §3.4 already calls for **filters**
  (entity type, story/chapter, connection density) — the intended navigation aid; not yet built into
  the M2.S5 viewer. (Session 33.)

## Graph curation & detail-level

The Session-33 reader run made the curation gap concrete. Three threads:

- **The reader is a correction surface.** Reading the highlighted text revealed errors the review
  queue can't show — a wrong Elira→Elara merge, entities that should have been marked but weren't,
  "the magistrate" highlighting as its own node instead of as Locke. This is direct evidence for the
  **next M4 slices** (click→side panel + right-click manual correction *in the reader*, spec §3.5):
  reading-with-context is where mistakes surface, so correction belongs there. Prioritise accordingly.
- **Detail level is purpose-dependent.** Accepting generously yields a dense, "everything" graph;
  other times the author wants a lean graph of just the principals. Post-PoC: a way to *curate* — bulk
  prune/keep, filter by importance, or per-view detail levels — using the displayed text for the
  context the graph alone lacks.
- **Open-world type proliferation.** Extraction invented ~23 fine-grained types (TAVERN, SHIP,
  ARTIFACT, FURNITURE, …) — INV-4 working as designed, but it crowds the reader legend and strains
  colour distinctness (DM-IH-5's hash fallback). Post-PoC: optional type consolidation/normalisation
  toward a coarser working taxonomy (without losing the open-world freedom). (Owner observations, Session 33.)

## Reader as the paragraph-by-paragraph working surface (post-PoC)

The reader (M4) starts read-only and gains correction (the next M4 slices). The owner's larger idea
(noted Session 34): make the reader the **primary working surface for the whole entity workflow** —
extraction, merging, and the user adding/removing entities — driven **paragraph by paragraph**.
Instead of (or alongside) the batch extract → review-queue flow, the author walks the text and works
each paragraph in place: extract this paragraph, see its candidates highlighted in context, accept/
merge/reject, manually tag a missed entity, remove a wrong one — all where the prose gives the context
the review queue lacks (this extends the "reader is a correction surface" thread above into a full
working loop). It pairs naturally with per-paragraph extraction (each paragraph is already the unit of
`entity_mentions` and the resume checkpoint).

The open design question this raises is **how relationships are treated in a paragraph-by-paragraph
context**, in two tiers:

- **Local (within the paragraph).** Relationships extracted from a single paragraph have both endpoints
  in view — the existing staged-relation → decide flow (`relation-lifecycle`) maps cleanly to "work this
  paragraph's relations here." How the per-paragraph relation surface looks in the reader (vs the
  separate relation-review queue) is the near design question.
- **Wider (across the text).** The harder, later question: relationships **between entities in different
  parts of the text** — a connection that only emerges from reading across paragraphs/chapters (the
  Session-33 "the smuggler = Elara" link surfaced only after reading both halves; see "Entity-resolution
  limitations… graph-traversal connection discovery"). A paragraph-local loop won't surface these, so we
  need a complementary way to work cross-text relationships: traverse/suggest from the accumulated graph,
  a whole-text relation pass, or a dedicated cross-section relation surface. How the local per-paragraph
  loop and the wider cross-text relation work compose is the open architecture question to think through
  before building this. (Owner idea, Session 34.)

## Reader entity side panel — visual refinement (post-PoC)

The M4.S2b side panel (click a highlight → details + `properties` + a 1-hop ego-graph mini-view +
an occurrence timeline) shipped **functional for the PoC**; the owner browser-check (Session 35)
flagged refinements deliberately deferred past V1:

- **Dense ego-graph on high-degree entities.** The embedded cytoscape mini-graph is hard to read for a
  busy node (Garret Locke = 29 neighbours / 40 edges crammed into a narrow column). The real fix is the
  **§3.4 graph *filters*** (already listed under *Graph curation & detail-level*) applied to the
  ego-graph, plus tuning the mini-graph's node/label sizing for a small box.
- **Styling polish.** Smaller fonts and general visual tidy-up of the panel (it mirrors
  `NodeDetailsPanel`'s plain structure; no design pass yet).
- **Wider / resizable panel.** Session 35 widened it `w-72 → w-80` as a cheap win; a resizable or
  larger panel would give the graph more room.
- **Richer occurrence entries.** The timeline shows a fixed ±60-char snippet (clamped to a few lines);
  an "expand to full paragraph" affordance would let the author read more without leaving the panel.

Two **code-level** refinements deferred from the Session-35 `/code-review` (recorded so a consciously-
deferred nit doesn't quietly grow into something bigger):

- **Cytoscape mounts rebuild the whole instance on data change.** Both `EgoGraphCanvas` (the panel
  mini-graph) and `graph-viewer/GraphCanvas` (the main viewer) destroy + re-create the cytoscape
  instance + re-run the `cose` layout whenever their data object's identity changes, rather than
  reconciling elements. Harmless at PoC scale (TanStack structural sharing keeps the ref stable when
  data is unchanged), but on a background refetch with genuinely new data it flickers/re-lays-out. If it
  ever bites, reconcile elements in place (cytoscape `cy.json({elements})` / add-remove) instead of a
  full teardown — and fix both mounts together (shared pattern).
- **The side-panel scroll bound is a magic constant.** `TextReader` wraps the panel in
  `sticky top-6 max-h-[calc(100vh-3rem)] overflow-y-auto` — the `3rem` is hand-synced to the page's
  `p-6`/`top-6` spacing. If the page padding or a future sticky header changes, that subtraction is
  silently wrong (panel overflows or leaves dead space). Folds naturally into the *resizable panel* work
  above — derive the bound from layout rather than a literal. (Session 35 `/code-review`.)

### Edit-affordance UX, deferred from M4.S3a-fe (Session 38)

The editable panel (M4.S3a-fe, PR #98) shipped **functional**; the owner explicitly deferred UX polish
past PoC ("not the time for UX… we'll iron the wrinkles after PoC"):

- **Relation add/edit UX is bare.** Adding a relation is a predicate text box + an entity search + a
  this→other/this←other direction toggle. Richer would be: edit a predicate in place (instead of
  remove + re-add), autocomplete predicates from existing edge types, and a clearer subject/object
  affordance than the arrow toggle.
- **Undo execution (the button) isn't built.** Every edit already records a before→after `graph_edits`
  row (INV-3 substrate), but there is no undo UI yet — corrections are forward-only (re-edit / remove +
  re-add). Undo-execution lands with **M4.S3b** (alongside undo-merge); this note tracks the *UI* gap.
- **A blank property key is silently dropped on save.** `rowsToProperties` skips a row whose key is
  empty (and a duplicate key → last-wins) with no hint to the author. Harmless, but a soft inline
  warning ("this row has no key and won't be saved") would be friendlier.
- **No "this name no longer appears in the text" hint.** Renaming an entity to a string absent from the
  prose correctly makes it stop highlighting (zero render-time matches, DM-S3a-4) — but silently. A soft
  hint (DM-S3a-4's deferred half) would tell the author aliases are the lever to restore coverage.

These were kept light on purpose — proof-of-concept, not final UI. (Owner browser check + `/code-review`, Session 35.)

## Frontend bundle — code-split the reader route (post-PoC, surfaced M4.S3c-fe1)

Adopting Tiptap for the reader (M4.S3c-fe1, Session 47) pushed the single Vite chunk over
500 kB (~1.04 MB / ~322 kB gzip), so `npm run build` now emits a chunk-size advisory (a
warning, not a CI gate). The reader/editor (Tiptap + ProseMirror) and the graph viewer
(cytoscape) are the two heavy, route-specific subtrees — natural candidates for a
`React.lazy` + dynamic-`import()` split so the initial load doesn't pay for both. Deferred
because it's a build-perf refinement with no PoC user impact (single-user, local). When
picked up: lazy-load the reader and graph routes, confirm the warning clears, and keep an
eye on the per-route gzip sizes. (Flagged in the PR-#115 review, not folded — out of the
fe1 parity scope.)

## Undo / delete robustness — V1 hardening (deferred from M4.S3b-be2, Session 42)

The general undo executor (M4.S3b-be2, PR #105) is **correct and reversible for the single local
author** the PoC targets; these make it sturdier for V1 / multi-context use. All were surfaced by the
session's `/review-pr` + multi-agent `/code-review` and consciously deferred (PoC-acceptable), recorded
here so they don't evaporate (owner ask: "note what should be done to make it more robust and better
working"). Routed here, not `PLAN_SHORT`, because none gates the current milestone.

- **Bound the undo stack (depth cap).** `graph_edits` retention is unbounded at PoC (the same
  none-at-PoC posture as `candidate_decisions` / `staged_relations`; ADR 0007, DM-S3b-7). A V1 depth
  cap (keep the last N operations, prune older grouped rows) prevents the log growing without limit.
- **Make undo-stack-head selection clock-independent.** `latest_live_operation` finds the top of the
  stack with `ORDER BY created_at DESC` over `graph_edits`, where each row of one grouped operation
  carries its *own* `default_factory` timestamp. It's correct for a single sequential author, but it
  leans on the highest-`seq` row being the latest-stamped. Stamp **one `created_at` per operation**
  (or order by a monotonic per-operation sequence) so concurrent/interleaved writes can't make the
  head land on the wrong (or a partial) operation.
- **Signal when an undo can't fully restore (open-world churn).** Undo of a delete recreates the node
  then its incident edges; if a *neighbour* was deleted in the meantime, `create_relation`'s
  endpoint-`MATCH` silently no-ops and that edge isn't restored (and the drift check only guards the
  primary entity, not far endpoints). Same for the delete-of-a-merge-survivor case (DM-S3b-5, owner
  chose allow + drift-refuse). Acceptable at PoC, but undo should **report** what it couldn't restore
  rather than claim a clean `applied`.
- **Harden the delete snapshot against a mid-delete crash.** `delete_entity` snapshots mentions+edges
  in memory, then deletes mentions, then the node, then writes evidence. A crash *between* the mention
  delete and the node delete, followed by a re-invocation, re-snapshots empty mentions (the node is
  still present) → that delete's undo can't restore them. Narrow window, single-user; a sturdier shape
  (e.g. evidence-as-pending-first, or a single cross-store unit) would close it.
- **Collapse the two grouped-row factories.** `_merge_rows` and `_delete_rows` (in
  `agents/entity_edit.py`) hand-maintain the same `id=uuid5(operation_id:seq)` + grouping-column row
  shape; a shared `_grouped_row(...)` factory would keep the id/idempotency scheme in one place when a
  third grouped op (split/un-merge) arrives. (Altitude nit from `/code-review`; pure refactor.)
- **`_next_generation` is a linear probe.** It queries `is_operation_undone` once per prior undone
  generation of the same targets. Fine at PoC depths; a single `MAX(generation)`-style read (or storing
  the generation explicitly) would make it O(1) and order-independent.

## Automated test tooling — Playwright + Postman (post-PoC)

Stand up **end-to-end browser tests (Playwright)** and **API contract/integration tests (Postman)**
after the PoC. Today the frontend is unit-tested (vitest + Testing Library) with the jsdom-untestable
cytoscape mounts covered by **manual** browser smoke walks, and the backend by pytest; there is no
automated browser-driven or external-API-contract layer. Post-PoC, Playwright drives the real UI flows
(upload → extract → review → reader / side-panel) and Postman exercises the REST surface, so the manual
smoke walks this project leans on become regression-guarded. (Owner note, Session 35.)

## World graph from multiple sources — attributable knowledge (post-PoC)

> **Scope decision — 2026-06-22 (owner): the WORLD-LEVEL / world-graph layer is OUT of PoC → here.**
> The "world graph" — a story belongs to a shared *world X* whose entities become cross-story merge
> candidates (spec §3.6; the world-graph-parent M4 slice) — is **dropped from the PoC**. What stays
> in PoC is the narrower **multi-story-within-one-project** capability: add a new story that **reuses
> the existing project graph**, with a migration that tracks **which entity appears in which story**
> (per-story entity membership) so the reader/graph can scope "this story vs the whole project", and
> so known entities can **leverage extraction** in a new story. That narrowed direction is recorded
> in `docs/PLAN_SHORT.md` (Decided 2026-06-22) and concretizes the long-deferred **§3.4 story-vs-
> project scoping** cross-cutting item — it is **not** this backlog entry. The spec (§3.6 + §9 M4
> feature order) still *describes* the world graph as in-scope; reconciling it to this decision is a
> pending **stop-and-amend** (propose → owner approves → amend §3.6/§9, then the plans). Until then,
> everything below (world-merge + the multi-source attribution generalisation) is **post-PoC**.

The spec plans a **world graph**: §3.6 (mark a story as belonging to world X → its entities
become merge candidates, same cascade with greater caution + always human review) and the M4 feature
order (multi-story → world-graph parent were V1 slices). Per the 2026-06-22 decision above, *cross-
story world-merge* — unifying entities across **stories** in one fictional universe — is now **post-
PoC** and lives here (basic multi-story-in-a-project, without the world layer, stays in PoC).

What the owner flagged (2026-06-19) is a **further dimension** the current model doesn't carry: using
Story Forge for **non-fiction / research** (the example: historical research) where the inputs are not
one author's stories but **multiple independent sources** that may **corroborate, disagree, or be
uncertain**. There, no single source is ground truth (unlike fiction, where the text *is* ground
truth), so the goal is a graph of **attributable knowledge** — every entity/relation/property claim is
**attributed to the source(s) that assert it**, and the graph preserves *who-says-what* rather than
collapsing conflicting claims into one "fact".

This generalises the existing world-merge: there the merge unifies entities and (per §10 q3) must
resolve **contradictory properties across stories** — "dialog UI, or soft 'both versions coexist'?"
The multi-source case pushes hard toward **"both coexist, each attributed"**: a relation/property
edge would carry **provenance** (which source, which passage) and possibly **agreement/confidence**
(how many sources assert it, do any contradict it). Building blocks already present:

- **Per-mention provenance is already captured** — `staged_relations` keeps the per-paragraph source
  even though the written graph edge collapses multiple mentions (ADR 0005). A source-attribution
  model is the same idea promoted from *mention* to *claim*, and scoped by **source** rather than only
  by chapter/paragraph.
- **Cross-source identity is context-dependent** — exactly the hazard already logged under
  *Entity-resolution limitations… "Cross-story / world-graph identity is context-dependent"*: source
  B's "the magistrate" may or may not be source A's, and similarity-only merge will wrongly fuse or
  miss links. Multi-source attribution makes this sharper (sources genuinely disagree), reinforcing
  spec §3.6's human-reviewed world-merge.

Open design questions to think through before building: what is the unit a source attaches to (a
node? an edge? a property? a whole claim/triple?); how a claim asserted by N sources is represented
(N attributed edges vs one edge with a provenance set); how contradiction is surfaced (the §10 q3
question, now multi-source); and whether "source" is just another scoping label alongside
story/project/world or a first-class node type. **Scope note:** the owner would like world-building in
the PoC "at least on basic level" — basic world-graph/multi-story is already the M4 plan; whether any
of the *multi-source attribution* model is pulled into PoC scope (vs recorded here as a post-PoC
direction) is an **owner scope call** that would go through the stop-and-amend-spec flow, not a quiet
feature add. (Owner idea, 2026-06-19.)

## Timeline / temporal qualification of relations & properties (post-PoC)

Owner flag (2026-06-19): **time is important in every aspect** and the model currently has no handle
on it. A relation today is a timeless assertion — `Garret —WEARS→ grey cloak` — but the real question
is **when** it holds, so wardrobe changes (and every other evolving state) can be tracked. Entities
change attributes over narrative time, relations start and end, states evolve; without temporal
qualification the graph flattens a whole story into one always-true snapshot.

The spec has **latent, unbuilt hooks** for this — they are the right anchors, not net-new ideas:

- An **`Event` node type** — "events on the world's timeline" (spec §3.2 taxonomy) — defined but never
  exercised; a natural anchor for *when* a relation/state holds (reify a change as an event).
- A per-entity **"timeline (where it appears in the story)"** in the §3.4 side panel — already shipped
  in M4.S2b as the **occurrence list** (occurrences in *text order*). That text/reading order is a
  proto-**narrative timeline** and the seed of real temporal ordering.

Things to think through post-PoC:

- **Two distinct time axes (bitemporal).** *Narrative/story time* — when in the fiction a fact holds —
  vs *record time* — when we ingested/edited it (already partly covered by the §10 q2 graph-versioning
  question + the `edit_history` log). Narrative time is the one the owner means and is the harder one:
  it's usually **not wall-clock**, but **relative/ordinal** — chapter/scene order, "before the duel",
  "after she leaves" — and may be vague or contradictory in the prose.
- **Where time attaches.** A relation edge needs a **validity interval / point** (`valid_from` /
  `valid_to`, or an anchor to an `Event` / scene), and the same for mutable **properties**. Modelling
  options: time-qualified edges, **reified relations** (edge → node so it can carry time + provenance),
  event nodes, or per-scene **state snapshots**.
- **Forward-compatibility now (ties to "get the baseline graph right").** Even though the feature is
  post-PoC, the **baseline graph we build during the PoC should not foreclose it.** The owner's stated
  PoC goal is a *clean, correct baseline graph to test changes and compare models against*, so the
  modelling choices made now (how relations are identified and stored, whether an edge is addressable
  enough to later hang a validity interval or an event anchor on) should leave the door open to
  temporal qualification + source attribution (see the multi-source section above), rather than baking
  in a timeless, single-snapshot edge that a later temporal model has to unpick. This is a design
  constraint to keep in mind on **current** relation-modelling decisions, not scheduled work. (Owner
  idea, 2026-06-19.)

---

## Process & tooling (post-PoC)

Refinements to *how we build*, deferred so they don't churn the process mid-PoC. (Process
changes still follow the human-in-the-loop `/retro` flow — this is just where the *idea* waits.)

- **Sweep skills + `AGENTS.md`/`CLAUDE.md` for soft/optional latitude phrasing.** Session 38
  surfaced that `/wrap-session` step 2 let the agent *self-assess* "this was routine" and skip the
  `/retro` prompt instead of asking (now fixed). The **class** of issue — rules worded with
  "maybe / at your discretion / if it feels routine / a X skipped by choice is fine" that let the
  agent decide what should be a deterministic step or an explicit user ask — likely recurs in other
  skills. Do a dedicated pass: grep the skills + the `AGENTS.md` files for that kind of latitude,
  and propose tightenings **one at a time** (each through `/retro`, human-approved) so a soft rule
  becomes either deterministic or an explicit "ask the user." Keep simplicity-first — only tighten
  phrasing that actually invites the agent to skip/guess a step, not every hedge. (Owner nudge,
  Session 38: "tighten up our rules and skills so they are more predictable/deterministic.")

## Code documentation generation — first stone toward living project documentation (post-PoC)

The owner's seed idea (2026-06-22): a tool/agent that **generates documentation from the codebase
itself** — the first stone toward a **living project-code-documentation** system where the docs are
derived from (and stay in sync with) the actual source, rather than hand-maintained prose that drifts.

This is deliberately recorded as a **direction**, not a spec'd feature — the design questions are wide
open and to be thought through before any build: what it documents (module/API surface, the
`api → agents → domain → adapters` layering, the agent/prompt/schema catalog, the data model), how it
stays *living* (regenerated in CI on change? a pre-commit step? diff-aware so it only re-derives what
moved?), how it avoids becoming a second source of truth that drifts (the same trap the architecture
vault's "reference, don't duplicate" rule guards against — see `architecture/AGENTS.md`), and whether
it leans on an LLM pass or stays deterministic-first ([[prefer-deterministic]]). It pairs naturally
with the public-portfolio goal (a stranger can read how the project is built) and with the existing
`AGENTS.md`-per-directory convention. Revisit at the PoC→V2 roll. (Owner idea, 2026-06-22.)
