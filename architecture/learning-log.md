---
type: learning-log
slug: learning-log
updated: 2026-06-02
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
