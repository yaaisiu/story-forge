---
name: document-code
description: >-
  Create or update Story Forge code documentation — in-code docstrings/comments AND standalone
  navigation docs (e.g. docs/CODE_GUIDE.md) — at a portfolio "good enough" bar, conservatively.
  Reuses the built-in Explore agent to survey, adopts the code-scribe doctrine to write (document
  only what the code verifiably shows; prefer omission to a guess; touch only the doc surface),
  and supports a diff-driven update mode so the same system refreshes docs as the code changes.
  Run when documenting a slice of the codebase, writing the code guide, or refreshing docs after
  a change.
argument-hint: "[scope: a path/glob | guide | reference [<area>] | changed [<git-range>]]"
---

# Document Story Forge code

This is the **first stone of the "code documentation generation" backlog item** (`docs/BACKLOG.md`,
owner seed 2026-06-22): a reusable toolset that documents the codebase and **keeps the docs
honest as the code changes**, without adding layers we can't maintain. It deliberately stays
light — it **reuses built-in agents** (Explore to read, general-purpose to write) and adds only a
doctrine, not a new agent.

**Two standing rules for this skill:**

- **Conservative by default.** The owner's steer is law: *better to write less and be sure of it
  than to add layers we're not sure of.* Uncertain → leave bare and flag, never guess.
- **Doc surface only.** This skill writes docstrings, comments, and doc files. It never changes
  logic. A run whose `git diff` shows a non-comment code line has gone wrong.

Work the steps in order. Don't eyeball where a `grep`/`git diff` can be exact.

## 0. Adopt the doctrine

