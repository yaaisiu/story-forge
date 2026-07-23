# PLAN_LONG.md — Strategic plan

> Stable, big-picture. Update only when scope genuinely shifts. Source: §9 of `story-forge-poc-spec.md`.

## V1 — Ingest + Graph + Viewer

The user can upload a draft, chunk it, extract entities/relations with the cascade matching pipeline, review and accept them into Neo4j, and explore the resulting graph. As a side effect, the codebase showcases the agent + multi-model architecture to portfolio visitors.

- [x] **Milestone 0 — Setup** (2-3 days) — completed 2026-05-19
  Docker Compose, FastAPI + React skeleton, CI with security checks, plan files, root and directory-level CLAUDE.md.
- [x] **Milestone 1 — Upload & structure** (3-5 days) — completed 2026-05-26
  Upload endpoint, language detection, docx/md/txt parsing, ChunkingAgent (local Ollama + Ollama Cloud), manual chunking UI, outline view.
- [x] **Milestone 2 — Basic extraction** (5-7 days) — completed 2026-06-11
  Three-tier LLM abstraction (local Ollama, Ollama Cloud, paid cloud via OpenRouter — the preferred paid route; see `docs/decisions/0003`), ExtractionAgent with JSON-schema validation, PreNERAgent (spaCy), Neo4j writes without dedupe, cytoscape graph viewer, budget tracking, agent activity panel. _(Note: the PreNERAgent ships but is **not wired into the live extraction path** — extraction is LLM-only. The spec was reconciled in Public-readiness Session 1, 2026-06-25 — §7 Step 3 now marks PreNER deferred for the PoC. The spaCy-without-LLM eval that would wire it is in `docs/BACKLOG.md`.)_
- [x] **Milestone 3 — Cascade matching** (5-7 days) — completed 2026-06-17
  MatchingAgent (fuzzy + embeddings), JudgeAgent (LLM-as-judge), review queue UI with keyboard navigation.
- [x] **Milestone 4 — V1 polish** (5-7 days) — completed 2026-06-24
  Inline highlights, side panel, manual annotation, properties/relations edit, multi-story (one shared graph per project; the cross-story world graph is post-PoC — `docs/BACKLOG.md`). All slices shipped and the multi-story feature was live-smoke-verified (Session 54). **V1 PoC complete** (spec §9 M4 outcome).

### Data flywheel — a custom NER model, later

The PreNERAgent (M2) uses stock spaCy pipelines (`pl_core_news_lg`, `en_core_web_lg`)
as a deliberately recall-first, low-precision baseline. Every entity the user accepts,
relabels, or corrects through the §3.3 review loop is training data. Once enough has
accumulated, **finetune a custom spaCy model** on the corrected "Wody Święte" corpus and
swap it in behind the same agent — at which point a `NerPipeline` Protocol earns its
place (see `backend/src/story_forge/CLAUDE.md`). Not scheduled; a direction the
architecture is kept ready for.

## Public readiness — docs, demo, spec reconciliation (✅ COMPLETE — last build session 64; rolled to archive Session 68)

The moment V1 is complete, lock the portfolio presentation before opening the next big build
(owner decision, 2026-06-24 / Session 54). This is a **light, finite** pass — no new product
features — to make the public repo read cleanly to an outside visitor:

- **README overhaul** — the portfolio hook (the agent + multi-model architecture story), an
  architecture overview/diagram, a real quickstart, and **demo artifacts** in `docs/` (the
  Oakhaven multi-story graph + agent-activity-panel screenshots generated during the Session-54
  smoke).
- **Code documentation** — seeds the existing `docs/BACKLOG.md` item *"Code documentation
  generation — first stone toward living project documentation."*
