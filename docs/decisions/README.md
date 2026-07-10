# Architecture Decision Records

One file per decision, numbered in the order it was made. Each ADR captures the context, the
choice, and its consequences. The log is **append-only**: a decision that is later revised is
marked *superseded* (in whole or in part) and the superseding ADR is linked — the original text
stays, so the record shows how the design evolved.

| # | Decision | Status |
|---|----------|--------|
| [0001](0001-three-tier-llm-strategy.md) | Three-tier LLM strategy | Accepted — provider-priority/quota consequences superseded in part by [0003](0003-llm-router-provider-order-and-budget.md); the three-tier model stands |
| [0002](0002-incubate-meta-architect-in-repo.md) | Incubate the meta-architect plugin in-repo | Accepted |
| [0003](0003-llm-router-provider-order-and-budget.md) | LLM router: provider order, hand-rolled adapters, control-first budget posture | Accepted |
| [0004](0004-intercept-before-write.md) | Intercept-before-write: the cascade stages, the human commits | Accepted |
| [0005](0005-relation-write-under-human-gate.md) | Relation edges are written under an explicit human gate | Accepted |
| [0006](0006-edit-committed-graph-under-human-gate.md) | Committed graph state is edited under explicit human-reached handlers (INV-9 broadened) | Accepted |
| [0007](0007-graph-mutations-and-grouped-undo-log.md) | Entity merge/delete/undo are grouped, reversible operations under the human gate | Accepted |
| [0008](0008-manual-correction-overlay-storage.md) | Manual correction in the reader: an overlay storage model + reconciled highlights | Accepted |
| [0009](0009-branch-protection-ruleset.md) | Branch protection on `main` via a repository ruleset | Accepted |
| [0010](0010-duplicate-suggestion-dismissal-store.md) | Persisting duplicate-suggestion dismissals: a staging-side pair store (graph-quality S4a) | Accepted |
| [0011](0011-edge-surrogate-handle-and-atomic-rekey.md) | A stable surrogate handle (`edge_uid`) for edges + atomic server-side edge re-key (graph-quality S5b-be) | Accepted |
