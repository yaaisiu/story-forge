<!--
  GLOSSARY-TERM TEMPLATE — a FULL NOTE: one concept = one note = one node in the graph.
  Lives in the vault at: architecture/glossary/<term-en-slug>.md
  This is what makes the glossary a real, wander-able knowledge graph instead of a flat list:
  each term is its own Obsidian node, and `related` draws true concept-to-concept edges.
  A generated glossary.md (type: glossary) indexes them all. Terms are deduped by slug and
  added organically — only when real work first surfaces them, never preloaded. The count of
  these notes is the signal that drives progressive disclosure.
-->
---
type: glossary-term
# slug = kebab-case of the ENGLISH term; filename matches. Other notes link it as [[slug]],
# which Obsidian resolves by filename regardless of the glossary/ folder.
slug: example-term
updated: 2026-06-01
status: living
# related = other glossary TERMS this concept connects to → real graph edges. Link each only
# ONCE and in one direction; Obsidian's backlinks panel gives you the reverse view for free.
related:
  - "[[a-related-term]]"
---

# <term-en> (<term-pl>)

**Definition:** <one line, plain language. If you can't say it in one line, you don't yet
understand it well enough to teach it.>

**Answers:** <the QUESTION this concept exists to answer — e.g. for "idempotency": "what
happens if this runs twice?". Name the question; that is how a word becomes a tool.>

**First encountered in:** [[<slug-of-the-artefact-where-it-first-appeared>]]

<Optional: one or two sentences of elaboration or a concrete example from THIS project — added
only once the term has earned more than its one-line definition.>
