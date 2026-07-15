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

## Distribute the `meta-architect` skills with the repository

The `meta-architect:*` skills (`decompose-requirement`, `review-architecture`,
`initialize-project-architecture`) that produce the `architecture/` vault currently live in a
**Claude Code plugin**, not in the repo — so they are **not distributed with Story Forge**. A
person who clones the public repo gets the vault (`architecture/`) and the ADRs that reference the
skills, but not the skills themselves, so they can't regenerate or extend the vault. **Owner ask
(Session 76): share the architect skills *with* the repository** so a cloner has the whole toolchain,
not just its output. Post-PoC because it's a packaging/distribution concern, not PoC functionality;
needs a decision on *how* (vendor the skills under `.claude/skills/`, document the plugin as a
dependency in the README, or a submodule) and a check that nothing in them is plugin-private. Pairs
with the public-portfolio goal — the repo already dogfoods the architect; the tooling should ship too.

**Scope escalated (Session 83, owner) — extract the whole toolchain as *portable, reusable* tooling
for his other repos, and make it the *next session's* focus** (after the Graph-quality S5b-fe merge).
The ask is broader than shipping the skills *with* Story Forge: package the machinery so it can be
**installed into any of his older repositories** and actually used there. Two asset classes, which
portable-ize differently:

- **The `meta-architect` plugin** (the `meta-architect:` agent + `decompose`/`review`/`initialize`
  skills + its doctrine) — already project-agnostic by design (it writes a vault, never touches
  project-specific policy). The easy one: carve it into its own git repo with a `.claude-plugin/plugin.json`.
- **The Story-Forge rituals** (`.claude/skills/`: resume-session, wrap-session, retro, review-pr,
  triage-advisory, add-dependency, pin-image, document-code — plus the `CLAUDE.md` doctrine). The
  higher-value, harder extraction: several are **coupled to Story-Forge specifics** (triage-advisory's
  `infra/osv/` paths, add-dependency's 14-day soak, review-pr's spec/plan reads). Extraction = deciding,
  skill by skill, *what is universal doctrine vs. a Story-Forge parameter*, and genericizing the rest.

Distribution mechanism = Claude Code **plugins + a marketplace** (`.claude-plugin/marketplace.json`):
`/plugin marketplace add <git-url>` once in any repo, then `/plugin install`, enabled per-repo in
`.claude/settings.json` + a `CLAUDE.md` doctrine snippet. Sketched next-session shape: (1) carve
`meta-architect` into its own repo; (2) genericize the reusable rituals into a second "dev-rituals"
plugin, parameterizing the coupling; (3) a marketplace repo tying them together; (4) trial-install into
one older repo. (Owner directive, Session 83, 2026-07-10 — this supersedes the narrower Session-76 ask
above and is the recorded next-session focus; see the handoff block.)

