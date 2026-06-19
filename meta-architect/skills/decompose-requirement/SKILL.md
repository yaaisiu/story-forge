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
and adopt its doctrine, conventions, update modes, guardrails, and calibration. Before writing a
note, read `${CLAUDE_PLUGIN_ROOT}/templates/vault-note.md` for the canonical frontmatter shape;
some note types also have a dedicated structural template in `templates/` (`adr`, `component`,
`state-machine`, `glossary-term`, `project`) — read it if present. **A `proposal` has no dedicated
template by design: its section structure is the one step 4 below enumerates** (kept in the skill
body as the single home, not duplicated as a template). **Interactive and human-in-the-loop: you
propose; the human decides.** Get today's date with `date +%F`.

## 0. Ground yourself
- The requirement is in `$ARGUMENTS`. If empty, ask for it before proceeding.
- Read the vault: `INDEX.md`, `PROJECT.md` (especially the source-of-truth registry and the
  calibration), `overview.md`, `components/`, the glossary (count term notes to set
  progressive-disclosure density), `invariants.md`, `open-questions.md`.
- Slug the requirement (kebab-case). If `proposals/<slug>.md` already exists, enter update mode:
  merge into it, never duplicate it.

## 0b. Operation-surface completeness sweep (multi-slice features)

When the requirement is one **slice** of a feature too big for a single session (it will be sliced
across several — e.g. S3a/S3b/S3c), **before** committing to the slice boundaries do a completeness
sweep: enumerate the **full set of operations the feature must eventually deliver** — typically the
create/read/update/delete surface over each domain object it touches (entities, relations, mentions,
…) — and confirm **every** operation is assigned a home: *this* slice, a *named later* slice, or
*explicitly deferred-and-recorded* (a backlog item / a post-PoC note). An operation with **no** home
is a **slicing gap** — surface it to the owner and route it before decomposing. This is distinct from
the ripple analysis (step 3) and the "but what if" pass (step 4's edge cases): those ask *what could
go wrong*; this asks *is the set of capabilities complete, and is each one homed* — so a needed
capability isn't silently dropped and the first slice isn't secretly carrying a hard fork that belongs
in a later one. (Single-slice features: name it n/a and move on. Story Forge M4.S3a, 2026-06-19: the
sweep over CRUD-of-{entities, relations, mentions} caught two unplaced operations — entity
field-editing and whole-entity delete — and routed them into S3a / S3b before the decompose.)

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
  **Mark any decision that rests on un-inspected external-tool behaviour `verify-at-build`,
  not settled.** A register entry asserting how a third-party Action/CLI/API *works* — "this
  Action SHA-pins cleanly", "the scanner parses `uv.lock` natively", "this endpoint returns
  shape X" — is a *hypothesis* until the tool is actually inspected, and a plan-first builder
  can take it as gospel. State the assumption explicitly and tag it `verify-at-build` so the
  implementer confirms it before relying on it; the chosen mechanism may have to change at
  build time even after the owner approves the *intent*. (Story Forge, PR #44: the SCA
  proposal's "SHA-pin the scanner **Action**" rested on an action that turned out to be a
  no-`runs:` metadata stub — built as a digest-pinned container instead; the *intent*
  (pin the scanner immutably) held, the *mechanism* did not.)
- **But what if** — edge cases, races, partial failures, hostile inputs; name failure patterns
  precisely and teach the names.
- **Gaps for the product owner** — acknowledged gaps to carry back to the PO.

## 5. Draft ADRs — only on confirmation
- For any decision the human **accepts**, draft a MADR ADR in `decisions/` (lean by default;
  escalated form when 3+ live options or a security/data boundary is crossed). **Never write an
  ADR without explicit confirmation.**

## 5b. Reconcile the proposal to *resolved* state — when the human decides

The proposal is **update-in-place**: once the human resolves the register, the note must be brought
**fully** to resolved state, not left in "I propose / open" framing with only a banner on top. A
half-resolved accepted proposal reads as undecided and misleads the next implementer (it cost PR #34
six review passes). Do **all** of this, then verify by grep:

- Flip `status: proposed → accepted` and add a short resolution banner (outcome + pointer to the
  authoritative ADR / plan).
- Rewrite **every** register entry from *My proposal* → **Decision** — including any the human
  **overrode** (say so explicitly: "owner chose X over my proposed Y"). Resolve every "Open:"
  sub-question too.
- **De-activate rejected options across the *whole body*, not just the register** — the affected
  layer/station rows, the **Mermaid diagram** nodes, the `config.py`/component lists, the "but what
  if" edge cases, the gaps-for-PO, and the hand-off all restate the plan; a rejected gate/option
  lingering in any of them reads as a build instruction. Mark them history, don't leave them imperative.
- Strike the mirrored items in `open-questions.md` with a dated pointer; flip the priority-queue
  entries that this pass completed.
- **Reconcile the host-repo homes too** (the vault only *references* them, but the decision changed
  them): the spec, plans, every `AGENTS.md`, `README`. Then **grep the whole repo** for the old
  framing — this is the same sweep `/review-pr` §2 and the host `AGENTS.md` "reconcile a decision
  across every home" rule describe. Do it proactively, before review.

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
