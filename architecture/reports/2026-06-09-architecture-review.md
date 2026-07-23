---
type: review
slug: 2026-06-09-architecture-review
updated: 2026-06-10
status: living
related: ["[[overview]]", "[[invariants]]", "[[open-questions]]", "[[m2s3-extraction-agent]]", "[[2026-06-02-architecture-review-post-m2s2]]", "[[idempotency]]", "[[poison-message]]", "[[source-of-truth]]"]
---

# Architecture review — 2026-06-09 (pre-M2.S4 drift + forward sweep)

> **Owner-requested before building M2.S4** ("check the architecture against the plan, as we did
> before the previous milestone, to make sure everything is in proper place and makes sense"). Two
> jobs: (1) a **drift check** of the vault against the as-built code now that **M2.S3** (PR #42,
> `ExtractionAgent`) and the **SCA gate** (PR #44) have merged since the last sweep
> (`[[2026-06-02-architecture-review-post-m2s2]]`); (2) a **forward lens** onto **M2.S4 — Neo4j
> writes, no dedupe** (spec §9 M2), the next session, checking the plan against the invariants and
> open questions before a line is written.

**Scope.** As-built M2.S3 (`agents/extraction_agent.py`, the candidate schemas,
`adapters/llm/{base,ollama,openrouter,router}.py`'s `ProviderResponseError` path, `api/stories.py`)
+ the SCA gate, vs the vault's claims (`overview.md`, `invariants.md`, `open-questions.md`,
`[[m2s3-extraction-agent]]`). Forward: `docs/PLAN_SHORT.md` Session 4 block + spec §3.2/§6.4/§9 vs
INV-1/3/8, OQ-1, OQ-2.

Severity legend: **blocker** (resolve before dependent work) · **risk** (will bite if unaddressed) ·
**watch** (track; not yet urgent).

## Headline

**No blockers. One forward `risk` worth fixing before M2.S4 (already half-caught this morning), and a
cluster of `watch`-level drift where the M2.S3 merge left three update-in-place notes lagging the
code.** The vault's *regenerated* surface (`INDEX.md`) and the *proposals* are fresh and honest —
INDEX already records OQ-10 "closed in code", M2.S3 built, OQ-13 closed. But three **update-in-place**
notes that weren't touched (or only half-touched) at the M2.S3 wrap now misstate the as-built: most
visibly **`overview.md`'s "honest snapshot" still lists M2.S2 *and* M2.S3 as "planned, not yet
built"** — three sessions stale, and it's the system-altitude note a newcomer reads first. The
forward lens found **no contradiction** between the M2.S4 plan and the invariants — the plan is
well-aligned — but it surfaces one data-layer trap (the `entity_mentions` table the vault's data model
assumes **does not exist in the schema yet**) and confirms the two framed M2.S4 decisions (OQ-1
two-store consistency, OQ-2 resumable batch) are still the owner's to settle as the session opens.

## 1. Drift — vault vs reality

- **`risk` — `overview.md` is three sessions stale (`updated: 2026-06-02`).** Its "Current as-built
  state (the honest snapshot)" lists **M0 → M2.S1** as built and **M2.S2 → M2.S6** as "planned, not
  yet built" — but **M2.S2 (PR #36) and M2.S3 (PR #42) are both merged.** The note even says of
  M2.S2 "only `adapters/llm/{base,ollama}.py` exist", which is now flatly wrong (the router, the
  OpenRouter adapter, the cost ledger, the status endpoint, and the whole `ExtractionAgent` all
  exist). This is the vault's *orientation* note (`architecture/AGENTS.md`: "orienting context");
  a stale snapshot here actively misorients the next contributor. **Recommend:** move M2.S2 + M2.S3
  into "built and merged", trim the planned list to M2.S4 → M2.S6, refresh `updated`. (Owner
  approval — I did not edit it; see Hand-off.)
- **`watch` — INV-5 still calls OQ-10 an open coverage gap that "closes in M2.S3".** `invariants.md`
  (`updated: 2026-06-08`) reads: *"Known coverage gap (OQ-10, closes in M2.S3): … Do not read INV-5 as
  already total until the typed `ProviderResponseError` path … lands and the router records + fails
  over on it."* It **landed** in PR #42: `ProviderResponseError` is defined in `base.py:39`, raised by
  both adapters at the envelope-unwrap point (incl. the null-`content` case — `ollama.py:101`,
  `openrouter.py:118`), and caught by the router (`router.py:142`, record-failure + fail-over). INV-5
  is now total over the edges the router handles. **Recommend:** flip the gap clause to as-built
  (OQ-10 closed), as the prior sweep flipped INV-2/5/7.
- **`watch` — `open-questions.md` OQ-10 isn't struck-closed, but `INDEX.md` says it is.** INDEX line
  71 reads "OQ-10 now **closed in code**"; the OQ-10 entry in `open-questions.md` still ends at
  "**Accepted (owner, 2026-06-08): build in M2.S3 … OQ-10 stays open only until the code lands**" with
  no closure line — unlike OQ-13, which got a "✅ **Closed in code 2026-06-08 (PR #44)**" line. Two
  homes of one fact now disagree (the [[source-of-truth]] discipline the project itself enforces).
  **Recommend:** add the matching "✅ Closed in code 2026-06-08 (PR #42)" line to OQ-10.

## 2. Source-of-truth conflicts

- **`risk` (forward, host-doc) — the data model assumes an `entity_mentions` table that the schema
  doesn't have.** `overview.md` Layer 4 says "Postgres owns … the entity↔paragraph occurrences", and
  OQ-1 frames the two-store seam around the Neo4j-entity ↔ Postgres-`entity_mentions` back-reference —
  both correct as *design*. But the table **does not exist in the migrations**: the only Alembic
  revisions are `create_document_tree` (projects/stories/chapters/scenes/paragraphs) and
  `create_llm_calls`; `entity_mentions` lives **only** in spec §6.4. The `docs/PLAN_SHORT.md` handoff
  asserted three times that the table "is already in M1's schema (verify before re-migrating)" — a
  false claim that would have led the M2.S4 implementer to skip the migration and fail at the
  paragraph↔entity insert. **Already corrected in `docs/PLAN_SHORT.md` this morning** (the handoff now
  says "write a new Alembic migration + extend `EXPECTED_TABLES`"). Flagged here so the vault's own
  data-model notes stay honest: the occurrences store is **created in M2.S4**, not inherited. No vault
  edit needed beyond awareness; the spec (§6.4) is the authority and is right.

## 3. Missing / undrecorded decision records

- **None new.** The independent-commit ledger choice (flagged in the prior sweep) is now recorded in
  INV-5's "Record durability (as-built)" clause. The SCA gate is decision-recorded
  (`[[backend-dependency-advisory-scan]]` + spec §6.7). The M2.S3 decisions (D1–D6) are recorded in
  `[[m2s3-extraction-agent]]` §5 + `docs/PLAN_SHORT.md` Decided. The agent layer's *shape* asymmetry
  is a `watch` below, not a missing ADR.

## 4. Invariant violations & near-misses (fresh "but what if")

- **`watch` — INV-4 (open-world types) is correctly enforced as-built.** `EntityCandidate.type` and
  `RelationCandidate.predicate` are free `str` with no `Enum` (`extraction_agent.py:68,93`); a
  never-before-seen type validates. No near-miss — confirmed first enforcer holds. (The invariant note
  says "Enforced at: … (M2.S3)"; reads as planned tense but is now true — fold into the same as-built
  refresh.)
- **`risk` — INV-8 (no-dedupe) has no enforcer until M2.S4, and its proof is a *test* that must be
  written.** Through M2 "two identical extractions must produce two nodes" is a contract with **no
  code holding it yet** — M2.S4 is the first enforcer. The danger is a well-meaning early dedupe (a
  `MERGE` instead of `CREATE` in the Cypher, a "skip if name exists" guard) sneaking in because it
  *looks* like an improvement. The plan already names the test (Session 4: "verify the no-dedupe
  property"); keep it as a **failing test written first**, and make the write use `CREATE`, never
  `MERGE`-on-name. This is the invariant most exposed by the upcoming session.
- **`watch` — INV-1 (human-in-the-loop) stays correctly absent in M2.** M2.S4 writes every candidate
  with no gate (INV-8), which is the deliberate temporary stance; INV-1's guard is M3. No action —
  confirming the plan doesn't accidentally introduce a half-built gate.
- **`watch` — INV-6 redaction-before-logging, carried forward.** Unchanged from the prior sweep: the
  log-redaction middleware INV-6 names still doesn't exist, and M2.S4's batch driver is a likely place
  to add diagnostic logging (a paused/failed batch wants a log line). If anything logs a provider
  error body before redaction exists, it's fail-open-by-sequencing. Build redaction before the first
  provider-error log line.

## 5. Structural rot

- **`watch` — the agent layer now has two collaborator shapes.** `ChunkingAgent` takes a raw
  `LLMProvider`; `ExtractionAgent` takes the `LLMRouter` (via a `_Router` Protocol). The proposal
  (`[[m2s3-extraction-agent]]` §3) flagged this as "worth deciding whether ChunkingAgent migrates to
  the router too" — still open, still not rot, but the asymmetry is now real in the tree. Decide at or
  after M2.S6 (integration polish); not M2.S4's concern.
- **`watch` — envelope-unwrap + `ProviderResponseError` is duplicated across `ollama.py` and
  `openrouter.py`** (near-identical raise-on-missing-key / raise-on-null-content blocks). Rule-of-three
  isn't tripped yet (two adapters), but a third direct vendor adapter (M2.S6) is the moment to extract
  a shared envelope-unwrap helper in `base.py`. Tracked in `docs/PLAN_SHORT.md` cross-cutting; noted
  here against the M2.S6 vendor-adapter work.
- **No orphans / ghost references / stale ADRs** in the vault graph. INDEX glossary count (20) matches
  the on-disk glossary notes; proposals and reports are all reachable.

## 6. Forward lens — M2.S4 plan vs architecture

The owner asked to check the plan against the architecture before building. **Result: aligned, no
contradiction.** M2.S4 respects INV-1 (no gate yet, correct), INV-3 (writes are reversible by
design), INV-8 (every candidate a fresh node), and lands OQ-1 + the OQ-2 batch driver exactly where
the proposals placed them. The forward lens surfaces **decisions to confirm and traps to avoid, not
conflicts**:

- **`watch` — OQ-1 (two-store write consistency) is now live and needs the owner's call.** M2.S4 is
  the first time the Neo4j entity write and the Postgres `entity_mentions` write coexist with **no
  shared transaction**. *But what if* the Neo4j write succeeds and the Postgres mention fails (or
  vice-versa)? The proposal's standing recommendation is **(c) accept eventual inconsistency at PoC
  scale** + a cheap "verify graph↔mentions" check, with write-order **Neo4j-then-Postgres** so the
  graph (identity) leads. Confirm this as the M2.S4 approach (or pick the outbox/repair option) before
  wiring the writes — it's a real seam, framed but unresolved.
- **`watch` — OQ-2 (resumable batch driver) lands here per `[[m2s3-extraction-agent]]` D5.** The
  router *raises* `BudgetExceededError`/`QuotaExhaustedError` mid-call and the agent *propagates*; M2.S4
  is where a batch driver must **catch** them and pause *resumably*, using the persisted graph write +
  `entity_mentions` as the durable "last-done" checkpoint (see [[idempotency]] — per-paragraph stable
  ids make resume-from-last-done cheap). Confirm the driver owns the catch, not the agent.
- **`risk` — the new graph-write API path must map router exceptions to HTTP, or it 500s.**
  `api/stories.py` today catches only `ChunkingError → 502` (`stories.py:234`); it does **not** catch
  the router's re-raised `ProviderResponseError` / transport error (all providers exhausted) or
  `BudgetExceededError`/`QuotaExhaustedError` — those would surface as an uncaught **500**, not a typed
  502/402-style outcome the frontend can model (`backend/CLAUDE.md` "Declare every non-2xx outcome").
  The M2.S4 ingest/extract endpoint inherits this: enumerate the router's exit exceptions and map each
  to a declared `responses=` status. The existing chunking-path gap is tracked cross-cutting; M2.S4
  adds a second consumer, so fix the pattern once. (Watch→risk specifically for the *new* path being
  built.)
- **`watch` — the blank-relation-fields validator is a confirmed as-built gap, correctly scheduled for
  M2.S4.** `RelationCandidate.subject/predicate/object` are plain `str` with **no** non-empty
  validator (`extraction_agent.py:92-94`), unlike `EntityCandidate.candidate_name` which has one
  (`:74-81`). A blank-field relation would write a malformed edge to Neo4j. The plan folds the
  validator into M2.S4 (the PR-#42 external-review gap); keep it on the checklist — it's exactly the
  kind of thing the graph write makes consequential.

## 7. Concepts worth studying (the teaching payoff)

- **Dual-write consistency without distributed transactions** — OQ-1 is a textbook instance: two
  stores that can't share a transaction, so a crash between writes leaves them disagreeing. The
  grown-up answers are the **transactional outbox pattern** (record intent in store A's transaction,
  a relay replays it into store B) and **idempotent retries keyed on a stable id**. We're choosing the
  PoC-scale shortcut (accept-and-reconcile), but knowing the named patterns is what lets you justify
  the shortcut rather than stumble into it. See [[idempotency]].
- **`CREATE` vs `MERGE` in Cypher** — the whole of INV-8 lives in this one-keyword choice. `MERGE`
  is "match-or-create" (idempotent on the match pattern → silent dedupe); `CREATE` always makes a new
  node. M2.S4 must use `CREATE` to *honour* the temporary no-dedupe invariant — the same keyword that
  M3's cascade will deliberately *not* use. Worth understanding the semantics before writing the first
  query, because the wrong default quietly violates a named invariant.
- **Doc freshness as a state machine over the artifact** — the drift this sweep found is not random:
  the *regenerated* note (INDEX) self-heals each run, while *update-in-place* notes (overview,
  invariants) only move when a human edits them, so they lag at exactly the moments nobody re-read
  them. This is why `review-architecture` exists and why the post-M2.S2 sweep argued for wiring it into
  `/wrap-session` — the freshness guarantee should fire on the same event (a merge) that creates the
  drift. Re-read `[[2026-06-02-architecture-review-post-m2s2]]` §6.

## Hand-off

- **No blockers.** One forward `risk` (the `entity_mentions` table absence) is **already fixed in the
  plan** this morning; the other `risk`s are the M2.S4 build's to honour (INV-8 via `CREATE`-not-
  `MERGE`; router-exceptions→HTTP on the new path). All else is `watch`.
- **Vault edits this sweep makes** (trail only, never code): adds the drift findings to
  `open-questions.md` (deduped), appends `learning-log.md` + `CHANGELOG.md`. It does **not** unilaterally
  edit `overview.md` / `invariants.md` — those are recommended below for owner approval (report-only
  discipline; the prior sweep folded its flips only after explicit approval).
- **Recommended for the owner (the drift fixes) — ✅ approved + folded 2026-06-09 (see [[changelog]]):**
  1. `overview.md`: M2.S2 + M2.S3 moved to "built and merged", planned list trimmed, Monitoring station
     flipped to `✅ partial`, `updated` refreshed. ✅
  2. `invariants.md`: INV-5's OQ-10 gap clause flipped to as-built (closed); INV-4's planned tense
     dropped. ✅
  3. `open-questions.md`: OQ-10's "✅ Closed in code 2026-06-08 (PR #42)" line added to match INDEX. ✅
  4. *(audit extra)* `PROJECT.md` Identity line + `m2s2-llm-router-budget-cap.md` stale `route()`
     depiction also corrected. ✅
- **Decisions still the owner's, before/at M2.S4 (framed, not resolved):** OQ-1 write-order +
  consistency posture; OQ-2 batch-driver ownership of the pause-and-ask catcher.
- **Architect deep-dives still on offer (unchanged):** draw the **LLM-call state machine**
  (`state-machines/`, the first one) and/or the first `components/` note (OQ-C). Neither blocks M2.S4.