**Design pass DONE (Session 84, 2026-07-13 — [`docs/design/tooling-extraction.md`](design/tooling-extraction.md)).**
An interview-led design note landed (PR #192): the grounded current state (meta-architect is
*already* a checked-in plugin SF dogfoods via a local marketplace — the premise above is partly
stale), a skill-by-skill universal-doctrine-vs-SF-parameter classification (🟢 3 already-generic
meta-architect trio · 🟡 4 light-param `retro`/`add-dependency`/`pin-image`/`document-code` · 🔴 4
heavy-rewrite `resume-session`/`wrap-session`/`review-pr`/`triage-advisory`), a new keystone
`review-and-integrate` skill (the "thread it in deliberately, not blindly" ask), and the owner's
resolved decisions — **D1** one `dev-rituals` plugin · **D2** one tooling monorepo
(`claude-dev-tooling`) · **D3** adaptive `review-pr` · **D4** stop at design; extraction is a
multi-session build. Consumption model resolved (SF vendors its own copies with an upstream
provenance pointer — closes the Session-76 "how" question). **Remaining = the build**, sliced per
the note's §9: (1) graduate meta-architect into the monorepo, (2) genericize the rituals, (3) build
`review-and-integrate`, (4) trial-install, (5) reconcile SF. Each ~one session, in fresh
conversations. **✅ EXTRACTION COMPLETE (Session 89, 2026-07-13) — all five §9 slices shipped.** The toolchain
now lives as portable Claude Code plugins in the public monorepo
[`yaaisiu/claude-dev-tooling`](https://github.com/yaaisiu/claude-dev-tooling); "apply the SF
treatment" is a one-command install trial-validated end-to-end. The five build slices:

- **Slice 1 DONE (Session 85, PRs #194 + #195):** `meta-architect` graduated into the monorepo
  (plugin + root marketplace); SF **vendors** its in-repo copy with `meta-architect/UPSTREAM.md`
  provenance, settings unchanged, ADR 0002 extended (kept Accepted — the vendored copy holds it).
- **Slice 2 DONE (Session 86, monorepo PR #1):** the 8 rituals genericized as the `dev-rituals`
  plugin (portable skeleton + per-repo `.claude/dev-rituals.config.json` profile, every field
  defaulted; `review-pr` degrades gracefully per D3), listed in the root `marketplace.json`.
- **Slice 3 DONE (Session 87, monorepo PR #2):** the keystone `review-and-integrate` skill — scans
  a target repo, recommends a fitting ritual set, and wires it in on owner selection (modelled on
  `initialize-project-architecture`, human-in-the-loop, idempotent).
- **Slice 4 DONE (Session 88, monorepo PRs #3 + #4):** the trial-install acceptance test against the
  owner's `image-metadata-extractor` — green end-to-end (the seeded handoff read back through
  `/resume-session` with zero drift); five findings sharpened the skill, headline **overlap ≠
  redundancy** (the skill correctly *refused* a wrong `git rm`-the-bloat instruction).
- **Slice 5 DONE (Session 89, this PR):** SF-side reconcile bookkeeping — this closure, the
  design-note "build complete" banner, and the plan confirmation.

**Path A (owner, Session 85):** SF **keeps its own bespoke `.claude/skills/` permanently untouched**;
the `dev-rituals` plugin is built for the owner's *other* repos, genericized *from* copies of SF's
skills. Only `meta-architect` is vendored back into SF (slice 1). No further SF work — the item is
closed. Full arc in `docs/design/tooling-extraction.md` + `docs/PLAN_SHORT.md` Decided S84→S89.

### The `dev-rituals` copy-model is wrong — we need a *generator*, not a plugin that owns the skills (owner, Session 93)

Using the shipped `dev-rituals` plugin revealed that its distribution model defeats the one property
that makes the SF skillset actually valuable: **self-improvement in a loop.** The plugin ships the
rituals as **plugin-owned skills** + a per-repo `.claude/dev-rituals.config.json` for knobs. In a
target repo the skill *bodies* live in the plugin's install directory, not in the repo — so they are
effectively **read-only there**. That kills the living loop: `/retro` can't read a session's friction
and **rewrite the skill in place** the way it does in SF (where the skills are the repo's own files
and their git history records how each ritual evolved). A consumer repo gets **frozen copies + a
config file**, not a skillset that learns the project's habits and diverges the way SF's did.
(`meta-architect` does *not* have this problem — it's genuinely project-agnostic, writes into a vault,
and doesn't need to learn the repo's habits; hence "for the architect it may be working.")

**The reframe: flip the plugin from a *container of skills* to a *generator of skills.*** The tool
should **ingest** our reference skillset (SF's `.claude/skills/` + the `CLAUDE.md` doctrine), **analyse**
the target repo (stack, CI, test runner, existing rituals), and **scaffold native, repo-owned skills
into that repo's `.claude/skills/`** — tuned to that project. From then on the skills are the repo's
*own* files: `/retro` can evolve them, the repo's git history records the evolution, and each project's
ritual set diverges the way SF's has. The plugin becomes a **bootstrapper** (and optionally an
upgrade-advisor that diffs a repo's skills against the reference), **not the runtime home of the skills.**

Key point worth preserving: **"self-improving, working in loops" is a property of *where the files
live*, not a feature you can bolt onto a plugin.** Skills owned by the plugin are structurally
un-improvable-in-place; that's the whole argument for the rewrite. Shape is closer to
`meta-architect:initialize-project-architecture` than to `dev-rituals` — a one-shot, human-in-the-loop,
**idempotent scaffold whose output is code the target repo owns**. It supersedes / reframes what the
`review-and-integrate` skill does today (that one wires the *plugin* in; this one writes skills *out*).
Lives in the `claude-dev-tooling` monorepo, not SF. **After the current Graph-quality plan**, per the
owner. (Owner ask, Session 93, 2026-07-15.)

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

**Robustness gaps surfaced in the auto path (Session 54 smoke) — TWO facets, the second more serious.**

*(1) A plausible LLM off-by-one hard-fails structure with no retry (the loud failure).* Auto-structuring
the `oakhaven-2` sample 500'd on the first call with `paragraph_range (23, 27) exceeds paragraph count 27`
— the model proposed an inclusive end-index one past the last paragraph. The validation itself is *correct*
(`proposal_to_outline` in `chunking_coordinator.py` refuses to silently drop/duplicate text —
`OutlineRangeError` when `end >= count`), but it is raised **after** schema validation, so the agent's
`validate_with_retry` loop (which only retries on Pydantic `ValidationError`) doesn't catch it: one
nondeterministic LLM range error fails the whole request. A manual retry succeeded. Fix: fold the range
check into the agent's retried-validation step (re-prompt on overflow the same way as on a schema error).

*(2) The auto-chunker can SILENTLY DROP trailing content and report success (the dangerous failure).* On
the retry that "succeeded," the LLM returned an outline whose scene ranges **stopped early** — it kept the
`## Chapter Six` heading paragraph but omitted all six of that chapter's content paragraphs. Structure
returned `chapter_count: 3, scene_count: 6` with **no error**, and because **paragraphs are persisted from
the outline** (`outline_to_tree` → `insert_paragraph`, not from the upload's raw split), the dropped
paragraphs **never entered the system** — the reader rendered 19 paragraphs ending at a bare "Chapter Six"
header, and extraction/accept ran only over what survived. The author caught it only by *reading* the
rendered story. Root cause: `proposal_to_outline` validates range **overflow** (`end >= count`) but never
**coverage** — an outline whose scene ranges don't cover every paragraph passes silently. **Fix: add a
completeness check** — after `proposal_to_outline`, assert the union of scene ranges covers all `[0, count)`
paragraphs (no gaps, no unassigned trailing paragraphs), and on a gap either re-prompt (retry budget) or
fail loudly (a 502/422) rather than persist a lossy outline. Belongs with the auto/hybrid eval baseline
above — silent content loss is the single most important thing that eval must catch. **Until fixed, treat
`manual` mode as the only trustworthy structuring path for content integrity** (deterministic `##`/`###`
parse, no LLM, no dropping); auto/hybrid can silently truncate a story.

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

**The spaCy PreNER baseline *without* the LLM — the intended sequencing (owner, Session 54).** The
deliberate plan is: establish the **LLM + human-in-the-loop** extraction as the accepted-baseline
"ground truth" first, *then* measure how the deterministic **spaCy PreNER baseline copes on its own
(no LLM)** against it — stock `pl/en_core_news_lg` first, the finetuned model later (`PLAN_LONG.md`
"Data flywheel"). This is a distinct eval axis from the model-vs-model comparison above (which scores
*LLM* tiers): the question here is "how much of the accepted graph can a no-LLM, CPU-only path recover
— recall/precision against the LLM+human reference — and at what token saving." Confirmed dormant at
M4 (Session 54 smoke): the live `/extract` path is **LLM-only** — `PreNERAgent` is built but **wired
into nothing** in the extraction coordinator (the `known_entities`/PreNER-hint param exists but is
passed empty), so PreNER injection (proposal D3) stays "deferred until a real eval exists." That eval
is this item. (The spec-drift was reconciled in Public-readiness Session 1, 2026-06-25 — §7 Step 3
now marks PreNER deferred for the PoC; this eval is what would wire it.)

## Chunking coverage — reject overlapping scene ranges (post-PoC, surfaced S71 `/code-review`)

The Graph-quality S1 range check (`domain/chunking.py` `paragraph_range_problem`) enforces that the
auto-chunker's scene ranges **cover** every paragraph `[0, count)` — no gaps, no dropped trailing
paragraphs (the silent-data-*loss* case S1 targets). It deliberately **permits overlap**: a paragraph
claimed by two scenes passes, and `proposal_to_outline` then slices that paragraph's text into both
scenes, so the persisted outline (and downstream extraction) carries the paragraph twice. The S71
`/code-review` flagged this (PLAUSIBLE): duplication isn't *loss*, so it's out of S1's stated scope,
but the duplicated text feeds entity extraction and could double-count. The fix is small — tighten the
check to require a **partition** (cover *and* no overlap) by reporting any index covered more than once.
Defer until duplication is observed in a real auto/hybrid run (the auto path is itself untested in
practice — see *Chunking modes* above), or fold in when the auto-chunker is next touched. (Session 71,
2026-06-29.)

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
  not just storing them. (Owner idea, Session 33.) **✅ PROMOTED (the same-entity / dedup subset) into
  Graph-quality scope as S4 — "suggest duplicate clusters over the accepted graph" (re-point the cascade
  matcher at committed entities; the human commits each merge), owner Session 69,
  `docs/specs/graph-quality.md` §3. The broader coreference / non-duplicate connection-discovery (the
  "smuggler"→Elara semantic link) stays backlog.**
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
  assumption a later disambiguation model has to unpick. (Owner note, 2026-06-20.) **Sharpened by a
  concrete Session-54 case — recurring common-noun *groups*, and the score-100 false-merge trap.** The
  Chapter-Six review staged **`crew` (Group)** with a **`Merge → crew` proposal at score 100** — but that
  paragraph's "crew" is the **Iron Wake**'s (Locke's warship), a *different* group from the **Gilded
  Gull**'s `crew` already in the graph. A **perfect string score is not proof of same-entity** for generic
  recurring groups/roles ("crew", "guard", "the captain", "harbor") — each container/scene can have its
  own instance, so the *right* action is often **New**, not the offered merge. Two compounding needs: (1)
  *matching* shouldn't present an exact-name match as self-evidently correct for common-noun types; (2)
  **the reviewer must be able to verify *which* entity a merge targets before committing** — which is
  exactly the "**Merge candidates show only a name + score — no quote/context**" UX item under *Ingest &
  review UX feedback*. Without a target-disambiguating quote, the high-confidence card actively steers the
  author into fusing two distinct crews. The §3.3 human gate is the only thing catching it today, and it
  can only catch it if the UI shows enough to tell the two apart. (Owner observation, Session 54 smoke.)
- **Gate exact-name duplicate creation.** Accepting a candidate as *New* whose canonical_name
  *exactly* matches an existing accepted entity should be **gated** (warn, or auto-offer the merge),
  not silently create a second identical node — especially because M3 has no entity↔entity merge to
  undo it (that's M4 / DM-Rel-5). A cheap safeguard at the accept gate. (Owner idea, Session 33.)
- **Future direction — entity-level properties + embeddings enable richer matching.** Matching today
  is name-fuzz (Stage 1) + *mention*-context vectors (Stage 2). Once accepted entities carry
  **properties and an entity-level embedding** on the graph node, matching can compare *meaning and
  attributes*, not just surface strings — the mechanism most likely to close the coreference/context
  gaps above (smuggler→Elara, the magistrate→Locke). (Owner observation, Session 33.)

## Graph-quality S4 duplicate-suggestion quality — name scorer + embeddings (post-PoC, surfaced S79)

The S4 duplicate-suggestion list works and is correctly human-gated, but its **suggestion quality** on
the real Oakhaven graph was poor — a flood of false positives — traced during the S4b live review to two
independent upstream causes, **both outside the S4b frontend** (the list honestly shows what the backend
computes). Deferred by the owner ("work with embeddings sometime later"); logged so the quality work is a
deliberate, informed pass, not a rushed hotfix.

- **The RapidFuzz `token_set_ratio` name scorer over-matches on shared/subset tokens.** `name_match_score`
  (`backend/src/story_forge/domain/name_similarity.py`) uses `token_set_ratio`, which returns **100 when one
  name's tokens are a *subset* of the other's** (`harbor` — its alias is literally "harbor" — vs `harbor
  master`, or `docks` vs `city's labyrinthine docks`), and a **single shared generic word** inflates the
  score (the aliases "heavy fog" vs "heavy brass" → **71**, above the `duplicate_suggest_floor` of 60). The
  self-join scores across the *cross-product of all surface forms and takes the max* (`duplicate_clusters._best_name_score`),
  so one coincidental alias collision surfaces the whole pair; and the combine is `max(name/100, cosine)` on
  an `OR` qualifier, so a name-100 pair tops the list *regardless of cosine*. **Fix direction:** replace raw
  `token_set_ratio` with a length/coverage-aware score (blend with `token_sort_ratio`/`WRatio`, or penalise
  a lone-shared-token match) so a container/contained or single-shared-word pair can't reach the floor.
  **Caveat — this scorer is shared with the intake cascade matcher** (`agents/matching_agent.py`), so a
  change affects auto-merge/matching at extraction time too, and S6's predicate-name suggest will reuse the
  same pattern — so it wants its own decision + session, not a spot fix. (Owner-surfaced, Session 79.)
- **No mention embeddings for graphs extracted without the `models` group.** This Oakhaven graph's 512
  `entity_mentions` all have `embedding = NULL`, so every suggestion falls back to name-only and the Stage-2
  cosine signal that would counter the name over-match is entirely absent. This is **documented, intended
  degradation** (spec §3.3): the embedding model lives in the optional `models` dependency group, and
  `CandidateStager._safe_encode` fail-closes an encode failure to `None` — so a backend run *without*
  `uv sync --group models` stages every candidate with a NULL vector, and the mention is written NULL on
  accept. **To get embeddings for existing graphs:** install the `models` group, then either re-extract or
  write a one-off backfill that re-encodes each mention's stored `context` and updates
  `entity_mentions.embedding`. Note embeddings add *recall* but don't by themselves suppress the name-scorer
  false positives above (the two fixes are complementary). (Owner-surfaced, Session 79.)
- **Confirmed for S6 predicate names (Session 92, S6a-1 verify-at-build).** The predicted reuse landed: on
  the real Oakhaven vocabulary (227 predicates), a bare predicate `IN` `token_set_ratio`-matches **every**
  predicate containing "in" as a token (`LOCATED_IN`, `DOCKED_IN`, `STORED_IN`, …) at name=100 — the
  container/subset over-match above, now over labels. `domain/label_synonyms.suggest_label_synonyms` reuses
  the same `name_match_score`, so the same length/coverage-aware fix applies (it also normalises case/
  underscores first, which is *separate* — that's needed for `PERSON`/`Person` to match at all, not the
  over-match). The **embedding rung does earn its place** here though (unlike the S4 NULL-vector graph): on
  types it uniquely surfaces `LOCATION`↔`PLACE` (cosine 0.878) that fuzzy misses. Tune the predicate
  precision when the S6b list is live and the owner can see it (same "its own decision + session" posture).

## Edge re-key orphans its displayed provenance (post-PoC, surfaced S83 `/code-review`)

Edge provenance (the source paragraphs + evidence quotes S3b shows in the edge-evidence panel) lives
in `staged_relations`, keyed by the **content-addressed** `edge_id` (`uuid5(subject, predicate,
object)`). The S5b edge re-key (`retarget_relation`) rewrites the **Neo4j** edge to a new content id
but deliberately does **not** touch `staged_relations` (no migration — S5b-be). So after a
re-predicate/re-target, the new edge id has no staged rows → its evidence panel reads **200 + empty**
and shows "added manually", while the original provenance is **orphaned** under the old (now
edge-less) content id. A **fold** onto an existing edge B likewise does not merge the folded edge's
source paragraphs into B's provenance — B keeps only its own. Net: curating an edge silently drops the
provenance the S3b panel is meant to surface.

This is a **backend/data-model** concern, not a frontend cache-invalidation one — the S5b-fe
`/code-review` initially framed it as a stale `edge-evidence` cache, but verifying against the backend
showed the write never dirties another edge's provenance, so no invalidation would fix it (the fresh
read on the re-keyed id is genuinely empty). The real fix is to **re-key / carry the `staged_relations`
provenance across an edge re-key + fold** (re-point the rows to the new content id; on a fold, union
the folded edge's rows onto the survivor), so a curated edge keeps its evidence. Pairs with the §4
`edge_uid` handle (INV-10) — the durable handle is the natural join key a provenance-follows-the-edge
fix would hang on. Revisit when edge provenance durability matters (post-PoC). (Surfaced S83
`/code-review`, verified against `agents/entity_edit.py` + `domain/relation_rekey.py`.)

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
- **A "New entity" card with an *armed* (amber) merge target reads as if Accept will merge (Session 54).**
  On a `proposal === "new"` card (`CandidateCard.tsx`), the green "New entity" badge is correct and
  **Accept (A) creates a new entity** — but the card *also* shows the "MERGE WITH INSTEAD" list, and if
  an alternative is armed (the user clicked it, or pressed `M`/Tab, → amber `border-amber-400 bg-amber-50`),
  plus a "Why:" line that name-drops the existing entity ("…while the existing entity is a body of black
  water…"), the whole card reads as if Accept might merge into that highlighted entity. The behaviour is
  right (the armed target only affects the **Merge (M)** button; Accept always follows the badge) — the
  gap is *visual*: the armed-target state isn't subordinate to the proposal badge. Fix is presentational —
  make the armed highlight clearly secondary on a new-proposal card (or don't let an alternative read as
  "selected" until the reviewer is actually choosing Merge), so Accept's outcome is unambiguous. (Owner
  observation, Session 54 smoke.)
- **Merge candidates show only a name + score — no quote/context to verify identity (Session 54).** When
  choosing a merge target, the "MERGE WITH INSTEAD" alternatives (and the "OR SEARCH ALL ENTITIES" handpick
  results) display just `canonical_name (score)` — e.g. *political treason (73.3)* offered against a "royal
  treason" candidate. The reviewer can't tell whether *political treason* is **the same** treason without
  leaving the queue to inspect that entity. A short **provenance snippet per merge option** — the existing
  entity's own first-mention sentence / a representative quote (and ideally its type + a few aliases) shown
  inline or on hover — would let the author confirm "yes, same thing" before merging. Needs the backend to
  surface each candidate target's context (the existing entity's mentions are stored; the alternatives/search
  payload would carry a quote alongside the name). Pairs with the "accepted-entities reference during review"
  orientation item above. (Owner idea, Session 54 smoke.)
- **The relation review card shows no source context — you can't commit a relation blindly (Session 54).**
  The *entity* review card carries the ±200-char source quote (`candidate.context`), but the **relation**
  card (`features/relation-review/RelationCard.tsx`) renders **only the surface triple + confidence** —
  `Locke —RECLAIMS→ stolen artifacts (0.96)` with Commit/Reject and nothing else. So the author decides
  whether a relation is real without seeing **how it was stated in the prose** — and as the modality/arity
  observations above show, the predicate often distorts the source ("would reclaim" → `RECLAIMS`, a ternary
  "store X in Y" → a binary edge), so the sentence is *exactly* what you need to judge it. The data is
  already there to fix it cheaply: the staged relation carries a **`paragraph_id`** (`staged_relations`
  keeps the per-paragraph source — ADR 0005), so the card can render the source paragraph/sentence as a
  quote blockquote, **mirroring the entity card**. This is a hard requirement for trustworthy relation
  review, not a nicety — committing relations blind is how a distorted edge slips into the "clean baseline
  graph." Sibling of the "edge evidence on click (graph viewer)" item above (same provenance, different
  surface: the *review queue* vs the *graph*). (Owner observation, Session 54 smoke.)

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
- **Entity-span granularity — stable identity vs transient modifier vs role-alias (Session 60).** The
  extractor folds **transient descriptive modifiers** into the entity surface form. Public-readiness
  Slice B staged **`desperate smuggler` (Person) → Merge → Elara Vance** (with `Elara Vance (100)`,
  `Smuggler (53.8)`, `Elira Vance (50)` as alternatives), but the stable identity is the role-noun
  **"smuggler"** — which is really an **alias of Elara**, not a separate node — while **"desperate"** is
  a **momentary state** of hers in that passage, better modelled as a (time-qualified) property/state
  than baked into the entity *name*. Generalises the owner principle that **the right level of entity
  granularity is case-/purpose-dependent** — *not* a fixed "coarser is always better": sometimes a
  fine-grained span carries signal (the state), sometimes it's noise (a modifier glued to a name). Two
  needs: (1) extraction/normalisation should separate the **stable identity** (head noun / known alias)
  from **transient qualifiers**, promoting role-nouns like "smuggler" to **aliases** of the named entity
  rather than standalone entities; (2) the transient state ("desperate") wants a home as a **property or
  a time-qualified state**, not an entity name — ties to the modality / eventive-vs-stative threads in
  *Timeline / temporal qualification* and the coreference/alias bullets under *Entity-resolution
  limitations*. Pairs with "Detail level is purpose-dependent" above and the deliberately oversaturated
  PoC graph (over-extraction left for post-PoC). (Owner observation, Session 60 / Public-readiness Slice
  B smoke — "we'll think about it.")
- **The author's own knowledge of the text is load-bearing for merges today — and one pass isn't enough
  (Session 60).** Until extraction/matching improve, producing a good graph leans on the **human knowing
  the source and referencing it during the merge decision** — the matcher offers a name + score but not
  the context to judge whether two surface forms are truly the same (is *this* "smuggler" / "crew" /
  "the magistrate" the one already in the graph?), so the author's familiarity with the text fills the
  gap the UI doesn't. This is the human-side mirror of **"Merge candidates show only a name + score — no
  quote/context"** (under *Ingest & review UX feedback*): surfacing the source quote per merge option is
  what would let someone *without* the whole text in their head decide correctly. Second facet: **a single
  initial run is not enough** — a good graph needs **iteration** (re-review, re-extract, correct in the
  reader, re-match) after the first pass; the PoC's one-shot extract → review → graph is a starting point,
  not a finished graph. Pairs with the granularity note above, the reader-as-correction-surface /
  paragraph-by-paragraph working-surface threads, and the extraction-eval baseline. (Owner observation,
  Session 60 / Public-readiness Slice B smoke.)
- **Open-world type proliferation.** Extraction invented ~23 fine-grained types (TAVERN, SHIP,
  ARTIFACT, FURNITURE, …) — INV-4 working as designed, but it crowds the reader legend and strains
  colour distinctness (DM-IH-5's hash fallback). Post-PoC: optional type consolidation/normalisation
  toward a coarser working taxonomy (without losing the open-world freedom). (Owner observations, Session 33.)
- **Predicate proliferation — semantically-equivalent relations should be mergeable (Session 54).** The
  relation-side twin of open-world *type* proliferation: extraction coins predicates free-form, so one real
  relationship shows up under near-synonyms on the same entity pair — in oakhaven-2's Elara/Jonas relations,
  **`ON_SHIP` and `PASSENGER_ON`** (Elara is aboard the ship) and **`CAPTAINS` and `COMMANDS`** (Jonas runs
  the ship) are duplicate edges meaning one thing each. This is **distinct from the exact-triple dedup we
  already have** — ADR 0005's deterministic `uuid5(subject, predicate, object)` only collapses *identical*
  triples, so two *different* predicate strings stay as two edges. Post-PoC: a way to **consolidate/normalise
  equivalent predicates** — a canonical-predicate vocabulary, or human-gated "these two predicates mean the
  same, merge them" (the relation analogue of entity merge), or a similarity hint at extraction/review time —
  without losing the open-world freedom. Pairs with the type-consolidation bullet above and the
  graph-as-editing-surface item below (merging predicates is one of the curation actions the graph surface
  would expose). (Owner observation, Session 54 smoke.) **✅ PROMOTED into Graph-quality scope as S6 —
  "predicate-name normalisation + NLP synonym suggestion" (reframed by the owner Session 69 as *naming
  consistency*, not edge-joining: rename graph-wide, an embedding layer suggests synonymous names, collapses
  reported not silent), `docs/specs/graph-quality.md` §3.**
- **The graph view itself as a direct editing/curation surface (Session 54).** Seeing the multi-story
  graph whole made the gap concrete: it's a good *read-only projection*, but the author can't **act on it
  where they see the problem** — to fine-tune an entity's details, merge two nodes that are obviously the
  same, or add / re-target / delete a relationship, they have to leave the graph for the reader panel or
  the review queues. **Some of the operations already exist in code** — the reader entity panel (M4.S3a-fe)
  edits name/type/aliases/properties and adds/removes relations, and the backend has the write paths
  (`PATCH …/entities/{eid}`, `POST`/`DELETE …/relations`, entity↔entity `merge`) — so this is **largely a
  UX-surfacing job, not net-new write plumbing**: bring those operations onto the graph canvas (click a
  node → inline edit/merge; drag between nodes → propose a relation; click an edge → edit/delete predicate),
  with the human gate intact (INV-1/INV-9 — every change is still an explicit human action). The owner's
  emphasis: **accessibility + ease are the crux** — a dense hairball (see also "Graph navigation at density"
  + the §3.4 filters) is only curatable if editing is fluid and in-place. Larger than one slice; think of it
  as the **graph-side twin of "the reader as the working surface"** (next section) — the two together are how
  the PoC graph becomes genuinely editable by the author. Needs its own design pass / decompose before any
  build. (Owner direction, Session 54 smoke.)

## Graph view state in the URL — reloadable/shareable filters (post-PoC, surfaced S73 `/code-review`)

The Graph-quality S2 navigation controls (entity-type filter, min-connections degree filter, and the
node-name search term) live in component `useState` in `GraphViewer.tsx`, as the accepted
`graph-navigation` proposal (§5 — "all of S2 is UI state … `useState`/a small store, not a persisted
transition") specified, and matching the **existing story/project scope toggle** in the same component
(also `useState`). Consequence: a page refresh, a bookmarked graph URL, or a shared link drops the whole
filter+search configuration and the user lands back on the unfiltered graph. `frontend/AGENTS.md` (State
management) notes that "a filter the user could reasonably reload into belongs in the query string (read
via `useSearchParams`), so a refresh keeps it" — so this is a real, tracked deviation, deferred by owner
call (S73). Post-PoC, lift the graph **view state** into the URL query string via `useSearchParams` —
and do the **filters and the scope toggle together** for consistency (serialize the type set + min-degree
+ search term + scope; parse them back on load), so a reloaded/shared graph URL restores exactly the view
the author had navigated to. (Surfaced by the S2 multi-agent `/code-review`; owner chose useState-now +
backlog, 2026-07-01.)

## Graph layout — label crowding for a filtered set of disconnected nodes (post-PoC, surfaced S73 smoke)

The Graph-quality S2 layout swap (`cose` → `cytoscape-fcose`, `GraphCanvas.tsx`) spreads a *connected*
graph well — the whole-project Oakhaven view (186 nodes / 286 edges) opens as a readable force-directed
cloud. But when a filter narrows to a set of nodes that are **mutually disconnected** (e.g. the `Location`
type, whose 19 nodes' edges nearly all point at *other* types and are dropped), each node becomes its own
component and fcose hands them to its **component-packer** (`packComponents`), which tiles the singletons
into a tight grid. The nodes are fine, but the labels (long entity names, positioned to the right of each
node) collide across columns and smear. `nodeSeparation` doesn't help — it only spaces nodes *within* a
connected component, not the packer's grid (verified in the S73 smoke). The real levers each have a cost
this slice shouldn't pay: `packComponents: false` lets gravity/repulsion scatter the singletons but risks
crowding the *connected* whole-project view (the primary, verified-good one); hover-/selection-only labels
would declutter but change label behaviour for the whole viewer. Post-PoC, improve the disconnected-set
case — likely hover/selection-gated labels, or a packer-spacing tune, or a dedicated grid/list rendering
for an all-disconnected filtered set. Low urgency: it's a secondary view (filtering to one low-connectivity
type), the nodes are navigable, and later slices (S4 entity dedup, S6 predicate-name normalisation) thin
the graph anyway. (Surfaced in the S73 browser smoke; owner + agent agreed to ship S2 and backlog this.)

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

### Manual-correction UX, deferred from M4.S3c-fe2 (Session 48)

The manual tag / correction UI (M4.S3c-fe2, PR #117) shipped **functional** and the owner verified the
flows in the browser; two refinements surfaced and were deferred past PoC:

- **No type hints/autocomplete on the new-entity `type` field.** Tagging a new entity offers a free-text
  `type` input (open-world, INV-4 — correct by design). But with no suggestions, the author can fragment
  one concept across near-duplicate type names (`character` vs `Character` vs `protagonist`) just by
  forgetting how they named it before. Post-PoC: suggest existing types (the project's distinct
  `type` set) as autocomplete hints while keeping the field free-text. (Clean V1 polish.)
- **A manually-tagged surface form is discoverable only as an *occurrence*, not on the entity's
  "known forms".** By design (DM-S3c-1 / ADR 0008) a manual tag is a stored per-occurrence span, **not**
  an alias — so tagging an inflected form/pronoun ("terror" → *fear*, "Jankowi" → *Janek*) makes it
  highlight + appear in the entity panel's **Occurrences** timeline, but it is **not** added to the
  entity's `aliases`, and nothing feeds it back to the cascade. The owner found this *unclear* in the
  smoke ("can be a bit unclear what happens when we use this function"). Post-PoC options to weigh:
  (a) also append the tagged form to the entity's aliases (or a distinct "manual forms" list) so it's
  discoverable beyond the occurrence snippet and the cascade can learn it (flywheel substrate); and/or
  (b) make the occurrence-vs-alias distinction visible in the UI so the behaviour isn't surprising.
  Deliberately beyond DM-S3c-1's storage model — a design extension, not a bug. (Owner browser
  check, Session 48.)

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

## Graph cache coherence across a project's stories (post-PoC, surfaced M4 multi-story FE, Session 53)

With multiple stories in one project sharing a single knowledge graph, a graph-writing edit is
invalidated **per story**: every mutation hook invalidates the 2-element prefix
`["story-graph", <editedStoryId>]`, which refreshes both scopes of the *edited* story but **not**
a *sibling* story's project-scoped view (`["story-graph", <otherStoryId>, "project"]`). So if story
B's "Whole project" graph is open and an entity is edited via story A's queue, B's project view
shows a stale picture until the 30 s `staleTime` lapses (or the view remounts). **Self-healing, no
data risk** — purely a display-refresh lag, and it needs the contrived A-then-B-within-30s sequence
to surface at all. Deferred (PoC-acceptable) because the correct fix — invalidate the whole
`["story-graph"]` family (all stories' graphs) on a graph edit — touches **~11 mutation hooks**
(`useReviewCandidate`, `useEntityEdit`, `useMergeEntities`, `useDeleteEntity`, `useAddRelation`,
`useRemoveRelation`, `useDecideRelation`, `useTagOccurrence`, `useSuppressOccurrence`,
`useChangeBoundaries`, `useUndo`) plus their tests, none of which the M4 FE slice otherwise touched.
Surfaced by the slice's multi-agent `/code-review` (PR #130) and consciously deferred with the owner.
When picked up: add an `allStoryGraphsKey()` (or invalidate `["story-graph"]`) at the graph-writing
hooks and update their invalidation assertions.

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
- **`merge_entities`' edge re-point deletes-old-before-creating-new — the same data-loss window
  S5b-be's re-key just closed (surfaced Session 82).** `EntityEditService.merge_entities`
  (`agents/entity_edit.py`) re-points each incident edge as `delete_relation(old)` then
  `create_relation(new)` (two separate Neo4j transactions), so a store failure *between* them loses that
  edge entirely — no replacement, and (evidence-last) no undo row. The S5b-be `retarget_relation` had
  the identical shape until `/code-review` caught it; it was **reordered to create-new-before-delete-old**
  (a mid-failure then leaves a recoverable duplicate, never a missing edge, and a retry converges). Merge
  should get the same create-first reordering (a re-point's `new_id != old_id` always holds off the
  survivor, so the two writes touch distinct edges — the flip is safe). Narrow window, single-user,
  PoC-acceptable; recorded so the fix lands when merge robustness is next touched. (Session 82 `/code-review`
  finding on the sibling retarget path; `merge` left as-is to stay surgical.)

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
- **Modality / irrealis — the relation is asserted as fact when the prose frames it as intent or future
  (Session 54).** Sibling problem to temporal qualification, surfaced in the oakhaven-2 relation queue:
  the source reads *"Locke **would reclaim** the stolen artifacts **and deliver** justice"* (intention /
  conditional future — he has **not** done it), but the extractor staged flat present-tense edges
  `Locke —RECLAIMS→ stolen artifacts` (0.96) and `Locke —DELIVERS→ justice` (0.94), reading as established
  fact. Same class: *"the magistrate **intended to** corner the criminals."* The flat predicate model drops
  the **modal/aspectual** qualifier (irrealis vs realis — wants/intends/would/plans vs did/does), so desire,
  intention, hypotheticals, negation, and future all collapse into asserted truth. A polished graph needs a
  **modality/polarity qualifier on the edge** (realis vs irrealis, and the irrealis flavour — intention,
  desire, future, counterfactual, negated) so "plans to kill the king" isn't stored identically to "killed
  the king." Ties to the same forward-compat constraint above: an edge addressable enough to later carry a
  validity interval should also be able to carry a modality flag, rather than baking in a bare asserted
  triple. Design-constraint-now, feature-later. (Owner observation, Session 54 smoke.)
- **Relation arity — n-ary relations flatten to a binary edge and drop an argument (Session 54).** Another
  sibling to modality/time, surfaced in oakhaven-2: the source says *"hid the **letter** and the **cipher**
  back inside her **satchel**"*, so the real facts are `Black Wax Letter —in→ satchel` and `Obsidian Cipher
  —in→ satchel`. The extractor instead staged a binary **`Person —STORES_IN→ leather satchel`** edge — "we
  lack information **what** is stored." "Store X in Y" is **ternary** (agent / theme / container); the flat
  subject→predicate→object edge can hold only two endpoints, so any relation with more than two arguments
  loses one — and the extractor may root it on the wrong pair (here the *agent*+*container*, dropping the
  *theme*, which is the salient fact). Post-PoC modelling options are the same lever as time/modality:
  **reify the relation** (edge → node) so it can carry extra typed roles (theme, instrument, beneficiary…)
  alongside time + provenance, or decompose an n-ary statement into linked binary edges through an
  intermediate node. Until then, n-ary statements are silently lossy — an extraction-quality signal an eval
  should score (ties to the extraction-eval section) *and* a modelling constraint on how addressable an edge
  is. (Owner observation, Session 54 smoke.)
- **Eventive vs stative relations — classify them, and order the eventive ones on the narrative timeline
  (Session 54).** The single strongest motivation for this whole section, made concrete by oakhaven-2's full
  relation list: relations split into two kinds that the flat model treats identically — **eventive** (a
  point-in-time action: `TOSSED heavy pouch of gold coins`, `BROKE_SEAL`, `INSPECTS`/`READS`/`UNFOLDS` Black
  Wax Letter, `GRABBED Elira`, `GAZES_AT`) versus **stative** (an enduring fact about living things/state:
  `SIBLING_OF Elira`, `WEARS heavy woolen cloak`, `KNOWS gold`, `INVOLVED_IN political treason`). A flat,
  unordered list drops a momentary "tossed the coins" next to a permanent "sibling of Elira" with no way to
  tell which is a fleeting event and which is always-true — and the **eventive** ones cry out for
  **ordering along the narrative timeline** (the reading-order seed already shipped as the M4.S2b occurrence
  list). Two needs fall out: (1) a **relation aspect classification** (eventive/stative — possibly a derived
  or extracted flag) so the UI/graph can render and filter them differently; (2) **timeline ordering** of the
  eventive relations so the author can read the sequence of what happened. This is exactly the "time is
  important in every aspect" thesis above, with a concrete handle: aspect is *what kind* of relation, the
  timeline is *when* the eventive ones fire. (Owner observation, Session 54 smoke — the call to "ground and
  pound" the graph quality later.)

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

**First lightweight stone landed (2026-06-25, PR #146):** the `/document-code` skill +
`code-scribe` doctrine (`.claude/skills/document-code/`) — a *manual-assisted, conservative*
toolset (reuses the built-in Explore + general-purpose agents; documents only what the code
verifiably shows; diff-driven `changed` update mode) plus `docs/CODE_GUIDE.md` as its first
output. This is **not** the *generated/CI-derived living-docs* system this item envisions — it's
the human-in-the-loop precursor. The full direction (auto-derivation, drift-free regeneration)
remains open for the PoC→V2 roll.

**Second stone landed (2026-06-25, PR #148, Session 62):** the agent-authored **`docs/code/`
reference layer** — one narrative note per layer (backend `domain`/`agents`/`adapters`/`api`;
frontend `features`/`data-layer`) + an index, describing each module's responsibility and key
pieces at module altitude, cross-linked into the code; authored by one `general-purpose` agent per
layer under the `code-scribe` doctrine. `/document-code` gained a `reference` mode for it, and — the
piece this item flags as the hard part (*staying living, not drifting*) — a **forcing function** so
the notes don't rot: a `/review-pr` §2 lens + `/wrap-session` §3a backstop flag a structural code
change that should trigger `/document-code changed`. Still human-in-the-loop, **not** CI-derived
auto-generation — but it now has the *keep-it-fresh* discipline this item's "how it stays living"
question was about. Auto-derivation remains the open V2 direction.

## Consolidated agentic-system architecture note (post-PoC)

The owner's question (2026-06-25): is there a single architecture doc for the **agentic system**
(the chunking → extraction → matching → judging pipeline, multi-model tier routing, the cascade,
the human gate)? **Today it's real but distributed** — spec §6.5 (agent orchestration, *CRITICAL*)
+ §7 (pipeline) + §6.4 (data model); the `architecture/` vault (glossary `agent`/`cascade-matching`/
`model-tier-routing`, the per-feature `proposals/`, `state-machines/`, `overview.md` nine-layer,
`invariants.md` INV-6/INV-7); ADRs 0001 + 0003; the README Architecture section; and
`backend/src/story_forge/AGENTS.md` + the ~98%-documented `agents/` module docstrings. There is **no
single consolidated note** — the vault's `architecture/components/` dir is empty, which is the
natural home.

Worth creating for the portfolio (the agent orchestration is the project's most interesting part,
and a reader currently has to assemble it from many places), but **not urgent** and easy to get
wrong: it must **reference, not duplicate** the distributed sources (the vault's own
"orientation, not a source of truth" rule — `architecture/AGENTS.md`) or it becomes another drift
surface. Natural shape: a vault **component note** (+ a Mermaid agent-orchestration diagram)
authored by `meta-architect:decompose-requirement`/`review-architecture` (the authorized vault
writer — ADR 0002), linked from `architecture/INDEX.md` and the new `docs/CODE_GUIDE.md`. Revisit
when the agentic system is next worked (the Graph-quality milestone) or at the PoC→V2 roll. Pairs
with the "Code documentation generation" item above. (Owner question, 2026-06-25.)

## Dual-store data architecture — analyse Postgres + Neo4j split (post-PoC)

The owner's seed idea (2026-06-23): at some point **step back and analyse whether the two-store
design (PostgreSQL + Neo4j) is still the right call**, or whether there's an optimisation — fewer
stores, a different split, or a cheaper way to answer the queries that currently fan out across both.

Today the split is deliberate (spec §6.4): **Postgres** owns the document tree + metadata + mention
spans/vectors (`projects/stories/chapters/scenes/paragraphs/entity_mentions/edit_history`), **Neo4j**
owns the knowledge graph (`:Entity` nodes + dynamically-typed relations). They are joined *at the
application layer* with **no cross-store FK** (the OQ-1 two-store-write-consistency seam), so several
reads already touch both — e.g. the per-entity detail BFF (`GET …/entities/{eid}`), the reader
(project-scoped entities + story-scoped mentions), and now the **derived per-story membership** the
M4 multi-story slice adds (Postgres mention→story rollup filtering the Neo4j project graph). Each
such cross-store join is a place where the split costs us.

Recorded as a **direction, not a spec'd change** — questions to weigh before any move: do we
actually exercise Neo4j's graph-traversal strengths enough to justify a second store (vs. Postgres
+ `pgvector` + recursive CTEs, or Postgres graph extensions like Apache AGE), what would consolidation
cost in migration + lost graph-query ergonomics, and what does the cross-store join overhead measure
at real scale. Pairs with OQ-1 (`architecture/open-questions.md`) and the §6.4 multi-tenancy seam.
Revisit at the PoC→V2 roll. (Owner idea, 2026-06-23, Session 50.)
