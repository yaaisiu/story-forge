---
type: learning-log
slug: learning-log
updated: 2026-06-08
status: living
related: []
---

# Learning log

Append-only. One line per architectural concept the first time real work surfaces it — `date ·
term · appeared in [[note]] · why it matters for THIS project`. New lines go at the bottom.

- 2026-06-02 · trust boundary · [[project]] · Story Forge's only real one is machine ↔ LLM provider — knowing that removes a whole class of auth concerns and focuses security on text egress.
- 2026-06-02 · source of truth · [[project]] · the vault's defining discipline — reference the spec/plans/code, never copy; two copies that can drift is the bug.
- 2026-06-02 · C4 model / altitude · [[overview]] · forces every note to declare its zoom level, so a concern loud at one level isn't lost at another.
- 2026-06-02 · agent (this project's sense) · [[overview]] · the testable unit the ingest pipeline composes from; "agents not functions" is what makes the model usage legible to a portfolio reader.
- 2026-06-02 · open-world ontology · [[overview]] · entity/relation types must stay extensible strings — the first new story breaks any hard enum.
- 2026-06-02 · state machine · [[overview]] · the candidate + ingest-job lifecycles are best modelled as states+transitions; guards enforce invariants, effects write evidence.
- 2026-06-02 · fail-closed · [[overview]] · the governing error stance — on uncertainty, fall through to the human / refuse, never proceed.
- 2026-06-02 · compliance / audit layer · [[overview]] · distinct from security; loud here because edit_history is a self-imposed, append-only evidence trail meant to become a dataset.
- 2026-06-02 · idempotency · [[open-questions]] · the key to resumable ingest after a mid-story failure — stable ids make a re-run safe.
- 2026-06-02 · invariant · [[invariants]] · a never-break contract with a named guard; an unenforced invariant is just a wish.
- 2026-06-02 · human-in-the-loop · [[invariants]] · the product's central stance — machine proposes, author commits; "no UI = no graph data".
- 2026-06-02 · cascade matching · [[overview]] · the core dedupe mechanism; cheap-deterministic-first, human-last; the project's loudest fail-closed surface.
- 2026-06-02 · model-tier routing · [[overview]] · one provider interface, three tiers, within-tier failover; local+cloud-free share one Ollama adapter (config, not code fork).
- 2026-06-02 · deterministic-first · [[overview]] · prefer deterministic/user-assisted methods before an LLM — visible in PreNER and in the cascade's free first stages.
- 2026-06-02 · outbox / saga (dual-write) · [[2026-06-02-architecture-review]] · the canonical answers to OQ-1's no-shared-transaction problem; worth reading even to consciously reject for the PoC.
- 2026-06-02 · fail-closed sequencing · [[2026-06-02-architecture-review]] · INV-5's "cap check before dispatch" — fail-closed is about ordering (check→act), not just the default value; a guard after the irreversible effect is decorative.
- 2026-06-02 · caller-asserted vs system-derived provenance · [[2026-06-02-architecture-review]] · INV-7's `model_tier` is echoed from the caller, not proven; audit/cost labels are only trustworthy when derived from the actor.
- 2026-06-02 · ADR lifecycle (amend/supersede/annotate) · [[2026-06-02-architecture-review]] · an accepted ADR is append-only — annotate or supersede, never edit Consequences; ADR 0001's stale quota line is the live example.
- 2026-06-02 · failover (within-tier) · [[failover]] · route around a dead/rate-limited provider without failing the call or crossing a cost tier; which error triggers it (429/5xx yes, 401 no) is the real design.
- 2026-06-02 · TOCTOU · [[toctou]] · the budget cap's guard is only best-effort under concurrency; naming the bounded overshoot is the honest move vs pretending the cap is exact.
- 2026-06-02 · envelope-vs-schema error · [[m2s2-llm-router-budget-cap]] · a 200 with a malformed wrapper ≠ valid wrapper with bad JSON; they need opposite handling (failover provider vs retry prompt).
- 2026-06-02 · out-of-band / write-ahead audit logging · [[2026-06-02-architecture-review-post-m2s2]] · a record that must survive the failure it describes can't share the transaction that rolls back on that failure — why `PostgresCostStore` commits on its own connection; the grown-up version is the outbox pattern.
- 2026-06-02 · poison message / dead-letter · [[2026-06-02-architecture-review-post-m2s2]] · the malformed-200 envelope is input that breaks the consumer on every retry; the discipline is quarantine-and-move-on (record + failover), never retry-forever the same dead provider.
- 2026-06-02 · totality over a state machine · [[2026-06-02-architecture-review-post-m2s2]] · a robust router maps every error class to exactly one of the four terminal states; both PR-#36 bugs were "a class mapped to the wrong terminal" — enumerating the state machine is the cure.
- 2026-06-02 · prompt injection (structural vs semantic) · [[prompt-injection]] · structural injection is closed *by construction* (message list from a trusted template, text-as-data); semantic injection is only *bounded* (conservative prompt + schema + human review) — ExtractionAgent's OQ-5 gate hangs on stating which guarantee you actually have.
- 2026-06-08 · software composition analysis (SCA) · [[software-composition-analysis]] · scanning deps against a known-vuln DB is a *different* control from the freshness soak: soak stops a hijacked release, SCA stops a known-vulnerable one — and a *pin-time* check can't replace a *continuous* one because vulns are disclosed after you pin (the starlette case).
- 2026-06-08 · defense in depth · [[defense-in-depth]] · Dependabot (post-merge, advisory) + a CI SCA gate (pre-merge, blocking) are kept *both* on purpose — independent nets that lag and fail differently cover each other's gaps; the redundancy is the feature, not waste.
