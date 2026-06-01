---
name: initialize-project-architecture
description: >-
  First-contact architecture bootstrap. Scans the repo (languages, frameworks, structure,
  CI, tests, deploy, existing docs), respects existing architecture documentation,
  classifies the project, runs ONE round of 5–7 high-impact interview questions (including
  one gauging the user's architecture-vocabulary familiarity), proposes a vault layout, and
  after explicit confirmation scaffolds an Obsidian-compatible architecture vault with an
  initial nine-layer pass. Writes only Markdown into the vault. Idempotent — re-running
  updates derived notes and appends history, never clobbers hand-shaped analysis.
argument-hint: "[vault-path; default ./architecture/]"
---

# Initialize project architecture

**Operate as the meta-architect.** Before anything else, read
`${CLAUDE_PLUGIN_ROOT}/agents/meta-architect.md` and adopt its doctrine, vault conventions,
update modes, guardrails, and pedagogical calibration for this entire run. Read the matching
note shape from `${CLAUDE_PLUGIN_ROOT}/templates/` before writing each note.

This skill is **interactive and human-in-the-loop**: it interviews the user and waits for
explicit confirmation before writing anything. Never skip a gate. Get today's date with
`date +%F` for `updated` fields.

## 0. Resolve the vault root
- Vault root = `$ARGUMENTS` if provided, else `./architecture/`.
- If a vault already exists there, enter **update mode**: regenerate derived notes (INDEX, the
  glossary index), refresh notes whose content changed, and NEVER overwrite update-in-place
  notes. Tell the user you are updating an existing vault, not creating one.

## 1. Scan the project (read-only)
- Detect languages, frameworks, directory structure, CI config, test layout, and
  build/deploy (Docker, compose, pipelines).
- Hunt specifically for existing architecture material: a spec, ADRs, design/planning docs,
  directory-level convention files (e.g. `CLAUDE.md`). You will **reference these as sources of
  truth, not duplicate them.**

## 2. Classify the project
- One of: web app · CLI · library · service · data pipeline · infrastructure · plugin · other —
  with a one-line justification grounded in what you actually scanned.

## 3. Interview — ONE round, 5–7 questions
- Pick the 5–7 highest-impact questions from gaps the scan could **not** answer. Never ask what
  the repo already tells you.
- Exactly one question gauges the user's architecture-vocabulary familiarity
  (novice / building / comfortable / advanced) — this seeds progressive disclosure.
- Tailor questions to the detected project type. Ask once; do not loop the interview.

## 4. Propose the vault layout — then CONFIRM before writing
- Present the files/dirs you intend to create (below) and which existing docs you'll reference
  as sources of truth.
- **Wait for explicit confirmation. Write nothing until the user agrees.**

## 5. Scaffold the vault (only after confirmation)
Create, each from its template:
- `INDEX.md` *(regenerated)* — auto-generated map of the vault; never hand-edited.
- `PROJECT.md` *(update-in-place)* — identity, personas & business, the source-of-truth
  registry, calibration — from the interview answers.
- `glossary/` directory + `glossary.md` index *(regenerated)* — the knowledge graph, seeded in
  step 7.
- `learning-log.md` *(append-only)*.
- `invariants.md` *(update-in-place)*.
- `open-questions.md` *(update-in-place)*.
- `CHANGELOG.md` *(append-only)*.
- empty directories: `decisions/`, `components/`, `state-machines/`, `proposals/`, `reports/`.

## 6. Initial nine-layer pass (seed system overview)
- Run the nine layers over the project **as a whole**; write `overview.md` *(type `overview`,
  update-in-place)* as the seed analysis note — the system-altitude (C4) view, distinct from
  `PROJECT.md`, which holds the system-altitude *inputs*. Personas and business are loudest, but
  touch every layer. Apply the nine stations; record empty stations and gaps into
  `open-questions.md`.

## 7. Seed the glossary
- Add a `glossary/<slug>.md` term note for each architectural term that genuinely surfaced
  during the interview and the seed pass (organic, deduped by slug). Cross-link `related` terms.
  Regenerate `glossary.md` as the index.

## 8. Log the writes
- Append a `CHANGELOG.md` entry: today's date + every file written this run.

## Idempotency (how re-runs behave)
- **update-in-place** (never clobbered): `PROJECT.md`, `overview.md`, `components/*`,
  `invariants.md`, `open-questions.md`, `glossary/*`.
- **regenerated** each run: `INDEX.md`, the `glossary.md` index.
- **append-only**: `CHANGELOG.md`, `learning-log.md`.
- Re-running refreshes derived notes and appends history; it never overwrites hand-shaped
  analysis. Glossary terms dedupe by slug.