- **Spec ↔ reality reconciliation (stop-and-amend flow)** — ✅ done. The spec described two
  features that aren't real: **PreNER as an active pipeline step** (dormant; extraction is LLM-only —
  reconciled Public-readiness Session 1, 2026-06-25; §7 Step 3 now marks it deferred) and the
  **world graph** (cut from PoC — reconciled Session 49, PR #119). The public spec no longer misleads
  on either. A third correction followed during the README work (2026-06-25): §2.1's *use-case*
  framing read as a "genuine personal tool" for an author actively writing "Wody Święte", but the
  PoC's sample content is LLM-generated (no real manuscript) and personal authoring/research use is
  aspirational — §2.1 now says so (immediate driver: exploring the architecture + build process), and
  the vault's `PROJECT.md`/`overview.md` business-driver framing was reconciled to match.
- **Security & CI posture writeup** — make the supply-chain + CI story legible to a visitor
  (owner-added 2026-06-25). The CVE approach (OSV/Trivy gates, the soak rule, the time-boxed-waiver
  lifecycle, the daily scan) and the CI approach (path-scoped jobs, always-on secret scan, branch
  protection) are real but live only in internal records (§6.7, `SECURITY.md`, `infra/*/WAIVERS.md`,
  the skills); surface them for an outsider rather than as an implied "secure-by-default" line.
- **Doc hygiene** — the `PLAN_LONG` boxes are now ticked; confirm the ADR/AGENTS map is navigable;
  consider a `CONTRIBUTING.md` (none exists today).

**Goal:** a stranger can land on the repo, understand what it is and how it's built, and run it.

## Preparation gate — before the next *build* milestone (owner, 2026-06-25, Session 60)

> **✅ Executed Session 66 (2026-06-26).** The prep gate ran: the PoC spec + backlog were reviewed,
> the Graph-quality milestone was scoped into its own spec doc ([`docs/specs/graph-quality.md`](specs/graph-quality.md)),
> this `PLAN_LONG.md` stub was refined (below), and the `AGENTS.md`/skills set was assessed (no new
> skill earns its place — the milestone is frontend-curation-heavy; `meta-architect:decompose-requirement`
> covers its branchy S0). The original framing is kept below for the record. ~~**Still pending:** the
> milestone **roll** (opens it in `PLAN_SHORT.md`) and the **S61 plan-trim prep** — separate units.~~
> ✅ Both done: the S61 plan-trim prep landed Session 67; the milestone **roll** landed Session 68.
> **Graph quality then ran Sessions 68–100 and closed at the Session-101 roll** — its full record is in
> [`docs/PLAN_ARCHIVE.md`](PLAN_ARCHIVE.md). A **second prep gate of the same shape is now due**: the
> next milestone is deliberately unchosen, and choosing it has a recorded prerequisite (below).

Before committing to the next build work (i.e. before the Graph-quality milestone below), run a
deliberate **cleaning / preparation pass** — the PoC's spec and plans were written for the PoC and
need a refresh for what comes after it. Concretely: **review the PoC spec and author a spec for the
new part of the work** (the PoC `story-forge-poc-spec.md` is PoC-scoped — the next phase likely needs
its own spec doc); **review this `PLAN_LONG.md`**; **adjust the `AGENTS.md`/`CLAUDE.md` set** to the
new shape of work; and **consider whether new skills or agents** earn their place. This is a
documentation/preparation/process gate, not a build milestone — its job is to make sure we *decide
what to do next* on a clean, current foundation rather than drifting into the next build on PoC-era
docs. Sequence it after the Public-readiness pass completes; slice it when picked up. (Recorded so
the next planning conversation can't miss it; the public-readiness pass stays the current focus.)

## Graph quality & cleanliness — curate the graph you have (✅ COMPLETE — S0–S7, Sessions 68–100; rolled to archive Session 101)

Then make the graph *trustworthy* before building writing features on top of it (owner: "a sprint
or two for graph clarity"). **Scoped at the Session-66 preparation gate** into a focused milestone —
full definition in [`docs/specs/graph-quality.md`](specs/graph-quality.md). The owner's steer
(Session 66): **focus this sprint on polishing the tools that work on the *existing* graph — curate,
fix, clean what's already there — rather than re-running or improving extraction; improving
extraction is a later, separate pass.** The write plumbing already exists (edit / merge / delete /
re-target, behind the human gate with undo, ADR 0006/0007), so this is largely a **UX-surfacing**
job, organised around the insight that the human gate is only as good as the *source context* it
shows at each decision.

Sliced (detail in the spec — **reshaped Session 69** after the S0 decompose + owner resolutions): **S0**
decompose the graph-curation surface ✅; **S1** stop the auto-chunker's **silent content loss** (the one
extraction-side item kept in — a data-integrity fix); **S2** **navigate** the graph — filters + node
search + a **better layout algorithm**, pulled early so curation isn't done on a hairball; **S3** edge
evidence + verifiable merges (the source quote at every decision) + cheap safeguards; **S4** **suggest
duplicate-entity clusters** over the accepted graph (proactive, human-gated — NEW); **S5** the **graph as
a direct in-place editing/curation surface** (the spine — node/edge edit/merge/delete on the canvas);
**S6** **predicate-name normalisation + synonym suggestion** (cut relationship-name noise, human-gated —
reframed from "consolidation", *not* edge-joining); **S7** the reader as a correction surface for existing
entities. The S0 decompose's main additions: two human-gated **"suggest, then you decide"** passes (S4
entities, S6 predicate names) and a reserved **stable edge handle** for future relation-modelling.

**Deferred to the later extraction pass** (the post-sprint fork — go deeper vs. move to V2): the
extraction/cascade **eval baseline** + spaCy-PreNER eval, and relation deep-modelling
(**modality / arity / eventive-vs-stative + timeline ordering**) beyond the **§4 edge-addressability
call** (resolved Session 69 — reserve a stable edge handle now, build the modelling later). Also tracked:
the deferred app capabilities this exposed — **re-structure / delete-story**.

## ◀ THE FORK — next milestone, deliberately unchosen (opened at the Session-101 roll)

Graph quality is done, and the roadmap now reaches a genuine **fork**: go **deeper on extraction**
(the deferred pass just above — re-extraction, the eval baseline, relation deep-modelling) or move to
**V2 Editing** (below). Both are legitimate next milestones; nothing in the roadmap decides between them.

**The choice has a recorded prerequisite: run fresh sample stories/articles end-to-end first.** The
working Oakhaven graph has been hand-curated across Graph-quality S4–S7 and therefore no longer shows
what the **pipeline** produces unaided — deciding the fork from it would read the wrong evidence. If
extraction is materially worse than the curated graph suggests, the extraction pass wins; if it holds up,
V2 wins. That run is a session of its own and comes *before* the fork is locked.

Two `docs/BACKLOG.md` items are flagged as **promotion candidates** for whichever branch wins, both
surfaced by real use in Session 100: the **normalise-names cards show no evidence** behind their labels
(a suggestion the author cannot evaluate is a human gate in name only — the Graph-quality thesis left
unapplied to its own S6 slice; the Session-101 architecture sweep independently reached the same finding
and supports promotion), and **24 % of the graph is isolated** (39 of 161 entities; two thirds at degree
≤ 1) with no bulk triage surface.

**Sizing note (Session-101 milestone-roll retro).** Graph quality was **8 slices but 33 sessions** — the
slice sizing was sound; the ~40 % that went to security-treadmill maintenance and one out-of-sequence
tooling detour was not planned for. Size the next milestone with that overhead in view, and keep it small
enough that its own Decided/Done log never approaches the `PLAN_SHORT.md` read limit (`docs/AGENTS.md` §7).

## V2 — Editing

Three modes (inline / dialog / diff), full edit_history pipeline. New agents: `InlineEditAgent`, `DialogAgent`, `DiffRewriteAgent`. Spec §4. Timeline after V1 (and after the two readiness/quality passes above).

## V3 — Style rewriting

Style presets, transfer from example, per-project style anchor. New agent: `StyleTransferAgent`. Spec §5. Timeline after V2.

## Security & DevSecOps hardening — later

Directions surfaced from a practitioner's DevSecOps notes (2026-06-08), kept ready but
not scheduled. The **governing principle** behind them: *security research takes
precedence over feature work* — a security-relevant change is researched (and, when it
touches the §6.7 baseline, decomposed + spec-amended) **before** other changes ship,
not folded in afterwards. Story Forge already practises a partial form of this via the
stop-and-amend-spec flow and the `meta-architect:decompose-requirement` pass that
produced the M2 backend SCA gate (`osv-scanner` vs `uv.lock`); the items below extend it.

- **Adopt Anthropic's `security-review` as a standing gate.** Wire the published
  Anthropic security-review (the `/security-review` skill and/or its GitHub Action) into
  the review flow as a routine pass on security-relevant diffs — fastest built by
  starting from Anthropic's own repo rather than hand-rolling. Complements, does not
  replace, `/review-pr` + `/code-review`.
- **Automated architecture-conformance gate.** Turn the meta-architect vault's
  invariants + the layering rules (`backend/src/story_forge/CLAUDE.md`) into an
  *automated* check (does the code still obey domain-imports-nothing,
  agents-use-the-`LLMProvider`-Protocol, prompts-in-`.j2`, LLM-output-Pydantic-validated?),
  rather than relying only on the reviewer-invoked `/review-pr` §4 greps and the manual
  `meta-architect:review-architecture` drift sweep.

## Operational logging & observability — later

The backend currently emits **no operational logs** (no `logging` config, no request/
error log lines) — surfaced 2026-06-11 while scoping the M2.S6 §6.7 key-redaction smoke.
At PoC scale this is acceptable (single user, run-it-and-watch) and it makes the "API
keys never logged" rule (§6.7) vacuously true. But structured operational logging
(request/error traces, an audit trail) is a real later need for debugging a live run.

**Distinct from training-data capture** (a common conflation): the data that feeds model
training is *not* scraped from stdout logs — it is the structured records the data layer
already persists. The **`llm_calls` ledger** holds per-call model/tier/tokens/cost/latency
(§6.6); the planned **`edit_history`** pipeline turns the author's accept/edit/reject
decisions into SFT/DPO pairs (spec §10 Q7 / the data-flywheel above). Operational logging
serves *observability*; the ledger + `edit_history` serve the *flywheel*. Keep them separate.

When operational logging *is* added, §6.7's key-redaction stops being vacuous: the M2.S6
leak-check smoke (documented in `backend/CLAUDE.md`) becomes its regression guard — auth
headers stripped, no `Bearer <token>` in any log line or traceback. Not scheduled.

## Post-PoC backlog → `docs/BACKLOG.md`

Concrete post-PoC items surfaced *during* PoC work — features, UX polish, bugs, and design
refinements (e.g. LLM-task evaluation baselines, entity-resolution limitations like coreference
and re-match ordering, ingest/review UX gaps, graph curation) — live in **`docs/BACKLOG.md`**,
kept separate so this file stays milestone-level strategy rather than a tactical pile. The
sections above (V1–V3, the data flywheel, security, observability) are the *stable strategic*
themes; granular "found it, fix it later" items go to the backlog. Reviewed at milestone rolls;
an item is promoted to `PLAN_SHORT.md` when picked up. (Split out Session 33.)

## When this file changes

A change here means the project's strategic scope shifted. Likely causes: a milestone proved infeasible, a new milestone became necessary, or priorities reordered. Every change here should be reflected in `PLAN_SHORT.md` and possibly in the spec.
