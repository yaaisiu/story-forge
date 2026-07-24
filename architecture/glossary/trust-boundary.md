---
type: glossary-term
slug: trust-boundary
updated: 2026-06-02
status: living
related: ["[[fail-closed]]", "[[source-of-truth]]"]
---

# trust boundary

**Definition:** the line at which data crosses between two contexts that trust each other to
different degrees — every such crossing is where validation and authorization must happen.

**Answers:** "where does control change hands, so where must I check?"

**First encountered in:** [[project]]

In Story Forge there is *no* human trust boundary (single local user). The one real boundary is
**machine ↔ external LLM provider**: the instant the author's text is sent to a cloud model it
leaves the fully-trusted local context. That crossing, not a login, is where the Security and
Compliance layers concentrate (see [[invariants]] INV-2).
