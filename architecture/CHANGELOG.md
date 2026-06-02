---
type: changelog
slug: changelog
updated: 2026-06-02
status: living
related: []
---

# Vault changelog

Append-only audit trail of writes into the vault. Newest entries at the top. History also lives
in `updated` fields (freshness) and git (diffs); this is the human-readable "what changed when".

## 2026-06-02 — `initialize-project-architecture` (first run, seed)

First live use of the meta-architect plugin on Story Forge. Created the vault at
`architecture/` (committed to git, per the init interview). Scaffolded:

- `PROJECT.md` — identity, personas/trust (single local user; the only trust boundary is machine ↔ LLM provider), business (personal tool + public portfolio, equal weight), source-of-truth registry, calibration (operator: novice → Scaffolded tier; both readers).
- `overview.md` — nine-layer system-altitude seed pass, grounded in the as-built present (M0→M2.S1 done; M2.S2+ planned); nine-station snapshot with empty boxes named (Monitoring not-yet-built, Expiry gap).
- `invariants.md` — 8 named invariants (INV-1 human-in-the-loop, INV-2 text-egress consent, INV-3 reversibility, INV-4 open-world types, INV-5 budget cap, INV-6 secrets/log redaction, INV-7 one-adapter-per-protocol, INV-8 temporary M2 no-dedupe).
- `open-questions.md` — operator priority queue (review-then-strategize), 5 vault-raised gaps (two-store consistency, ingest recovery, quota-exhausted UX, retention/Expiry, extraction injection pass), and a reference (not copy) to spec §10's ten questions.
- `glossary/` — 14 seed term notes + regenerated `glossary.md` index (trust-boundary, invariant, state-machine, fail-closed, human-in-the-loop, idempotency, open-world-ontology, source-of-truth, c4-model, agent, cascade-matching, model-tier-routing, compliance-audit-layer, prefer-deterministic).
- `learning-log.md` — 14 lines, one per concept taught this run.
- `INDEX.md` — regenerated vault map.
- Empty dirs (with `.gitkeep`): `decisions/`, `components/`, `state-machines/`, `proposals/`, `reports/`.

No production code touched. No ADR written (none confirmed). Sources of truth referenced, not
duplicated: `story-forge-poc-spec.md`, `docs/PLAN_*.md`, `docs/decisions/`, the seven
`AGENTS.md` files, the code.

**Review fold (same day, PR #30):** Codex flagged that `glossary/model-tier-routing.md` said
the router was "Built in M2.S2" while `overview.md` correctly lists M2.S2 as planned and the
repo has only `adapters/llm/{base,ollama}.py`. Reworded to "Planned for M2.S2 … not yet built".
Swept the whole vault for the same tense-overclaim class — this was the only instance.
