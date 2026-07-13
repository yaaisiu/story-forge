# ADR 0002 — Incubate the meta-architect plugin in-repo

**Status:** Accepted — the plugin **graduated** to its own repo 2026-07-13 (see the graduation
update below); Story Forge keeps a vendored copy, so the in-repo-folder decision still holds.
**Date:** 2026-06-01
**Related spec section:** n/a — dev tooling, intentionally *not* in the product spec (see Decision)

## Context

We built a domain-agnostic **meta-architect** — a Claude Code plugin (an architect persona plus
three skills: `initialize-project-architecture`, `decompose-requirement`, `review-architecture`)
that produces Markdown design artefacts into an Obsidian-compatible vault and teaches
architectural vocabulary as a side-effect of real work. It never writes production code.

This is **reusable tooling, not a Story Forge product feature.** Long-term it belongs in its own
repository, installable across any project. But we want to *use* it on a real project, learn from
it, and refine it before extracting — and Story Forge is a strong first patient precisely because
it already has a spec, two plan files, an ADR set, and seven `CLAUDE.md` files. That makes the
first run a real bootstrap *and* a stress-test of the tool's "respect and reference existing docs,
don't duplicate" promise.

## Decision

1. **Incubate the plugin inside this repo** as a self-contained directory, `meta-architect/`
   (its own `.claude-plugin/plugin.json` + `marketplace.json`, `agents/`, `skills/`,
   `templates/`, `decisions/`, `README.md`, `examples/`). "Graduating" it later is just moving
   that one folder to its own repository — no rewrite.
2. **Wire it via committed settings.** `.claude/settings.json` gains `extraKnownMarketplaces`
   (a **relative** `./meta-architect` directory source — no hardcoded home path) plus
   `enabledPlugins`, so anyone who clones and trusts the repo is offered the plugin.
3. **It is dev tooling, not a product feature** → it is deliberately **not** added to
   `story-forge-poc-spec.md`. The plugin's *own* design decisions live in
   `meta-architect/decisions/` (its ADRs); this ADR records only the host-repo decision to
   incubate it.
4. **Sequencing.** Built this session. Run `initialize-project-architecture` on Story Forge
   **next session**. Integrate the skills into the existing rituals (`/resume-session`,
   `/wrap-session`, `/review-pr`) **only after** learning from that first run — wiring the
   process before living with the tool once would be premature structure.

## Alternatives considered

- **Standalone repo from day one:** cleaner separation, but we could not dogfood it inside a real
  development workflow while building it — we'd be guessing at what works.
- **Global user-level install (`~/.claude/`):** available everywhere immediately, but not
  version-controlled as a unit, not reproducible for collaborators, and a weaker portfolio story.
- **Scatter the skills into `.claude/skills/`:** mixes the architect among Story Forge's own six
  skills and muddies extraction. A self-contained folder keeps the boundary clean.
- **Hard-wire the workflow integration now:** rejected as premature — validate after the first
  real run, then integrate on evidence (see Decision §4).

## Consequences

- The repo carries a clearly-bounded `meta-architect/` subtree that reads, to an outsider, as
  "we built and dogfooded our architect here, then extracted it" — a deliberate portfolio signal.
- `.claude/settings.json` now declares a local marketplace and enables the plugin (committed and
  reproducible). Collaborators are offered it on folder trust.
- The plugin's own ADRs (nine-layer model, glossary-as-knowledge-graph, vault update model) live
  under `meta-architect/decisions/`, separate from this `docs/decisions/` set — two namespaces,
  no collision.
- **Next session's first task:** run `initialize-project-architecture` on Story Forge (writes
  `architecture/`, referencing the spec and `docs/` as sources of truth rather than copying them).
  Increment three, later: evidence-based workflow integration.
- When the plugin is eventually extracted, this ADR remains the record of why the folder lived
  here and how it graduated.

## Update — 2026-06-26 (Session 68): evidence-based integration begins (Decision §4 condition met)

