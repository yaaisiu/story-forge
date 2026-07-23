---
type: review
slug: 2026-07-23-architecture-review
updated: 2026-07-23
status: living
related:
  - "[[overview]]"
  - "[[project]]"
  - "[[invariants]]"
  - "[[open-questions]]"
  - "[[m4-inline-highlights]]"
  - "[[graph-name-normalisation]]"
  - "[[2026-06-25-architecture-review]]"
---

# Architecture review — 2026-07-23 (Graph-quality → next-milestone roll)

**Scope.** The whole vault, read against the Graph-quality milestone (S0–S7, Sessions 68–100,
PRs #164–#223) and the current code. This is the **milestone-roll** sweep — the first run under the
ADR-0002 §4 wiring that makes `review-architecture` a standing roll step (`/wrap-session §5c`), with
`/resume-session §3c` as the triage consumer. It carried two **queued inputs** from the
`docs/PLAN_SHORT.md` cross-cutting list; both are now closed (see *Queued inputs*, below).

**Headline.** No blockers. The vault's two strategic notes had gone a **whole milestone stale** — both
still described the project as "now in a Public-readiness milestone" — which is precisely the drift class
that motivated wiring this sweep into the roll in the first place. Re-synced on sight. Three `risk`
findings follow; two of them are *already tracked* in `docs/BACKLOG.md` and are recorded here so the
architectural reading of them is on record, not because they are unhomed.

---

## Queued inputs (both closed)

### QI-1 · DM-IH-8 tooltip homes vs the amended spec §3.5 — **closed**

Session 100 amended spec §3.5: the reader tooltip now specifies a **graph-derived relation summary**
(up to three connections, one line per distinct neighbour, most-connected-neighbour first, `+N more`).
That supersedes **DM-IH-8**'s 2026-06-18 resolution ("(a) name + type + aliases now; a richer description
is the side-panel slice's job"). The spec and the code were reconciled at S7; the **vault** homes were
not, and only the `meta-architect:*` skills may write them (ADR 0002) — hence the queue.

Reconciled across **four** homes, all recorded as **superseded, not wrong**:

| Home | What changed |
|---|---|
| [[m4-inline-highlights]] — register banner | DM-IH-8 row now carries the `⟶ SUPERSEDED 2026-07-23` note |
| [[m4-inline-highlights]] — `### DM-IH-8` body | Full supersession block: what landed, why (a) was right for a read-only slice, and that the (c) LLM-summary rejection **still stands** (the new summary is derived, not generated) |
| [[m4-inline-highlights]] — Mermaid node + Requirement prose | Node relabelled; the design-time Requirement sentence kept verbatim with an inline supersession marker (history stays intact) |
| [[open-questions]] — the DM-IH-8 bullet | Supersession recorded with the spec §3.5 authority pointer |
| [[overview]] — M4.S1 as-built line | Now names the S7 summary alongside name+type+aliases |

The **architectural reading worth keeping**: DM-IH-8 was never a wrong call — it was a correct scoping
decision for a slice that had no derived-summary machinery, and it *explicitly* flagged the extension as
"cheap to add under (a)". What S7 actually found was that the **spec line had never been updated to match
the resolution**: §3.5 promised a "brief description" that no entity has ever carried, in any version of
the schema. So this is a *drift closure*, and the fix ran in the honest direction — the promise was made
real from data the graph already held, rather than quietly deleted.

### QI-2 · Session-59 motivation reframe residue — **closed, and the estimate was wrong both ways**

The cross-cutting item predicted "~6 files" of `proposals/*.md` still using **"personal tool"** as a
design-driver lens, naming `m2s2`, `m2s3`, `m3-cascade-matching`, `backend-dependency-advisory-scan` and
others. The actual state:

- **One** live home, not six: `proposals/m3-cascade-matching.md` — softened to "the authoring tool
  (designed-for, currently aspirational)" with a pointer to [[project]] Layer 2. (`CHANGELOG.md` also
  carries the phrase and stays verbatim: append-only history.)
- **But two homes the keyword grep could not see**, and they were the *worse* kind — genuine as-built
  overclaims rather than an analysis lens. [[m4-inline-highlights]] referred twice to **"the real 'Wody
  Święte' draft"** / "the real 'Wody Święte' corpus". There is no real draft; the content is
  LLM-generated sample material (App. B test fixture). Both corrected to name it as a fixture.

