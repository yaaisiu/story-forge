---
type: glossary-term
slug: direct-manipulation
updated: 2026-07-08
status: living
related:
  - "[[graph-canvas-editing]]"
  - "[[graph-curation-surface]]"
  - "[[backend-for-frontend]]"
---

# direct manipulation (bezpośrednia manipulacja)

**Definition:** a UI pattern where the user acts on the **object itself, in place** — select the thing on
screen and edit it *there* — rather than describing the change in a separate form, dialog, or command
pane. The object is continuously visible, the action is a gesture on it, and the result shows on the same
surface. The term is Ben Shneiderman's (1982); the opposite is *indirection* — edit the world through a
console/panel that lives somewhere else.

**Answers:** "should the author clean up a graph node/edge on the graph itself, or over in a separate
reader pane?"

**First encountered in:** [[graph-canvas-editing]]

Why it matters *here*: Graph-quality S5 makes the graph canvas the editing surface (the owner's stated
emphasis — curate *where you see the problem*, §3 S5), which is direct manipulation applied to a knowledge
graph. The pattern is not just UX flavour — it *drives an architecture call*: because the author edits on
the canvas, S5 should **reuse the editing panel that already does the writes** (the reader's
`ReaderEntityPanel` + its [[backend-for-frontend]] hooks) rather than fork a second, graph-native editor
(graph-canvas-editing DM-S5-1). The discipline it teaches: a UX principle can select the cheapest
architecture — "edit in place" means "surface the existing write plumbing on this canvas," not "build new
write plumbing for this canvas."
