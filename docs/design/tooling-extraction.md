# Design note — extracting the Story Forge tooling as portable plugins

> **Status:** APPROVED (Session 84); build underway. **Slice 1 done** — Session 85, `meta-architect`
> graduated to `yaaisiu/claude-dev-tooling` (PRs #194 + #195). Author: session 84 (2026-07-13). Owner
> directive (BACKLOG "Distribute the meta-architect skills", Session-83 escalation). This is a
> *design + packaging* unit, not a test-first code build.
>
> **Refinement — 2026-07-13 (Session 85, owner):** for the **session-workflow rituals**, Story Forge
> **keeps its own bespoke `.claude/skills/` permanently and is NOT migrated onto the exported
> `dev-rituals`** (path A). The generic `dev-rituals` plugin is built **for the owner's other repos**;
> SF genericizes *from* its skills as source material but its working copies are never touched or
> replaced. This narrows §7 (SF vendors **`meta-architect` only**, not the rituals) and shrinks §9
> slice 5 (no SF rituals migration). See the §7 and §9 update notes below.

## 1. Why

The owner's other repositories are mostly **private projects he wants to make public**, but
first each needs the same treatment Story Forge got: adaptation, polish, documentation,
security hardening, and a working iteration loop. Story Forge has grown a toolchain that does
exactly this — the `meta-architect` architecture plugin and a set of `.claude/skills/` rituals
(session loop, PR review, security-gate treadmill, docs). Right now that toolchain is **welded
to Story Forge** and can't be reused elsewhere. The goal: **package it as portable Claude Code
plugins, installable into any repo**, so "apply the Story-Forge treatment" becomes a one-command
setup.

## 2. What the owner wants (from the Session-84 interview)

1. **All of it portable** — meta-architect, the session-workflow loop, `review-pr`, and the
   infra/docs skills. Not a subset.
2. **A review-and-integrate skill is the keystone requirement** — a skill that *surveys a target
   repo and threads the tooling in deliberately, not blindly.* This is the genuinely-new piece;
   everything else is extraction + genericizing.
3. **Architecture discipline is the near-universal must-have; the rest of the loop is
   case-by-case.** The tooling can't be all-or-nothing — integration must *recommend and
   selectively enable* what fits each repo.
4. **Target repos are all kinds of stacks** (similar/smaller/larger), **Python almost always
   present.** Genericizing must be real (parameterize the SF-coupled bits), not cosmetic.
5. **SF keeps its own version but records where it came from.** The generic plugins get
   generalized for *any* workflow; generic changes might not fit SF, so SF **vendors its own
   adapted copies with a provenance pointer upstream** rather than auto-installing from the
   marketplace (which could break SF when the generic version moves). This resolves the standing
   Session-76 "how does SF keep consuming them" question.

## 3. Current state (grounded — the BACKLOG premise is partly stale)

- **`meta-architect/` is already a checked-in, self-contained plugin** (17 tracked files):
  `.claude-plugin/plugin.json` (v0.1.0) + `.claude-plugin/marketplace.json`. Its README says it
  is *"incubated inside Story Forge… built as a self-contained plugin directory so that
  'graduating' it later is just moving the folder to its own repo — no rewrite."* The marketplace
  manifest itself is described as *"Local incubation marketplace… before extraction to its own
  repository."* → **Plan step "carve meta-architect into its own plugin" is structurally done;
  the remaining work is the physical move to its own git repo.**
- **SF already dogfoods the plugin via a local `directory` marketplace** —
  `.claude/settings.json`:
  ```json
  "extraKnownMarketplaces": { "meta-architect-local": { "source": { "source": "directory", "path": "./meta-architect" } } },
  "enabledPlugins": { "meta-architect@meta-architect-local": true }
  ```
  So the install mechanism (local marketplace → enabled plugin) is **proven in this repo.**
- **The rituals are plain `.claude/skills/` skills, NOT a plugin** (8 skills, auto-discovered).
  To be marketplace-distributable they need to be wrapped in a plugin directory (a
  `.claude-plugin/plugin.json` + a `marketplace.json`), mirroring meta-architect.
- **`docs/decisions/0002-incubate-meta-architect-in-repo.md`** records *why* meta-architect lives
  in-repo — the extraction will supersede/extend that ADR.

## 4. Deliverables (three plugins + one new skill)

All three ship in **one tooling monorepo** (`claude-dev-tooling`, per D2):

1. **`meta-architect` plugin** — graduate the existing `meta-architect/` folder into the monorepo.
   Already plugin-shaped; the work is the move + updating SF's settings to point at the graduated
   source (per the consumption model, §7).
2. **`dev-rituals` plugin** — a new plugin wrapping the genericized `.claude/skills/` rituals.
   The higher-value, harder extraction: decide *skill by skill* what is **universal doctrine** vs
   a **Story-Forge parameter**, and genericize the coupled bits (§5). Includes the keystone
   `review-and-integrate` skill (§6).
3. **One `marketplace.json`** at the monorepo root listing both plugins, so a single
   `/plugin marketplace add <git-url>` → `/plugin install` works in any repo.

## 5. Asset classification — universal doctrine vs SF-parameter, skill by skill

This is the core of the extraction: for each skill, what genericizes trivially, what needs a
parameter, and what is deeply SF-coupled. Grounded in a full read of every SKILL.md.

| Skill | Verdict | What's universal | What's an SF parameter / coupling |
|---|---|---|---|
| **decompose-requirement** | 🟢 already-generic | the whole skill (uses `${CLAUDE_PLUGIN_ROOT}`, configurable vault root, *references* host docs) | only teaching anecdotes name SF ("M4.S3a", "PR #34") — harmless |
| **review-architecture** | 🟢 already-generic | the whole sweep | its report-triage forcing-function currently lives in SF's `resume-session §3c` — needs a home in the target repo |
| **initialize-project-architecture** | 🟢 already-generic | the whole bootstrap — its job *is* to run against an unknown repo | none |
| **retro** | 🟡 light-param | reflect → propose → surface-one-at-a-time → apply-with-hygiene → report | plan-file paths, milestone/archive vocabulary, merge hygiene |
| **add-dependency** | 🟡 light-param | registry-age + advisory-check *method* (any Python/JS repo) | the **14-day soak** number, `check_dependency_age.py` hook, the spaCy-wheel appendix |
| **pin-image** | 🟡 light-param | Docker tag-date lookup + dockerized Trivy scan + OS-vs-bundled-CVE call | the **7-day soak**, `infra/trivy/` waiver layout, compose+ci as the tag homes, SF service names |
| **document-code** | 🟡 light-param | Explore-survey → conservative doctrine → general-purpose write → diff-driven update | doc-home paths (`docs/code/*`), SF layer taxonomy, the bundled `code-scribe.md` doctrine (ships alongside) |
| **resume-session** | 🔴 heavy | the *skeleton*: read handoff → verify anchors → survey git → report drift | the handoff-block **schema**, SF doc topology, and the whole §3b waiver / §3c architecture-report / §3d bloat sub-steps (≈half the skill) |
| **wrap-session** | 🔴 heavy | the mirror skeleton + the retro/roll prompt | green-state **gate commands** (uv/ruff/mypy/pytest, vite), the plan structure (Decided/Blocked/Done/cross-cutting), milestone-roll archive mechanics |
| **review-pr** | 🔴 heavy | §1 correctness/bug taxonomy (transferable *patterns*) | the entire project lens: §2 spec-appendix fidelity, §4 `domain/agents/adapters/api` layering, §5 §6.7 security gates, §6 test layout |
| **triage-advisory** | 🔴 heavy | the *lifecycle concept*: fix-first → time-boxed waiver → drop-revisit (no ignore forgotten) | every concrete step — OSV+Trivy+npm-audit stack, pinned scanner versions, `infra/` waiver registers, the soak numbers, the two sibling skills |

**Reading of the table:** the **meta-architect trio graduates as-is** ("move the folder"). The
**four light-param skills** (`retro`, `add-dependency`, `pin-image`, `document-code`) need a small
config surface: *soak days + waiver/register paths + verify hook + doc
homes*. The **four heavy skills** are **not a parameterization but a rewrite** — separate a
portable *skeleton* from a project-specific *config + lens* layer. Two structural consequences:

- The heavy skills encode SF's **doc topology** (the handoff-block contract, `PLAN_SHORT/LONG/
  ARCHIVE`, Decided/Blocked/Done) and **toolchain** (the exact green-state commands, the OSV/
  Trivy/npm-audit gates). Genericizing = defining a *portable ritual skeleton* + a per-repo
  **profile** that supplies the doc paths, the section vocabulary, and the gate commands.
- They also carry the **most SF-earned anecdotal lessons** (dozens of `Session N` / `PR #N`
  references). Those are transferable as *patterns* but not literal steps — the generic version
  keeps the pattern, drops the anecdote (or moves it to an SF-only appendix).