**This is a finding about method, not just content.** The Session-59 item's home list was derived by
grepping one phrase, and the residue that mattered most used *different words*. It is the vault-side
instance of the same lesson the host repo learned twice this milestone (Sessions 97 and 98) and recorded
at this roll in root `AGENTS.md`: a list of "the homes" is a starting point, not an inventory.

---

## Findings

### Drift — vault vs reality

**R-1 · `risk` (fixed on sight) — [[overview]] and [[project]] were a whole milestone stale.**
Both notes carried `updated: 2026-06-25` and stated the project "is now in a **Public-readiness**
milestone — portfolio/spec/doc polish before the next build milestone (Graph-quality, then V2 Editing)".
Public-readiness **closed at the Session-68 roll**, and the entire Graph-quality milestone — 8 slices, 33
sessions, PRs #164–#223, two new ADRs (0010, 0011) and a new invariant (INV-10) — was absent from the
vault's "honest as-built snapshot".

*Why it matters, and why it is a `risk` rather than a `watch`:* [[overview]]'s as-built section is the
note a stranger (or the next session) reads to learn what the system *is*. A reader arriving today would
have concluded that graph curation had not started. This is the **fifth** recurrence of doc-freshness
drift, and the second time it reached a **milestone roll** uncaught — the exact evidence that wired this
sweep into the roll (ADR 0002 §4).

*Resolved:* both notes re-synced and re-dated. [[overview]] gained a full Graph-quality section (S0–S7,
each with its defining finding) and a "Next" paragraph that records the fork as **deliberately unchosen**
and gated on its prerequisite. [[project]]'s identity paragraph now names the milestone as complete.

*The residual worth naming:* the mechanism that let it happen is unchanged. Vault writes stopped after
Session 91's register resolution; Sessions 92–100 shipped four build slices and produced **one** vault
edit (`invariants.md` at S6a-2). The roll wiring is the backstop, and it worked — but it means the vault
is honest at roll boundaries and progressively less honest in between. That is a *deliberate* tradeoff
(ADR 0002 kept `decompose`/`initialize` event-triggered and did not wire a per-slice update), so it is
recorded as a property, not a defect.

**R-2 · `watch` — the `updated:` frontmatter is unmaintained on 13 notes.**
A mechanical comparison of each note's `updated:` against the date of its last content-bearing commit
found **13 notes** whose body is newer than the freshness signal that describes it, e.g.
`invariants.md` (`2026-07-10` vs a `2026-07-15` S6a-2 edit — **corrected to 2026-07-15**),
`learning-log.md`, `glossary/glossary.md`, `proposals/graph-curation-surface.md`,
`proposals/backend-dependency-advisory-scan.md`, and eight glossary terms.

*Why it matters:* `updated:` is the vault's only cheap freshness signal, and §6b of this skill exists
specifically to stop the sweep from *leaking* that debt. When a third of the dated notes lie about their
own age, "is this note current?" stops being answerable without git. Not a blocker — no *content* is
wrong because of it — but the signal is decorative on those notes.

*Not mass-fixed deliberately:* setting 13 dates without reading each diff would be guessing which edits
were content-bearing. `invariants.md` was corrected because it is a core note and its diff was
unambiguous. **Concrete next move:** either accept the git log as the real freshness source and drop
`updated:` to a coarse signal, or make the bump a checked step wherever a note is edited outside a sweep.

### Source-of-truth conflicts

**S-1 · `watch` — `architecture/AGENTS.md` still says "INV-1…INV-9"; INV-10 shipped at S5b-be.**
The vault's own navigation file describes `invariants.md` as holding "INV-1…INV-9; INV-8 retired at
M3.S4a". **INV-10** ("an edge's `edge_uid` survives re-point, re-predicate, and merge") was minted at
Graph-quality S5b-be with an enforcer and tests, and `invariants.md` documents it correctly.

*This sweep cannot fix it.* `architecture/AGENTS.md` is a **host-repo convention file, not a vault
note** — it carries no `type:` frontmatter and the architect skills treat it as read-only, by that file's
own rule. So it is reported, not edited. **Concrete next move:** a one-token edit by a human or a
non-architect agent — "INV-1…INV-**10**" in `architecture/AGENTS.md`'s navigation bullet.

### Invariant violations & near-misses

No violations. Two **near-misses**, both concerning **INV-1** (human-in-the-loop on every entity
create/merge and every relation edge). Both are already tracked in `docs/BACKLOG.md` — recorded here for
the architectural reading, and so §3c triage can confirm the tracking rather than rediscover them.

