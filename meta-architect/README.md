# meta-architect

> A domain-agnostic **product architect** you drop into any repository. It produces *only*
> Markdown design artefacts — ADRs, decision registers, component notes, invariants, state
> machines, reviews — into an Obsidian-compatible vault. It **never writes production code**.
> And it **teaches** architectural vocabulary and reasoning as a side-effect of doing real
> work, because the artefacts it leaves behind are meant to make you a better architect.

## Status — graduated (this is Story Forge's vendored copy)

This plugin was **incubated inside the Story Forge repository** — used, refined, and stress-tested
here — and has now **graduated** to its own distributable home,
[`claude-dev-tooling`](https://github.com/yaaisiu/claude-dev-tooling). This `meta-architect/`
directory is Story Forge's **vendored copy**, which SF consumes in-place and re-syncs deliberately
rather than auto-installing (see [`UPSTREAM.md`](./UPSTREAM.md)). It was always built as a
self-contained plugin directory, so graduating was just moving the folder — no rewrite. See
[`decisions/`](./decisions) for the plugin's own design decisions, and
`docs/decisions/0002-incubate-meta-architect-in-repo.md` for the incubation-and-graduation record.

## Philosophy

**Architecture is the projection of consequences, not the design of features.** A requirement
is a stone dropped in water; the architect's job is to trace the ripple — through users,
data, failure modes, security, audit, operations — *before* code is written. The output is
never "the requirement restated"; it is a list of components, a state register, named
invariants, decisions with their consequences, and acknowledged gaps to take back to the
product owner.

The **golden line** governs everything it produces:

> A feature is only good once we know **who can use it**, **how it is enforced**, **what
> happens on failure**, and **what evidence remains after the fact**.

Its tone is **translator-and-mentor**, never peer-architect-talking-down. It defines each term
on first use (English + Polish where useful), and it gets more concise automatically as your
glossary fills — it teaches more when you know less, and steps back as you grow.

## The method

### Nine layers
Every requirement is passed through nine layers — each asks a different question, and an
unconsidered layer is a blind spot:

1. **User / personas** — who uses it, at what trust level
2. **Business** — why we're doing it (compliance, risk, revenue, a deal)
3. **Domain** — the ubiquitous language; the nouns and verbs
4. **Data** — entities, fields, ownership, foreign keys
5. **Behavior** — state machines, transitions, terminal states
6. **Errors** — failure modes; fail-open vs fail-closed
7. **Security** — threat model, abuse paths
8. **Compliance / Audit** — provable adherence and the durable evidence trail
9. **Operations** — observability, support diagnostics, runbooks

(Layer 8 was split from Security deliberately — see [`decisions/0001`](./decisions/0001-nine-layer-model.md).)

### Nine stations
A separate checklist for a *feature's enforcement lifecycle*:
**Identity → Intent → Policy → Decision → Access → Monitoring → Evidence → Expiry → Review.**
An empty station is a design gap. Layers are dimensions of *analysis*; stations are a checklist
of *controls* — they meet at Evidence/Review but run on different axes.

### The rest of the doctrine
- **Source of truth** — every fact has exactly one authoritative home; the vault *references*
  existing docs, never duplicates them.
- **Invariants** — rules the system must never break; each is a design contract.
- **State machines over naïve statuses** — model guards (where invariants are enforced) and
  effects (where evidence is created).
- **"But what if"** — relentless edge-case enumeration is the primary discovery tool.
- **Decision register, not recommendations** — open decisions are framed (Context / Options /
  My proposal / Open questions); the architect proposes, the human decides.
- **ADRs in MADR** — lean by default, escalating to the fuller form when a decision has 3+ live
  options or crosses a security/data boundary.

## The vault

The architect writes into `./architecture/` (configurable). Every note carries five-field
frontmatter (`type / slug / updated / status / related`), cross-links with `[[wikilinks]]`,
and follows one of three **update modes** so the vault grows predictably:

| Mode | Behaviour | Examples |
|------|-----------|----------|
| regenerated | rebuilt each run (derived) | `INDEX.md`, the `glossary.md` index |
| append-only | add, never edit | `CHANGELOG.md`, `learning-log.md`, ADRs |
| update-in-place | edit surgically, log the change | `PROJECT.md`, components, invariants, state-machines |

```
architecture/
├── INDEX.md              # generated map of the vault
├── PROJECT.md            # identity, personas, business, source-of-truth registry, calibration
├── overview.md           # the system-altitude nine-layer pass
├── decisions/            # MADR ADRs
├── components/           # one note per major component
├── state-machines/       # one note per stateful entity
├── proposals/            # one note per decomposed requirement
├── reports/              # dated architecture-review reports
├── glossary/             # one note per term → a real knowledge graph
├── glossary.md           # generated index of the glossary
├── invariants.md         # running list of design contracts
├── open-questions.md     # unresolved decisions
├── learning-log.md       # chronological log of concepts you've met
└── CHANGELOG.md          # audit trail of the architect's own writes
```

## The educational model

The teaching is not a lecture bolted on — it *is* the artefacts:

- **Terms defined on first use**, inline, EN + PL where useful.
- **The glossary is a knowledge graph** — one note per term, cross-linked, wander-able in
  Obsidian. After a few months it's a personal reference work in its own right (see
  [`decisions/0002`](./decisions/0002-glossary-as-knowledge-graph.md)).
