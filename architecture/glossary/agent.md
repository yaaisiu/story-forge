---
type: glossary-term
slug: agent
updated: 2026-06-02
status: living
related: ["[[model-tier-routing]]"]
---

# agent (agent — in Story Forge's sense)

**Definition:** a thin, individually-testable module that owns exactly one logical task and
bundles its own prompt template, its output schema, its preferred model tier, and the
orchestration logic that calls the router.

**Answers:** "what is the unit we compose the LLM pipeline out of?"

**First encountered in:** [[overview]]

Story Forge's ingest pipeline is a small catalog of agents — `ChunkingAgent`, `PreNERAgent`,
`ExtractionAgent`, `MatchingAgent`, `JudgeAgent`, `ReviewQueueService` (§6.5). "Agents not
functions" because each owns its prompt+schema as first-class, git-versioned, mock-testable
artefacts — and the structure makes *which model does what* legible to a portfolio reader. (Note:
this is the project's local sense; not every agent here calls an LLM — PreNER and Matching are
deterministic.)