**N-1 · `risk` — the normalise-names gate is *nominal*: the human approves what they cannot evaluate.**
S6's `/stories/:id/normalise-names` list presents a suggested synonym pair (`LOCATED_IN` ↔ `PINPOINTED`)
with a fold count and an arm-then-confirm rename. It shows **no evidence** — not one bearing edge, not one
source sentence. INV-1 holds *formally*: a human clicks, and nothing renames without that click. But the
invariant's **purpose** is that a human *decides*, and a decision made without the evidence to decide on
is a rubber stamp wearing a gate's clothes.

*Why this is the sharpest finding in the sweep:* the Graph-quality milestone's stated thesis — written
into its own goal in `docs/PLAN_SHORT.md` — is that **"the human gate is only as good as the context it
shows you"**, and its enabling insight is that bringing that context to the decision point is *cheap*
because the data already exists. S3 applied it (edge evidence). S4 applied it (type + aliases + a context
quote on every merge card). **S6 did not**, and the gap was found only when the owner used the feature on
the real graph in Session 100 — dumping the bearing edges by hand settled a decision in seconds that the
UI could not settle at all. A milestone's own thesis went unapplied to one of its own slices, and no
review caught it, because every review checked the slice against *its* register rather than against the
milestone's premise.

*Blast radius:* a predicate rename is a **graph-wide, N-edge write** (INV-10's first realized consumer).
It is grouped and reversible (INV-3), so this is a correctness-of-curation risk, not a data-loss one.

*Tracked:* `docs/BACKLOG.md`, flagged in the Session-100 handoff as a **promotion candidate** for the next
milestone rather than post-PoC polish. This report supports the promotion.

**N-2 · `risk` — the review-queue cursor is a bare index, so the gate can be *misaddressed*.**
`frontend/src/hooks/useReviewQueue.ts` tracks the selected row as a plain integer that is **clamped** on
re-render but never **re-anchored to the item's identity**. Any refetch that reorders or drops rows moves
the highlight under the author silently; a decision keyed to "the selected row" can then be persisted
against an item the author never looked at.

*The architectural shape:* this is a **TOCTOU** ([[toctou]]) at the human gate — the check (the author
reads the card) and the use (the author presses a key) are separated by a window in which a background
refetch can change what "selected" means. INV-1 asks that a human decide *each* write; an index-anchored
cursor cannot guarantee the human decided *this* write.

*Currently latent, and honestly assessed:* Session 100 built an optimistic row-drop that would have made
this acute (shrinking the window from a 14–18 s refetch to ~50 ms after a keypress) and **reverted it
before merge** when `/code-review` surfaced the interaction. Verification against the live dismissal log
showed real decisions land 1–8 s apart, far outside the current window. But the hazard is live on **all
four queues today**, on every refetch — the revert removed the amplifier, not the cause.

*Tracked:* `docs/BACKLOG.md` as *"instant repaint needs an identity-anchored cursor first"*, recorded as
the prerequisite gating any future optimistic-repaint work.

### Missing decision records

**None.** Both ADR-worthy calls of the milestone were recorded at their build slice, as their registers
required: `docs/decisions/0010-duplicate-suggestion-dismissal-store.md` (S4a) and
`0011-edge-surrogate-handle-and-atomic-rekey.md` (S5b-be). The choices that were deliberately *not*
escalated to ADRs — the `cytoscape-fcose` layout swap (DM-GN-2), the label-dismissal store reusing ADR
0010's design at label granularity (DM-NN-3) — are each recorded in their proposal register and in
`docs/PLAN_SHORT.md` Decided, which is the right altitude for them.

### Structural rot

**T-1 · `watch` — `components/` is still empty after 100 sessions.**
The vault has 19 `proposals/`, 3 `state-machines/`, 36 glossary terms, 9 reports — and **zero** component
notes, though `architecture/AGENTS.md` documents the folder and the meta-architect doctrine names
per-component as the altitude where Data, Errors, Security, Compliance/Audit and Operations dominate. The
vault has operated entirely at **System** altitude ([[overview]]) and **per-Feature** altitude
(`proposals/`), skipping **Component**.

*This may well be correct* — a single-user local app with 8 well-named agent modules may genuinely not
need a per-component layer, and inventing one would be ceremony. But an empty folder is an **unnamed empty
box**, and the vault's own house rule is to *name* the empty box rather than leave it blank. **Concrete
next move:** either write one sentence in `architecture/AGENTS.md` saying per-component notes are
deliberately not used and why, or populate the two components where the "but what if" would actually pay
— the `LLMRouter` (failover, budget, tier fallback) and `EntityEditService` (now eight witnessed
writer-paths under INV-9).

**T-2 · `watch` (fixed on sight) — one genuine ghost reference.**
`glossary/compensating-transaction.md` linked `[[idempotent]]`; the term note is `idempotency`. Repointed
to `[[idempotency|idempotent]]`. The other four slug-diff hits (`[[note]]`, `[[wikilinks]]`,
`[[wikilinked]]`) are the known format-placeholder false positives already documented in the 2026-06-02
report. **One orphan:** slug `index`, which nothing links *to* — expected, it is the root map.

### Fresh "but what if" — over what Graph-quality changed

**W-1 · `watch` — the S7 label-embedding cache is unbounded and deliberately cross-project.**
`LabelVocabularyReader._embeddings` is an app-lifetime `dict[str, list[float]]` keyed on the **bare
label**, explicitly shared across projects, never evicted. This is a *good* call and the code says why: a
label's vector depends on nothing but the string, so per-project keys would forfeit the sharing for
nothing. It took a vocabulary load from ~14 s to ~1.4 s.

Two consequences worth having on record rather than rediscovering:

- **It crosses the tenancy key.** [[multi-tenancy]] in this vault is `project_id`-as-property; this cache
  is the first structure that deliberately spans it. Harmless today — a type label is not private data,
  and there is one trusted local user (INV-2's persona justification) — but if multi-user ever arrives,
  this is a shared mutable structure sitting *below* the tenancy boundary, and it should be found by
  design rather than by incident.
- **No eviction.** Bounded in practice by how many distinct labels a graph accumulates (tens to hundreds;
  the real graph has 227 predicates / 45 types), so ~megabytes at worst. A `watch`, not a leak — but the
  bound is a property of the data, not of the code.

**W-2 · `watch` — the tooltip summary reads the whole project edge set per reader load.**
`summarise_relations` is fed by one `get_relations(project_id)` per reader load — the same read `/graph`
already performs, so it adds no *new* query shape, and it is the honest cost of the deliberately
**project-scoped** summary (spec §3.5). But it is O(project edges) on a *per-story* read, and it grows with
the whole world graph rather than with the story being read. Fine at PoC scale; the first thing to measure
if the reader ever feels slow on a large project. Recorded because the Session-100 lesson — *measure before
classifying a slowness report* — applies here in advance.

---

## Foundational inputs — for owner re-confirmation, not verification (§1b)

These are **owner-asserted** and no consistency check can validate them; the spec, vault and code all
faithfully echo whatever they say. Surfacing them, not asserting them:

1. **One persona, full trust, local; no human trust boundary** ([[project]] Layer 1). Still true? It is
   load-bearing — it removes authn/authz, tenancy and rate-limiting from the entire design, and W-1 above
   is the first structure that leans on it.
2. **Two business drivers, portfolio-primary with authoring aspirational.** Corrected in Session 59 and
   re-confirmed by this sweep's QI-2 pass. Still the honest weighting?
3. **The operator's self-described architecture-vocabulary level is "novice"** ([[project]] Calibration).
   After 100 sessions, 36 glossary terms and 19 feature decompositions, this is very likely stale — it is
   the input that sets the vault's teaching density, and it has never been revisited.

---

## Concepts worth studying

- **[[toctou]] (time-of-check to time-of-use)** — the shape behind N-2. Worth reading beyond its usual
  filesystem/security framing: the version that bites here is a *UI* TOCTOU, where the two ends of the
  race are a human's eye and a human's finger. The general fix is the one the backlog item names — key
  the action to the *identity* of the thing acted on, never to its position.
- **Nominal vs substantive controls** — the distinction underneath N-1. A control that is *present* and a
  control that is *effective* are different properties, and a checklist only ever measures the first. This
  is why the nine stations ask "present?" and then force you to say *where* — the "where" is what makes
  the answer falsifiable. Story Forge's own milestone thesis is a restatement of it.
- **Cache key scope and tenancy** — W-1 in general form. Reading on cache-key design (what belongs in a
  key, and what a key's *absence* implicitly asserts) pays off far beyond this case: a cache key is a
  claim about what a value depends on, and a wrong claim is invisible until two tenants disagree.
- **Documentation as a state machine** — the recurring motif behind R-1 and R-2 (this is its fifth
  recurrence). The productive framing is that a doc has *states* (fresh / stale / lying) and that only
  **transitions with forcing functions** keep it out of the bad ones. This vault now has exactly one such
  forcing function (the roll wiring), and R-1 is the evidence that one is enough to catch drift but not
  enough to prevent it.