§4 deferred ritual integration until "after learning from that first run." That condition is now
met. `review-architecture` ran once (Session 58, `architecture/reports/2026-06-25-architecture-review.md`)
and the **Public-readiness milestone-roll retro** (Session 68, the first run of `/retro`'s
milestone-roll mode) surfaced the evidence: an architecture sweep that only runs when a human
remembers it is an un-triggered artifact that rots — the same failure class the vault's own
report-triage (`/resume-session` 3c) and the `docs/code/` freshness backstop were built to close,
and the milestone showed real vault drift (PreNER-as-live-stage) reaching the roll uncaught.

**Decision (owner, Session 68):** wire **`review-architecture` into the milestone-roll ritual** as a
standing step — `/wrap-session §5c` runs it at each roll (producer), paired with the existing
`/resume-session §3c` triage (consumer). This is the §4 "integrate on evidence" path, not a reversal.
The other two skills (`initialize-project-architecture`, `decompose-requirement`) stay
**event-triggered** (bootstrap / branchy-feature step-0), not ritual-wired — no evidence yet calls for
that. First execution of the wired step is the **next** roll (this roll encoded the wiring only;
owner's call, to keep the roll unit bounded). Reconciled homes: `docs/AGENTS.md §7`,
`.claude/skills/wrap-session/SKILL.md §5c`, `.claude/skills/resume-session/SKILL.md §3c`, root
`CLAUDE.md`, `architecture/AGENTS.md` "Status of the workflow integration". The vault *notes* that
still frame the integration as fully deferred (`open-questions.md`, `INDEX.md`, `PROJECT.md`,
`learning-log.md`) are writer-restricted and get reconciled at that next sweep.

## Update — 2026-07-13 (Session 85): the plugin graduated to its own repo

The "graduate later" plan in Decision §1 and the Consequences ("we built and dogfooded our
architect here, then extracted it") is now executed. `meta-architect` has been extracted into a
standalone public tooling monorepo, **[`claude-dev-tooling`](https://github.com/yaaisiu/claude-dev-tooling)**
(working name; owner: yaaisiu), which hosts the plugin plus a single root
`.claude-plugin/marketplace.json`. A future `dev-rituals` plugin (the genericized `.claude/skills/`
rituals) will join the same monorepo. This is slice 1 of the owner-directed tooling-extraction unit
designed in **`docs/design/tooling-extraction.md`** (Session 84).

**This is a graduation, not a reversal — SF keeps a vendored copy.** Per the design note's §7
consumption model, Story Forge does **not** switch to marketplace-installing the plugin. It keeps
this `meta-architect/` directory as a **vendored copy**, consumed via the unchanged local
`directory` marketplace (`extraKnownMarketplaces.meta-architect-local` → `./meta-architect`), and
re-syncs from upstream **deliberately**, never by an automatic pull. Rationale: the canonical copy
will be generalized for any workflow, and SF (its most demanding user) carries SF-specific tuning —
auto-flowing upstream changes would risk breaking the repo. This resolves the standing Session-76
"how does SF keep consuming these once extracted" question: vendor + record provenance.

So `.claude/settings.json` is **functionally unchanged** by this slice. What changed in SF:

- Added `meta-architect/UPSTREAM.md` — the provenance pointer (upstream URL, vendored version
  `0.1.0`, date, and the deliberate-re-sync policy).
- Updated `meta-architect/README.md` "Status" and `meta-architect/.claude-plugin/marketplace.json`
  "description" from "incubating / before extraction" to "graduated; vendored copy".
- This ADR update.

Deferred to later extraction slices (per the design note §9): genericize the rituals into
`dev-rituals` (slice 2), build the keystone `review-and-integrate` skill (slice 3), trial-install
into an older repo (slice 4), and the full SF reconciliation onto the consumption model incl.
`docs/BACKLOG.md`/plan updates (slice 5). The design note also flags one seam for slice 3:
`review-architecture`'s report needs a *consumer* in any repo that installs it (in SF that is
`/resume-session §3c`); `review-and-integrate` should wire that forcing-function.
