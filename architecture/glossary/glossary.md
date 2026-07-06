---
type: glossary
slug: glossary
updated: 2026-07-06
status: living
related: []
---

# Glossary index

The glossary is a **knowledge graph**, not a flat list: each term is its own note (a node) in
`glossary/`, cross-linked via `related` so concepts form a web you can wander in Obsidian. This
index is **regenerated** each run; the term notes are the source. Terms are added *organically* —
only when real work first surfaces them — and deduped by slug. Count today: **34**.

| Term (EN / PL) | Answers | Note |
|---|---|---|
| trust boundary / granica zaufania | where does control change hands? | [[trust-boundary]] |
| invariant / niezmiennik | what must stay true no matter what? | [[invariant]] |
| state machine / maszyna stanów | what states, which transitions? | [[state-machine]] |
| fail-closed / domyślnie zamknięty | proceed or stop on doubt? | [[fail-closed]] |
| human-in-the-loop / człowiek w pętli | who has the final say? | [[human-in-the-loop]] |
| idempotency / idempotentność | what if it runs twice? | [[idempotency]] |
| open-world ontology / ontologia otwarta | must I know every category up front? | [[open-world-ontology]] |
| source of truth / źródło prawdy | which copy is right? | [[source-of-truth]] |
| C4 model / model C4 | at what zoom level am I reasoning? | [[c4-model]] |
| agent (Story Forge sense) | the unit the LLM pipeline composes from | [[agent]] |
| cascade matching / kaskadowe dopasowanie | same entity, for how little spend? | [[cascade-matching]] |
| model-tier routing / routing po poziomach modeli | which model, and failover to what? | [[model-tier-routing]] |
| compliance / audit layer / warstwa zgodności | what evidence remains afterward? | [[compliance-audit-layer]] |
| deterministic-first / najpierw deterministycznie | do we actually need an LLM here? | [[prefer-deterministic]] |
| failover / przełączanie awaryjne | what happens when the provider is unavailable? | [[failover]] |
| TOCTOU / sprawdzenie-a-użycie | is this guard safe if two things run at once? | [[toctou]] |
| prompt injection / wstrzyknięcie promptu | can untrusted text act as instructions? | [[prompt-injection]] |
| poison message / zatruta wiadomość | what about input that fails every retry? | [[poison-message]] |
| software composition analysis / analiza składu oprogramowania | do any of our deps have a known vuln? | [[software-composition-analysis]] |
| defense in depth / obrona w głąb | if one control misses, does another catch it? | [[defense-in-depth]] |
| intra-batch deduplication / deduplikacja wewnątrz partii | why can't the queue merge dupes from one pass? | [[intra-batch-dedup]] |
| referential integrity / integralność referencyjna | why not write the edge the moment we see it? | [[referential-integrity]] |
| ego-graph / graf egocentryczny | how much of the graph is "around" this entity? | [[ego-graph]] |
| backend-for-frontend (BFF) | one endpoint per screen, or stitch in the client? | [[backend-for-frontend]] |
| lost update / zgubiona aktualizacja | what stops one edit silently erasing another? | [[lost-update]] |
| compensating transaction (saga undo) / transakcja kompensująca | how to undo across two stores with no shared transaction? | [[compensating-transaction]] |
| materialization / materializacja | derived-on-read or stored-and-addressable? | [[materialization]] |
| multi-tenancy / tenancy key / wielodostępność / klucz dzierżawy | which owner's slice does this query see? | [[multi-tenancy]] |
| surrogate key / klucz zastępczy | is this the same edge after I curate it? | [[surrogate-key]] |
| reification / reifikacja | how do I say something *about* a relationship? | [[reification]] |
| provenance / proweniencja | where in the text did this fact come from? | [[provenance]] |
| entity resolution / rozpoznawanie tożsamości encji | are these two names the same thing, and who decides? | [[entity-resolution]] |
| connected components / składowe spójne | A≈B and B≈C — is {A,B,C} one duplicate cluster? | [[connected-components]] |
| blocking / blokowanie | dedup is O(n²) — how to avoid comparing everything? | [[blocking]] |
