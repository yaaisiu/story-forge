---
type: glossary-term
slug: poison-message
updated: 2026-06-02
status: living
related: ["[[failover]]", "[[idempotency]]"]
---

# poison message / dead-letter (zatruta wiadomość / martwa kolejka)

**Definition:** an input that breaks the consumer the *same way on every retry* — so retrying it is
futile and a naïve retry-forever loop wedges the whole pipeline on one bad item. The discipline is
**quarantine-and-move-on**: record it, set it aside (a "dead-letter"), continue with the rest.

**Answers:** "what do I do with input that will fail no matter how many times I retry it?"

**First encountered in:** [[2026-06-02-architecture-review-post-m2s2]] (named there); made concrete in
[[m2s3-extraction-agent]] as the OQ-10 malformed-`200`-envelope case.

In Story Forge the live instance is OQ-10: a provider returning `200` with a broken body. Retrying the
*same prompt* against the *same provider* will fail identically — so the right handling is **not** the
agent's prompt-retry but the router's [[failover]]: record a failure row, move to the next provider,
don't loop. This is exactly why envelope-malformed (→ failover the provider) and schema-invalid (→
retry the prompt) need opposite handling — one is a poison message, the other is a transient that a
second attempt can fix.