Read **`code-scribe.md`** (beside this skill) and operate as it for the rest of the run — its
hard guardrails (verify-before-claim, prefer-omission, house-style, no-logic-changes,
navigate-don't-restate, Karpathy-minimal) govern every edit below. If you'll write a dated doc,
get the date: `date +%F`.

## 1. Fix the scope

`$ARGUMENTS` sets the target:

- **a path or glob** (e.g. `frontend/src/components`, `backend/src/story_forge/api`) — document
  the in-code docs (docstrings/comments) for that area.
- **`guide`** — author/refresh `docs/CODE_GUIDE.md`, the newcomer *navigation* doc (reading
  order + directory map + links; points, doesn't describe).
- **`reference [<area>]`** — author/refresh the `docs/code/*.md` *reference* layer: per-layer
  narrative notes that **describe** each module's responsibility and its key classes/functions
  (the "what's where" a reader/agent needs), one note per layer, indexed by `docs/code/README.md`.
  This is the descriptive sibling of `guide` — held to the code-scribe rule-6 *reference* discipline
  (module altitude, never a copy of signatures/behaviour). With no `<area>`, do the whole set; with
  one (e.g. `backend-agents`), refresh that note. See §4a.
- **`changed [<git-range>]`** — *update mode*: re-document only what moved (default range
  `main...HEAD`). See §5.

If `$ARGUMENTS` is empty, ask which scope before proceeding — don't default to "everything".

## 2. Survey (reuse the built-in Explore agent)

Spawn the **Explore** agent (read-only) to map the scope before writing. Ask it for: which files
/ symbols already have good docs, which are genuine gaps a stranger would struggle with, the
2–3 best house-style exemplars to match, and any docs that look **stale** (describe behaviour the
code no longer has). Reuse — don't re-derive the survey by hand.

For `guide` scope, the survey instead confirms the *navigation facts*: the real directory
layout, which `AGENTS.md` files exist, the actual request path through the code, the spec
sections that matter — so the guide points at things that exist.

## 3. Propose — concrete, conservative, and surfaced for anything non-trivial

Turn the survey into a concrete list: each `file:symbol` → the proposed docstring/comment, **or**
`leave bare — <reason>`. Apply the doctrine: anything you can't confirm from the code goes to
*leave bare + flag*, not to a plausible guess.

For more than a handful of edits, **surface the list to the user before applying** — they can
veto a guess before it lands. For a single small file or the guide, a brief inline summary is enough.

## 4. Apply (the executor adopts the doctrine)

- **Small scope** (one file, the guide, a few symbols): write the edits yourself in the main loop.
- **Bulk scope** (many files / a whole directory tree): spawn **built-in general-purpose**
  agent(s) — they have `Edit`/`Write` — **one per directory** for parallelism, each instructed to
  first read and adopt `code-scribe.md`, then apply only the agreed edits.

Write in the house style (§4 of the doctrine). For `guide` scope, keep `docs/CODE_GUIDE.md` to
the **navigation layer** — reading order, directory map, links to the current `AGENTS.md`/spec,
one short real request-trace — and **link it from README's Project map**. Never restate what an
`AGENTS.md` already owns.

> **Cite every path by checking it, never from memory.** A nav doc's main failure mode is a
> broken link — and ADR / `AGENTS.md` / module filenames are exactly what you misremember (e.g.
> `0003-llm-provider-routing.md` when the real file is `0003-llm-router-provider-order-and-budget.md`).
> Before you write a link, confirm its target exists (`ls docs/decisions/`, `ls` the dir). This is
> the verify-before-claim guardrail applied to *paths*, done at write time, not deferred to §6.

## 4a. Reference mode — `reference [<area>]`

The descriptive layer the navigation `guide` deliberately omits — the `docs/code/*.md` notes that
let a reader (or another agent) learn *what's where* without opening every file. **One note per
layer**, matched to how the code is organised — backend `domain`/`agents`/`adapters`/`api`,
frontend `features`/`data-layer` — plus a `docs/code/README.md` index that links them and is itself
linked from `docs/CODE_GUIDE.md` and the README Project map.

- **Bulk-spawn one general-purpose agent per note** (§4 bulk pattern): each first reads and adopts
  `code-scribe.md` (esp. rule-6 *reference* discipline), reads its layer's `AGENTS.md` + the code,
  then writes its note. Survey first (§2) so the agents target the real modules.
- **Give each agent the full *planned* set of sibling filenames up front** so its "how it connects"
  section links siblings directly. The fan-out is parallel, so a sibling note doesn't exist *on
  disk* when an agent runs — but the set is known *before* the fan-out, and a verify-before-cite
  agent that hasn't been told the plan will (correctly) refuse to link a file it can't see and leave
  a "link as they land" placeholder, forcing a manual cross-link cleanup pass afterward. Hand it the
  planned names (`./backend-domain.md`, `./backend-agents.md`, …) and that pass disappears. (Earned
  Session 62: the first `reference` run cost a six-edit cleanup because each writer was blind to its
  siblings.)
- **Each note's shape:** a 1-paragraph statement of the layer's responsibility → a module-by-module
  walk (each module's job + its key public classes/functions as a one-line *what + why*) → how it
  connects to the neighbouring layers. **Describe, don't trace:** no copied signatures, no field
  lists, no line-by-line behaviour — link to the code and the `AGENTS.md`/spec for those.
- **Links GitHub-friendly:** relative Markdown links (`../../backend/...`), not `[[wikilinks]]` —
  the public repo renders on GitHub, where wiki-links don't resolve (Obsidian still opens relative
  links fine). Cite every path by checking it exists (the verify-before-claim box below).

## 5. Update mode — `changed [<git-range>]`

The reason this is a *system*, not a one-off pass: re-run it to keep docs honest as code moves.

- `git diff --stat <range>` to find changed files; for each changed symbol, check its docstring
  still matches the new behaviour — refresh the stale ones, add docs to genuinely-new public
  surface (Karpathy-minimal), and **flag** any `docs/CODE_GUIDE.md` pointer the change invalidated
  (a moved/renamed/removed path). Don't re-document untouched code.
- **Also refresh the reference layer:** if a changed file's layer has a `docs/code/*.md` note,
  re-walk that note (`reference <area>`) — a changed responsibility, a new/removed key class, or a
  moved path is exactly what makes a reference note drift. The note's module altitude keeps this
  cheap: most symbol-level changes don't touch it, but a structural one does.

## 6. Verify

- Re-read each edit against the code it describes — every claim traces to a real line.
- Run the scope's gate, report-only: Python → `ruff check` / format check on touched files;
  TypeScript → `tsc --noEmit` / eslint; docs → confirm every link/path resolves to a real target.
- `git diff` shows **only** doc/comment/doc-file lines — zero logic changes. If it doesn't, stop
  and fix before reporting.

## 7. Report

Close out with: what was documented, **what was left bare and why** (the conservative residue is
a feature, not an omission), any drift/bug noticed-but-not-fixed (with `file:line`), and the
natural next scope. The reader should trust that everything written is true and nothing uncertain
was invented.
