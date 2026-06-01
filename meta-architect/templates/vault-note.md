<!--
  CANONICAL VAULT-NOTE TEMPLATE  —  meta-architect
  Every note written into the architecture vault opens with the five frontmatter
  fields below, in this order. This file is the single source of truth for that
  shape: the agent prompt and all three skills derive their note headers from here.
  It is a TEMPLATE asset (read via ${CLAUDE_PLUGIN_ROOT}/templates/), not itself a
  vault note — hence these HTML comments, which a real note would not carry.
-->
---
# type — what KIND of note this is. Acts as a discriminator so the vault is queryable.
# one of:
#   index | project | overview | adr | component | state-machine | invariants
#   glossary | glossary-term | learning-log | open-questions | proposal | review | changelog
type: component

# slug — kebab-case, globally unique, IDENTICAL to the filename without ".md".
# This is the note's address. Wikilinks elsewhere ([[this-slug]]) resolve to it.
slug: example-slug

# updated — YYYY-MM-DD, the date the agent last wrote this note.
# This is the freshness signal `review-architecture` uses to spot stale notes.
updated: 2026-06-01

# status — where this note sits in its lifecycle. A state machine over the document
# itself (see lesson). one of:
#   draft | proposed | accepted | superseded | deprecated | living
status: draft

# related — declared structural edges to other notes, as [[wikilinks]]. This is what
# turns the vault into a graph you can WANDER in Obsidian: each entry renders as a
# clickable link in the Properties panel and as an edge in graph view. The agent reads
# the same field by stripping the [[ ]] to recover the slug. May be empty.
# (Body prose links incidental mentions as [[slug]] too; both feed Obsidian's graph.)
related:
  - "[[some-related-slug]]"
  - "[[another-slug]]"
---

# <Human-readable title>

<Body. The FIRST appearance of any architectural term is defined inline — EN + PL where
useful, e.g. "trust boundary (granica zaufania) — the line at which data crosses between
contexts of different trust levels." Subsequent appearances may link to the glossary with
[[trust-boundary]] instead of redefining.>