**Parameterization mechanism (proposal):** the SF-specific values a genericized skill needs
(plan-file paths, spec path, the dependency-soak window, the security-gate tool + ignore-file
paths, the review docs to load) come from a small **per-repo config** the integration skill
writes — e.g. a `.claude/dev-rituals.config.json` or a documented block in the repo's
`CLAUDE.md`. A skill reads its parameters from there and falls back to sensible defaults. This
keeps the skill body universal and pushes every SF-ism into data the integration step fills in.

## 6. The keystone: a `review-and-integrate` skill

The owner's explicit requirement — thread the tooling into a repo *deliberately, not blindly.*
This is the analog, for the whole ritual stack, of what
`meta-architect:initialize-project-architecture` already does for the vault (scan repo →
interview → scaffold). **Per "reuse before building," model it on that skill rather than invent
from scratch** — it may even be a sibling in the same family.

Sketched behavior:
1. **Scan the target repo** — languages, stack, CI, existing docs/plans, test setup, whether it
   already has any of these skills or a `CLAUDE.md`.
2. **Recommend a fit** — which rituals make sense here (meta-architect near-always; the security
   treadmill only if there are pinned deps / images; `review-pr` scaled to whether a spec/plan
   exists; the session loop if the repo wants that discipline). Present the recommendation; the
   owner selects.
