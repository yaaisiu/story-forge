---
type: glossary-term
slug: open-world-ontology
updated: 2026-06-02
status: living
related: ["[[cascade-matching]]"]
---

# open-world ontology (ontologia otwarta)

**Definition:** a type system where the set of kinds (entity types, relation types) is **not
fixed up front** and is allowed to grow as real data demands — the opposite of a closed
enumeration decided in advance.

**Answers:** "must I know every category before I start, or can the schema learn?"

**First encountered in:** [[invariants]]

Story Forge's entities and relations are open-world (§3.2): `type` is a free string with
*examples that constrain but do not restrict*. Enforced as [[invariants]] INV-4 — code must
never "tidy" `type` into a hard enum, because the first new story would break it.
