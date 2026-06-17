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
- **`invariants.md`** — the rules that must never break (INV-1…INV-9; INV-8 retired at M3.S4a) and **where each is
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
  prefer fixing the *source* note over the generated map.
- **This `AGENTS.md` is a host-repo convention file, not a vault note** — the architect skills treat
  it as read-only (it has no `type:` frontmatter and isn't one of the note kinds they manage).
- **When the vault drifts from reality, that's a bug to file, not a fact to trust** — the
  `review-architecture` sweep exists to catch exactly that; its latest `reports/` entry says how
  honest the vault currently is.

## Status of the workflow integration (read this before assuming a ritual runs the architect)

The architect skills are **deliberately NOT wired into** `/resume-session`, `/wrap-session`, or
`/review-pr` yet — that integration is deferred until we've lived with the vault (ADR 0002 §4). So
nothing runs them automatically; invoke them by hand when the work calls for it (a milestone-boundary
drift sweep, or a "step 0" decomposition of a genuinely branchy feature). The evidence for whether/
how to wire them is being gathered run-by-run — see the `reports/` and `proposals/` history.

**`/resume-session` step 3c is not a counter-example.** It triages a report that *already exists* (walks
its blocker/risk findings, checks each is tracked) — it never *runs* the architect. Reading an artifact
the architect left behind is the consumer side of a producer/consumer pairing; auto-*running* a
`meta-architect:*` skill from a ritual is the wiring that stays deferred (ADR 0002 §4). Likewise
`/resume-session` step 1 reads the handoff a human-invoked sweep may have seeded — same distinction.
