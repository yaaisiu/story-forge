# ADR 0002 — Incubate the meta-architect plugin in-repo

**Status:** Accepted
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
