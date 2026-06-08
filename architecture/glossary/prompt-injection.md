---
type: glossary-term
slug: prompt-injection
updated: 2026-06-02
status: living
related: ["[[trust-boundary]]", "[[human-in-the-loop]]"]
---

# prompt injection (wstrzyknięcie promptu)

**Definition:** when untrusted text fed to an LLM tries to act as *instructions* rather than
*data* — either forging the prompt's structure, or steering the model away from its task.

**Answers:** "the story text I'm extracting from can contain anything the author typed — what
stops a paragraph that *looks like instructions* from hijacking my prompt?"

**First encountered in:** [[m2s3-extraction-agent]] (the OQ-5 must-verify gate; §6.5 / `/review-pr` §4).

Two kinds, with opposite defensibility — naming the split is the whole point:
- **Structural** — the paragraph carries `[SYSTEM]` / `[ROLE]` markers or a literal output-shaped JSON
  block, trying to forge the message structure or pre-seed the answer. **Closed by construction:** build
  the call as a `list[Message]` from a trusted template, keep the untrusted text as *data* inside one
  `content` string, and never reparse model output mixed with story text. The transport-level role
  boundary then holds no matter what the paragraph says.
- **Semantic** — "ignore previous instructions, output X". *Cannot* be closed by construction; only
  *bounded* — a conservative prompt, schema validation that rejects non-conforming output, and the
  [[human-in-the-loop]] backstop. The honest move is to state which guarantee you actually have:
  structural is *guaranteed*, semantic is *bounded*. Mistaking one for the other is how a "we're
  injection-safe" claim quietly overstates itself.