3. **Parameterize + wire in** — write the per-repo config (§5), enable the chosen plugins in
   `.claude/settings.json`, and drop the doctrine snippet into `CLAUDE.md`.
4. **Human-in-the-loop throughout** — recommend, don't impose; the owner confirms each enablement.

This makes "architecture is a must, the rest is case-by-case" (§2.3) a first-class behavior
rather than a manual chore.

## 7. Consumption model — how SF (and any repo) keeps using them

Owner's steer (§2.5): **SF vendors its own adapted copies with a provenance pointer upstream.**
Concretely:
- The **canonical generic** plugins live in the tooling monorepo (the graduated `meta-architect`,
  the new `dev-rituals`), published through its single marketplace (D2).
- **SF keeps in-repo copies** (meta-architect already is one; the rituals become one) and
  consumes them via the local `directory` marketplace it already uses — so SF is unaffected when
  the generic version moves.
- **Provenance is recorded, not auto-tracked** — each in-repo plugin notes its upstream
  marketplace URL + the version/commit it was vendored from, so a re-sync is a *deliberate* act,
  never an automatic pull that could break SF.
- **Other repos** install the canonical generic version straight from the marketplace (they have
  no reason to fork), unless/until they need to adapt — at which point they vendor + record
  provenance the same way.

> **Update — 2026-07-13 (Session 85, owner refinement):** the "SF keeps in-repo copies" bullet
> above applies to **`meta-architect` only** (done in slice 1 — a vendored copy consumed via the
> local marketplace, with `UPSTREAM.md` provenance). For the **rituals**, SF does **not** vendor a
> copy at all: it **keeps its existing bespoke `.claude/skills/` untouched**, and the exported
> `dev-rituals` plugin is built purely for other repos. So there is no vendored-rituals copy or
> rituals-provenance pointer in SF — the loose skills stay exactly as they are.

Rationale for not marketplace-installing into SF directly: the generic plugins will be
generalized for *any* workflow, and SF has accumulated SF-specific tuning; letting upstream
changes flow in automatically risks breaking the repo that is these tools' most demanding user.
Deliberate re-sync keeps SF stable while still recording the lineage the owner asked for.

## 8. Decisions (resolved by the owner, Session 84)

- **D1 — one `dev-rituals` plugin, not a split.** The security-gate cluster, the session loop,
  and review/docs all ship in a single plugin; the `review-and-integrate` skill enables
  individual skills selectively per repo. Owner steer: package it efficiently into one reusable
  repo, minimal ceremony — selectivity happens at integration time, not by fragmenting the
  distribution. (meta-architect stays its own separate plugin.)
- **D2 — one tooling monorepo.** A single repo (working name `claude-dev-tooling`) hosts **both**
  plugins (`meta-architect/`, `dev-rituals/`) **+ one `marketplace.json`**. One
  `/plugin marketplace add <git-url>` exposes both. Split into separate repos later only if a
  plugin genuinely needs independent versioning.
- **D3 — `review-pr` is adaptive.** Parameterize "this repo's source-of-truth docs"; run the
  full spec/plan-fidelity + layering lens when they exist, and **degrade gracefully to
  correctness + portfolio-hygiene** when they don't. Most useful across the owner's varied repos.
- **D4 — this session stops at the approved design.** The actual extraction (moving files,
  creating the monorepo, genericizing the heavy skills, building `review-and-integrate`,
  trial-install) is a **multi-session build** afterward, sliced per §9 — likely ~one session per
  deliverable.

**One design seam the survey surfaced (for the build):** `review-architecture`'s report has a
*consumer* — in SF, `resume-session §3c` triages it. When meta-architect graduates, a target repo
that installs it needs *something* to consume the architecture report, or findings rot. The
`review-and-integrate` skill (§6) should wire that forcing-function when it enables meta-architect
in a repo that also takes the session loop.

## 9. Proposed sequencing (build happens in later sessions, after design sign-off)

1. **Graduate `meta-architect`** into the monorepo + its marketplace + update SF's settings +
   supersede ADR 0002. (Lowest-risk; already plugin-shaped.)
2. **Genericize the rituals** into `dev-rituals` — skill by skill per the §5 table, with the
   per-repo config mechanism. The bulk of the work.
3. **Build the `review-and-integrate` skill** (§6).
4. **Trial-install into one older repo** (§2 acceptance test — does "apply the SF treatment"
   actually work end to end?).
5. **Reconcile SF** onto the consumption model (§7) + update BACKLOG/plan/ADR. **(Refined S85:
   this no longer includes migrating SF's rituals — under path A, SF keeps its bespoke
   `.claude/skills/`. Slice 5 shrinks to closing BACKLOG/plan + the design-note tidy; the
   `meta-architect` half was already reconciled in slice 1.)**

Throughout: **SF's own `.claude/skills/` are never touched by this extraction** (path A, Session 85).
Slice 2 genericizes *from* copies of them into the `dev-rituals` plugin; `/resume-session` and
`/wrap-session` keep running from SF's untouched working copies, so the "keep the rituals functional"
risk is handled by simply not modifying them.
