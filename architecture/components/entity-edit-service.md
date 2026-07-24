---
type: component
slug: entity-edit-service
updated: 2026-07-24
status: living
related: ["[[overview]]", "[[invariants]]", "[[graph-operation]]", "[[compensating-transaction]]", "[[candidate-lifecycle]]", "[[relation-lifecycle]]", "[[surrogate-key]]", "[[lost-update]]"]
---

# EntityEditService

Component-altitude note ([[c4-model]]) for `backend/src/story_forge/agents/entity_edit.py`
(`class EntityEditService`). The single service every human-initiated edit of **already-committed**
graph state passes through — and therefore the graph writer in the **third through eighth** witnessed
instances of **INV-9** (six of the eight). Spec §3.4/§3.5; ADRs 0006 (edit), 0007 (merge/delete/undo),
0008 (manual tagging), 0011 (name normalisation).

## Responsibility

Turn one human edit action into the grouped, **reversible** set of graph writes it implies — plus the
before→after evidence row that makes it undoable. (The many operations below share one reason to
change: "how a human-gated edit to committed graph state is applied and recorded.")

## Source of truth

Owns the **edit operation**, not the graph facts. Neo4j (via the `EntityGraphEditor` protocol) remains
the authority on the committed graph; Postgres `graph_edits` is the authority on *what was edited and
how to reverse it*, and this service owns the mapping from a human action → that grouped write + its
inverse. It also owns the **undo-stack semantics** (which operation is "live" and reversible). It does
**not** decide *whether* an edit is right (the human does — INV-1) nor normalise labels automatically
(INV-4 — predicate/type stay free strings; a rename is human-chosen, never code-collapsed).

## Interfaces

- **Exposes** (each reached **only** from an explicit human-reached API route):
  `edit_entity` · `add_relation` / `remove_relation` / `retarget_relation` · `merge_entities` ·
  `delete_entity` · `undo_last` · `tag_new_entity` + the manual mention/suppression mutators ·
  `rename_predicate` / `relabel_entity_type` (graph-wide name normalisation). Routes:
  `PATCH …/entities/{id}`, `POST`/`DELETE …/relations`, `PATCH …/relations/{edge_id}`,
  `POST …/entities/{id}/merge`, `DELETE …/entities/{id}`, `POST …/graph-edits/undo`,
  `POST …/paragraphs/{pid}/tags`, `POST …/label-vocabulary/rename`.
- **Consumes** three injected collaborators: `EntityGraphEditor` (the Neo4j writers —
  `create_entity`/`update_entity`/`relabel_entity_type`/`create_relation`/`delete_relation`/
  `delete_entity`), `EditEvidenceRepo` (the grouped `graph_edits` log), and `MentionRepo` (the
  Postgres mention/suppression layer).

## Invariants

- **INV-9 — the graph writer outside the cascade gates.** It is the only class that writes
  *already-committed* graph state, and every path into it is a human-reached handler (never an
  extraction/matching/judge stage). It grows INV-9's enumeration by *paths*, not writer classes
  (broaden-don't-mint, ADR 0006): instances **3** (post-commit edit), **4** (merge — destructive,
  multi-write), **5** (delete + the undo *reverser*), **6** (tag-as-new-entity), **7** (edge re-key),
  **8** (graph-wide rename — whose `relabel_entity_type` is the *one genuinely-new* graph-writer symbol
  the whole milestone added). The exact roster is enumerated in [[invariants]] INV-9 — read it there,
  don't restate a count here (it grows).
- **INV-3 — every operation is a grouped [[compensating-transaction]].** A single action may be N
  writes (a merge re-points every incident edge); all N land as one grouped, reversible `graph_edits`
  operation, and `undo_last` replays the inverse in reverse `seq`. See [[graph-operation]].
- **INV-10 — an edge's [[surrogate-key]] survives re-key.** `retarget_relation` / `rename_predicate`
  re-key an edge (delete-old + create-new, since the id is `uuid5(subject,predicate,object)`) while
  preserving its opaque `edge_uid`, so a future qualifier/reification is not severed by curation.
- **INV-1 — a human commits every write.** The service has no autonomous path; it is the *executor* of
  a decision a person already made at the gate.

## State

Owns the **operation undo stack** — model it as [[graph-operation]] (`applied → undone`; transition
`undo_last`, guarded against drift → 409). Its per-object edits also drive the self-transitions in
[[candidate-lifecycle]] (a committed-node edit) and [[relation-lifecycle]] (a committed-edge edit).
The service instance itself is otherwise stateless (all state is in Neo4j + `graph_edits`).

## Layer fingerprint

- **Security** — the most **destructive** surface in the system: merge and delete re-point or remove
  committed identity. There is no inter-user trust boundary (single full-trust persona), so the guard
  is **not** authz — it is INV-9 (only human-reached code writes here) plus per-op tenancy checks
  (`EntityNotFound` covers an entity belonging to another project). The abuse model is *mistake*, not
  *attacker*: the mitigations are reversibility (INV-3) and evidence, not access control.
- **Data sensitivity** — operates on the author's own graph + prose spans (internal, single-tenant).
  The `graph_edits` log stores before→after images of that same data; no third party, no egress
  (contrast [[llm-router]] — this component never crosses the [[trust-boundary]]).
- **Errors** — **fail-closed on drift**: `undo_last` refuses with `UndoConflict` (→409) rather than
  clobber a change made since the operation was recorded (a [[lost-update]] in reverse, ADR 0007); a
  stale-tab edit of a merged/deleted node raises `EntityNotFound`/`RelationEdgeNotFound` (→404); a
  self-merge raises `SelfMergeError` (→409) before any read. **Known Errors-layer debt (tracked):** the
  edit routes call `get_story`/`get_project` **outside** their declared-503 `try`, so a Postgres outage
  on that read 500s while the route declares 503 — a systemic `docs/PLAN_SHORT.md` cross-cutting item
  to fix in one focused pass over the edit routes.
- **Compliance / Audit** — "what remains after the fact" is the grouped `graph_edits` before→after row
  per operation: the reversibility substrate (INV-3) *and* part of the planned `edit_history`
  data-flywheel signal (distinct from operational logging, which does not exist yet).
- **Operations** — no operational logs today; the observable "what can be reversed right now" signal is
  the live undo stack (`latest_live_operation`), surfaced as the reader/canvas undo affordance.
