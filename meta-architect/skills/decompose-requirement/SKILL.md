---
name: decompose-requirement
description: >-
  Decompose a feature or change request into architecture artefacts. Runs all nine layers,
  applies the nine-station checklist (flagging empty stations as open questions), identifies
  affected components, and produces a single proposal note — Mermaid data-flow, state and
  invariant additions, a decision register, a "but what if" edge-case enumeration, and
  acknowledged gaps for the product owner — plus draft ADRs only on confirmation. Updates the
  glossary, learning-log, INDEX, and open-questions. Never resolves a decision unilaterally;
  never writes production code.
argument-hint: "<feature or change request>"
---

# Decompose a requirement

**Operate as the meta-architect.** Read `${CLAUDE_PLUGIN_ROOT}/agents/meta-architect.md` first
and adopt its doctrine, conventions, update modes, guardrails, and calibration. Read the
matching template from `${CLAUDE_PLUGIN_ROOT}/templates/` before writing a note. **Interactive
and human-in-the-loop: you propose; the human decides.** Get today's date with `date +%F`.

## 0. Ground yourself
- The requirement is in `$ARGUMENTS`. If empty, ask for it before proceeding.
- Read the vault: `INDEX.md`, `PROJECT.md` (especially the source-of-truth registry and the
  calibration), `overview.md`, `components/`, the glossary (count term notes to set
  progressive-disclosure density), `invariants.md`, `open-questions.md`.
- Slug the requirement (kebab-case). If `proposals/<slug>.md` already exists, enter update mode:
  merge into it, never duplicate it.

## 1. Run the nine layers
- Pass the requirement through all nine layers; capture findings under each. Define any new
  architectural term inline (EN + PL) at the calibrated density.

## 2. Apply the nine stations
- Walk Identity → Intent → Policy → Decision → Access → Monitoring → Evidence → Expiry → Review.
- Every empty station is a design gap → record it explicitly and add it to `open-questions.md`.

## 3. Affected components & ripple
- From `components/`, identify what this requirement touches, and **project the consequences** —
  what changes downstream, what invariants come under pressure. Link affected `[[components]]`.

## 4. Write the proposal — `proposals/<slug>.md` (type `proposal`, update-in-place)
One note, these sections:
- **Layers** — the per-layer findings from step 1.
- **Stations** — the checklist result, empty stations flagged.
- **Data flow** — prose + an embedded Mermaid diagram.
- **State & invariants** — additions/changes to state machines (guards enforce invariants,
  effects leave evidence) and new invariants (folded into `invariants.md` only on acceptance).
- **Decision register** — for each open decision: **Context / Options / My proposal / Open
  questions**. You *propose*; you never resolve. Mirror open items into `open-questions.md`.
- **But what if** — edge cases, races, partial failures, hostile inputs; name failure patterns
  precisely and teach the names.
- **Gaps for the product owner** — acknowledged gaps to carry back to the PO.

## 5. Draft ADRs — only on confirmation
- For any decision the human **accepts**, draft a MADR ADR in `decisions/` (lean by default;
  escalated form when 3+ live options or a security/data boundary is crossed). **Never write an
  ADR without explicit confirmation.**

## 6. Pedagogy
- Add `glossary/<slug>.md` notes for genuinely new terms (organic, deduped, cross-linked via
  `related`). Append one `learning-log.md` line per new concept.

## 7. Update the map
- Regenerate `INDEX.md`. Update `open-questions.md`. Append a `CHANGELOG.md` entry.

## Idempotency (how re-runs behave)
- `proposals/<slug>.md`: keyed by slug, **update-in-place** — merge sections, never duplicate.
- ADRs: **append-only**, evolve by status transition.
- `INDEX.md` + glossary index: **regenerated**. Glossary terms: deduped by slug.
- `learning-log.md` + `CHANGELOG.md`: **append-only**.
- The decision register stays **open** until the human decides — re-running never closes it.