- **A learning log** records each concept you met, where, and why it mattered *here*.
- **Progressive disclosure** — verbosity scales down automatically as your glossary fills.
- **Reviews end with "concepts worth studying"** — pointers for going deeper.

## Install

This is a **Claude Code plugin**, not an Agent SDK app: Claude Code *is* the runtime, and the
architect is skills + a persona that run inside it.

**Inside Story Forge (already wired):** committed in `.claude/settings.json` via
`extraKnownMarketplaces` (a relative `./meta-architect` path) + `enabledPlugins`. Anyone who
clones and trusts the repo is offered the plugin. After a settings change, run `/reload-plugins`.

**In another repo (or after extraction):**
```bash
claude plugin marketplace add ./path/to/meta-architect
claude plugin install meta-architect@meta-architect-local
# then, inside Claude Code:
/reload-plugins
```

## The three skills

| Skill | When it fires | What it does |
|-------|---------------|--------------|
| `initialize-project-architecture` | once, first contact | scans the repo, interviews you (one round), and scaffolds the vault with an initial nine-layer pass |
| `decompose-requirement` | per feature/change | runs the nine layers + nine stations, produces a proposal note (data-flow, state, invariants, decision register, "but what if", PO gaps) |
| `review-architecture` | periodic / on-demand | sweeps for drift, source-of-truth conflicts, missing ADRs, invariant violations, orphans, stale ADRs; report-only |

All three are interactive and human-in-the-loop: they propose, you decide. None writes an ADR
or resolves a decision without your confirmation.

## Intended workflow integration — *hypothesis, not yet wired*

The goal is for the architect to be a *phase of how you build*, not three commands you remember
to type. The current **hypothesis** (to be validated after the first real `initialize` run,
then implemented) is three touchpoints in the host repo's rituals:

- **Bootstrap** — the start-of-session ritual detects a missing `architecture/` vault and
  offers to initialize.
- **Front of the feature flow** — `decompose-requirement` runs at "step 0", before the
  failing test, so the decomposition feeds the spec and tests.
- **Drift sweep** — `review-architecture` runs at session-wrap / pre-merge, complementing
  code-level PR review at the architecture altitude.

These are deliberately **not** hard-wired yet: wiring the process before living with the tool
once would be premature structure. We validate, then integrate.

## How this differs from other architect-style agents

Most "architect" agents give one-shot advice in chat. This one:
- writes **durable artefacts into a versioned vault**, not disposable chat;
- keeps a **decision register, not recommendations** — it never resolves your decisions for you;
- carries a **teaching loop** (glossary graph + learning log + progressive disclosure) as a
  first-class output, not an afterthought;
- **refuses to write production code** — it stays an architect, by construction.
