# PLAN_LONG.md — Strategic plan

> Stable, big-picture. Update only when scope genuinely shifts. Source: §9 of `story-forge-poc-spec.md`.

## V1 — Ingest + Graph + Viewer

The user can upload a draft, chunk it, extract entities/relations with the cascade matching pipeline, review and accept them into Neo4j, and explore the resulting graph. As a side effect, the codebase showcases the agent + multi-model architecture to portfolio visitors.

- [x] **Milestone 0 — Setup** (2-3 days) — completed 2026-05-19
  Docker Compose, FastAPI + React skeleton, CI with security checks, plan files, root and directory-level CLAUDE.md.
- [x] **Milestone 1 — Upload & structure** (3-5 days) — completed 2026-05-26
  Upload endpoint, language detection, docx/md/txt parsing, ChunkingAgent (local Ollama + Ollama Cloud), manual chunking UI, outline view.
- [ ] **Milestone 2 — Basic extraction** (5-7 days)
  Three-tier LLM abstraction (local Ollama, Ollama Cloud, paid cloud via OpenRouter — the preferred paid route; see `docs/decisions/0003`), ExtractionAgent with JSON-schema validation, PreNERAgent (spaCy), Neo4j writes without dedupe, cytoscape graph viewer, budget tracking, agent activity panel.
- [ ] **Milestone 3 — Cascade matching** (5-7 days)
  MatchingAgent (fuzzy + embeddings), JudgeAgent (LLM-as-judge), review queue UI with keyboard navigation.
- [ ] **Milestone 4 — V1 polish** (5-7 days)
  Inline highlights, side panel, manual annotation, properties/relations edit, multi-story, world graph parent.

### Data flywheel — a custom NER model, later

The PreNERAgent (M2) uses stock spaCy pipelines (`pl_core_news_lg`, `en_core_web_lg`)
as a deliberately recall-first, low-precision baseline. Every entity the user accepts,
relabels, or corrects through the §3.3 review loop is training data. Once enough has
accumulated, **finetune a custom spaCy model** on the corrected "Wody Święte" corpus and
swap it in behind the same agent — at which point a `NerPipeline` Protocol earns its
place (see `backend/src/story_forge/CLAUDE.md`). Not scheduled; a direction the
architecture is kept ready for.

## V2 — Editing

Three modes (inline / dialog / diff), full edit_history pipeline. New agents: `InlineEditAgent`, `DialogAgent`, `DiffRewriteAgent`. Spec §4. Timeline after V1.

## V3 — Style rewriting

Style presets, transfer from example, per-project style anchor. New agent: `StyleTransferAgent`. Spec §5. Timeline after V2.

## Security & DevSecOps hardening — later

Directions surfaced from a practitioner's DevSecOps notes (2026-06-08), kept ready but
not scheduled. The **governing principle** behind them: *security research takes
precedence over feature work* — a security-relevant change is researched (and, when it
touches the §6.7 baseline, decomposed + spec-amended) **before** other changes ship,
not folded in afterwards. Story Forge already practises a partial form of this via the
stop-and-amend-spec flow and the `meta-architect:decompose-requirement` pass that
produced the M2 backend SCA gate (`osv-scanner` vs `uv.lock`); the items below extend it.

- **Adopt Anthropic's `security-review` as a standing gate.** Wire the published
  Anthropic security-review (the `/security-review` skill and/or its GitHub Action) into
  the review flow as a routine pass on security-relevant diffs — fastest built by
  starting from Anthropic's own repo rather than hand-rolling. Complements, does not
  replace, `/review-pr` + `/code-review`.
- **Automated architecture-conformance gate.** Turn the meta-architect vault's
  invariants + the layering rules (`backend/src/story_forge/CLAUDE.md`) into an
  *automated* check (does the code still obey domain-imports-nothing,
  agents-use-the-`LLMProvider`-Protocol, prompts-in-`.j2`, LLM-output-Pydantic-validated?),
  rather than relying only on the reviewer-invoked `/review-pr` §4 greps and the manual
  `meta-architect:review-architecture` drift sweep.

---

## When this file changes

A change here means the project's strategic scope shifted. Likely causes: a milestone proved infeasible, a new milestone became necessary, or priorities reordered. Every change here should be reflected in `PLAN_SHORT.md` and possibly in the spec.
