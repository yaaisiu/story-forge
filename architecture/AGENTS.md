# AGENTS.md — architecture/

This directory is the **meta-architect vault**: the *architectural projection layer* over Story
Forge. It holds the consequence-analysis the repo did not previously have anywhere — named
invariants, state machines, a decision register, per-feature decompositions, dated review sweeps,
and a teaching glossary. It was bootstrapped by the in-repo `meta-architect/` plugin (see
`docs/decisions/0002`) and is committed deliberately, as a public-portfolio signal ("we dogfooded
our architect here").

## The one rule that governs everything here

**This vault is orienting context, NOT a source of truth.** It *references* the authoritative
sources; it never overrides them and must never duplicate them. When the vault and an authoritative
source disagree, the **source wins** and the vault is the thing that's drifted (fix the vault):

| For… | The authority is… | The vault gives you… |
|---|---|---|
| what we build | `story-forge-poc-spec.md` (the spec) | the *architectural reading* of it + a §-reference |
| the plan / decisions made | `docs/PLAN_SHORT.md` (Decided) + `docs/decisions/` (ADRs) | the *open* decisions, framed as register entries |
| what the code does today | the code in `backend/`, `frontend/` | the as-built-vs-planned honesty note |
| per-directory conventions | the seven `AGENTS.md` files | — |

So read the vault to **understand consequences and orient**; act from the spec, the plans, and the
code.

## How to navigate

Start at **`INDEX.md`** — the regenerated map of the whole vault. From there:

- **`PROJECT.md`** — the stable inputs: identity, personas/trust, business drivers, and the
  **source-of-truth registry** (the single most useful table — where each kind of fact authoritatively lives).
- **`overview.md`** — the nine-layer system-altitude analysis, grounded in the as-built present.
- **`invariants.md`** — the rules that must never break (INV-1…INV-10; INV-8 retired at M3.S4a, INV-10
  minted at Graph-quality S5b-be) and **where each is
  enforced** vs. where the guard is still planned. Read this before touching the LLM/agent/graph
  layers; it tells you which guarantees you're on the hook for.
- **`open-questions.md`** — framed-but-unresolved decisions (OQ-N) + the operator's next-step
  priority queue. If you're about to make a design call, check here first — it may already be framed.
- **`glossary/`** — one note per architectural term (EN + PL), cross-linked into a knowledge graph;
  the index is `glossary/glossary.md`. Use it when a term in another note is unfamiliar.
- **`proposals/`** — per-feature nine-layer decompositions (`decompose-requirement` output). Read
  the relevant one as a "what could go wrong" briefing before building that feature — e.g.
  `m2s2-llm-router-budget-cap.md` for the router/budget work: data-flow diagram, decision register,
  and the full "but what if" edge-case enumeration.
- **`reports/`** — dated `review-architecture` sweeps (drift, invariant near-misses, stale ADRs).
  The latest one is the current health snapshot. **Findings don't rot:** a report's **blocker/risk**
  findings are *triaged* at the next `/resume-session` (step 3c) — each must be resolved or tracked
  (an `open-questions.md` OQ, a `docs/PLAN_SHORT.md` cross-cutting item, or the handoff) before the
  session moves on. That step 3c ↔ the report's own actionable-findings discipline (`review-architecture`
  SKILL step 7) is the producer/consumer pairing that gives a report the forcing function it otherwise
  lacks (a report, unlike a decision register or a CVE waiver, can't block a build or re-red CI by itself).
- **`decisions/`** — vault-framed ADRs *once confirmed* (host-project ADRs still live in
  `docs/decisions/`). The plugin's *own* framework ADRs are separate, under `meta-architect/decisions/`.
- **`state-machines/`** — explicit state+transition models (guards enforce invariants; effects
  write evidence). Populated as lifecycles are drawn.

`[[wikilinks]]` connect notes; the vault is Obsidian-compatible if you want to wander it as a graph.

## Who writes here, and how it stays honest

- **The three `meta-architect:*` skills write the notes** (`initialize` / `decompose-requirement` /
  `review-architecture`). They write **only Markdown, only into this vault, never production code.**
- **Humans and other agents read it as orienting context** and may correct it like any repo doc —
  but the architect re-syncs derived notes (`INDEX.md`, the glossary index) on its next run, so
  prefer fixing the *source* note over the generated map. **Targeted correction vs re-derivation:**
  a small, *known* fix to a source note (a stale fact, a corrected framing) is a fine **hand-edit** —
  the next `review-architecture` sweep re-syncs the derived map and any per-feature `proposals/`
  that echo it. Reserve **routing the fix to a `review-architecture` sweep** for *broad* drift or a
  re-derivation across many notes, where the skill's systematic pass is the point. (Session 57
  routed a multi-note reconciliation to the sweep; Session 59 hand-fixed two source notes and
  tracked the residual `proposals/` / `INDEX` for the next sweep — both correct.)
- **This `AGENTS.md` is a host-repo convention file, not a vault note** — the architect skills treat
  it as read-only (it has no `type:` frontmatter and isn't one of the note kinds they manage).
- **When the vault drifts from reality, that's a bug to file, not a fact to trust** — the
  `review-architecture` sweep exists to catch exactly that; its latest `reports/` entry says how
  honest the vault currently is.
- **In a `proposals/` decompose, don't assert an exact *forward* invariant-enumeration ordinal** —
  e.g. "the ninth witnessed instance" of INV-9's human-reached-writer paths (`invariants.md`
  numbers them). At decompose time that count is a `verify-at-build`-class claim about *future*
  build state: the build assigns the real ordinal, and slices reorder. Phrase it non-numerically
  ("another witnessed path; the build assigns the ordinal") and let the build (or a later
  `review-architecture` sweep) fill the number. (Earned S5→S6: the S5 proposal guessed "eighth"
  and it landed *seventh*; the S6 proposal's "ninth" was caught by `/review-pr` and softened — a
  wrong count in a portfolio design doc reads as a real error to a stranger.)

## Status of the workflow integration (read this before assuming a ritual runs the architect)

Integration is **evidence-based** (ADR 0002 §4): wire a skill into a ritual only once living with it
shows the wiring earns its place. As of **Session 68** the first such wiring has landed —
**`review-architecture` runs at every milestone roll** (`/wrap-session §5c`), paired with the existing
`/resume-session §3c` triage of its report. The evidence: the Public-readiness milestone-roll retro
showed an architecture sweep that only runs when a human remembers it rots like any un-triggered
artifact, and real vault drift (PreNER-as-live-stage) reached the roll uncaught. The other two skills —
`decompose-requirement` and `initialize-project-architecture` — stay **event-triggered** (a "step 0"
decomposition of a genuinely branchy feature; first-contact bootstrap), **not** ritual-wired; no
evidence yet calls for that. Invoke those by hand when the work calls for it.

**`/resume-session` step 3c is the consumer half, not the producer.** It triages a report that
*already exists* (walks its blocker/risk findings, checks each is tracked) — it never *runs* the
architect. The producer (running `review-architecture`) is now wired at the milestone roll;
step 3c reads what that run — or any hand-invoked sweep — left behind. Likewise `/resume-session`
step 1 reads the handoff a sweep may have seeded — same producer/consumer distinction.
