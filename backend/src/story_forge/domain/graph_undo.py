"""Inverting a recorded graph operation — the pure half of the undo executor (M4.S3b-be2, INV-3).

A merge / delete / edit was recorded in `graph_edits` as a grouped, ordered set of before→after
rows (ADR 0007, the compensating-transaction substrate be1 wrote). This module turns those rows
back into an **ordered inverse plan**: a list of small, side-effect-free *action descriptions* the
`EntityEditService` then executes against Neo4j + Postgres, plus a declarative **drift check** that
refuses the undo if the graph has moved on since (the "lost update in reverse", ADR 0007 / DM-S3b
"but what if" case 5).

Pure by construction (domain layer): it reads the rows and emits dataclasses; it performs no I/O and
makes no decisions that need a live read. The single ordering rule it encodes is *reverse `seq`* —
each operation's rows were numbered so that replaying their inverses highest-`seq`-first restores a
consistent graph (a merge recreates the absorbed node *before* re-pointing its mentions; a delete
recreates the node *before* its incident edges, which Neo4j would otherwise drop as dangling).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from story_forge.domain.graph import GraphEntity, GraphRelation
from story_forge.domain.graph_edit import GraphEdit
from story_forge.domain.models import EntityMention


@dataclass(frozen=True)
class RecreateEntity:
    """Recreate a node from its full before-image snapshot (undo of a merge's `delete_absorbed`
    or a whole-entity `delete_entity`)."""

    entity: GraphEntity


@dataclass(frozen=True)
class RestoreEntityFields:
    """Write a subset of fields back onto a still-present node (undo of an `edit_fields` or a
    merge's `merge_consolidate` — un-fold the survivor's aliases/properties)."""

    entity_id: UUID
    fields: dict[str, object]


@dataclass(frozen=True)
class RecreateRelation:
    """Re-create an edge from its before-image (undo of a re-point/fold/discard/remove)."""

    relation: GraphRelation


@dataclass(frozen=True)
class RemoveRelation:
    """Delete an edge (undo of a re-point/fold's *new* edge, or of a manual `add_relation`)."""

    edge_id: UUID


@dataclass(frozen=True)
class ReassignMentions:
    """Move specific mention rows back onto an entity (undo of a merge's `repoint_mentions` —
    *exactly* the ids the merge moved, never the survivor's own mentions)."""

    mention_ids: list[UUID]
    to_entity_id: UUID


@dataclass(frozen=True)
class RestoreMentions:
    """Re-insert deleted mention rows from their full snapshot (undo of a whole-entity delete, or
    of a single manual `delete_mention` — a one-element list)."""

    mentions: list[EntityMention]


@dataclass(frozen=True)
class RemoveMention:
    """Delete one mention by id (undo of a manual `add_mention`, M4.S3c)."""

    mention_id: UUID


@dataclass(frozen=True)
class DeleteEntity:
    """Delete a node by id (undo of a `create_entity_from_tag` — remove the human-minted entity,
    M4.S3c). The grouped tag-new op removes its mention first, so this never orphans one."""

    entity_id: UUID


@dataclass(frozen=True)
class RemoveSuppression:
    """Delete a suppression by id (undo of a `suppress_span` — un-hide the occurrence, M4.S3c)."""

    suppression_id: UUID


@dataclass(frozen=True)
class RestoreMentionSpan:
    """Write a manual span's old offsets back (undo of an `edit_mention_span` / change-boundaries,
    M4.S3c)."""

    mention_id: UUID
    span_start: int
    span_end: int


InverseAction = (
    RecreateEntity
    | RestoreEntityFields
    | RecreateRelation
    | RemoveRelation
    | ReassignMentions
    | RestoreMentions
    | RemoveMention
    | DeleteEntity
    | RemoveSuppression
    | RestoreMentionSpan
)


@dataclass(frozen=True)
class DriftCheck:
    """A declarative guard the service runs against a live read before applying the undo. The
    operation produced a known after-state for one entity; if the graph no longer matches it,
    someone edited/deleted/recreated that entity since, and undoing would clobber their change —
    so the service refuses (→409). `expect_present=False` guards a delete's undo: the node must
    still be absent (nothing re-created it under the same id)."""

    entity_id: UUID
    expect_present: bool
    expected_fields: dict[str, object] | None = None


@dataclass(frozen=True)
class InversePlan:
    """The reversal of one recorded operation: the ordered actions to apply and the drift guard."""

    actions: list[InverseAction] = field(default_factory=list)
    drift: DriftCheck | None = None


class UndoNotInvertible(ValueError):
    """A recorded row carries an `op` the inverter does not know how to reverse — a forward writer
    was added without teaching undo about it. Fail loud rather than silently skip (INV-3)."""


def invert_operation(rows: Sequence[GraphEdit]) -> InversePlan:
    """Build the inverse plan for one grouped operation (all rows share an `operation_id`).

    Rows are replayed in **descending `seq`** so the graph stays consistent at each step. The
    drift check is taken from the operation's *primary* row — the merge's `merge_consolidate`
    (survivor), the delete's `delete_entity` (must-stay-absent), or a singleton `edit_fields`
    target. Relation-only singletons carry no entity drift guard (best-effort undo).
    """
    if not rows:
        return InversePlan()

    ordered = sorted(rows, key=lambda r: r.seq, reverse=True)
    actions: list[InverseAction] = []
    drift: DriftCheck | None = None

    for row in ordered:
        if row.op in ("delete_absorbed", "delete_entity"):
            snapshot = _require(row.before, row.op)
            actions.append(RecreateEntity(entity=GraphEntity(**snapshot)))
            if row.op == "delete_entity":
                # whole-entity delete: undo refuses if the id has been re-used since.
                drift = DriftCheck(entity_id=row.target_id, expect_present=False)
        elif row.op == "delete_relations":
            for edge in _list_of(_require(row.before, row.op), "edges"):
                actions.append(RecreateRelation(relation=GraphRelation(**edge)))
        elif row.op == "delete_mentions":
            mentions = _list_of(_require(row.before, row.op), "mentions")
            actions.append(RestoreMentions(mentions=[EntityMention(**m) for m in mentions]))
        elif row.op in ("edit_fields", "merge_consolidate"):
            before = _require(row.before, row.op)
            actions.append(RestoreEntityFields(entity_id=row.target_id, fields=dict(before)))
            # the survivor (merge) / edited node must still match what the op produced.
            drift = DriftCheck(
                entity_id=row.target_id,
                expect_present=True,
                expected_fields=dict(row.after) if row.after is not None else None,
            )
        elif row.op == "repoint_relation":
            # forward = delete old_edge, create a *genuinely new* new_edge(after) on A; undo =
            # delete that new edge, recreate the old one.
            after = _require(row.after, row.op)
            before = _require(row.before, row.op)
            actions.append(RemoveRelation(edge_id=UUID(str(after["id"]))))
            actions.append(RecreateRelation(relation=GraphRelation(**before)))
        elif row.op == "fold_relation":
            # forward = delete B's old_edge, then MERGE onto an edge **A already had** (new_edge.id
            # is A's pre-existing edge — that's what makes it a fold). So the new edge must NOT be
            # removed on undo (it was never created here); undo only recreates B's old edge.
            actions.append(RecreateRelation(relation=GraphRelation(**_require(row.before, row.op))))
        elif row.op == "discard_self_loop_relation":
            # forward dropped the old edge (no new edge); undo re-creates it. The op name is
            # `f"{step.kind}_relation"` from the merge writer — "discard_self_loop_relation",
            # matching the "repoint_relation"/"fold_relation" siblings above.
            actions.append(RecreateRelation(relation=GraphRelation(**_require(row.before, row.op))))
        elif row.op == "add_relation":
            # forward created the edge at target_id (before is None) — UNLESS it MERGE-folded onto
            # an edge that already existed, creating nothing, in which case undo must not delete
            # that pre-existing edge. The `after` image records which (legacy rows: no flag = made).
            if not (row.after or {}).get("merged_into_existing"):
                actions.append(RemoveRelation(edge_id=row.target_id))
        elif row.op == "remove_relation":
            # forward deleted the edge; undo re-creates it from the before-image. A be2+ row carries
            # the full edge snapshot (faithful confidence/properties); a legacy S3a row carried only
            # subject/predicate/object — reconstruct it at manual confidence, the best it can do.
            before = _require(row.before, row.op)
            if "type" in before:
                actions.append(RecreateRelation(relation=GraphRelation(**before)))
            else:
                actions.append(
                    RecreateRelation(
                        relation=GraphRelation(
                            id=row.target_id,
                            type=str(before["predicate"]),
                            subject_id=UUID(str(before["subject_id"])),
                            object_id=UUID(str(before["object_id"])),
                            confidence=1.0,
                        )
                    )
                )
        elif row.op == "repoint_mentions":
            before = _require(row.before, row.op)
            actions.append(
                ReassignMentions(
                    mention_ids=[UUID(str(mid)) for mid in _list_of(before, "mention_ids")],
                    to_entity_id=UUID(str(before["from_entity_id"])),
                )
            )
        elif row.op == "add_mention":
            # forward inserted a manual mention at target_id; undo deletes it by id.
            actions.append(RemoveMention(mention_id=row.target_id))
        elif row.op == "create_entity_from_tag":
            # forward minted a node from a tag (before None); undo deletes it. The drift guard
            # refuses if the node was edited/merged-away since (mirror edit_fields' after-guard) —
            # deleting an entity someone has since changed would clobber that change.
            after = _require(row.after, row.op)
            actions.append(DeleteEntity(entity_id=row.target_id))
            drift = DriftCheck(
                entity_id=row.target_id, expect_present=True, expected_fields=dict(after)
            )
        elif row.op == "suppress_span":
            # forward wrote a suppression at target_id; undo removes it (un-hides the occurrence).
            # Rejection ("not an entity"/"not this entity") is *always* a suppression (DM-S3c-1 B),
            # so the resolver subtracts it post-overlay even from a manual span — one mechanism.
            actions.append(RemoveSuppression(suppression_id=row.target_id))
        elif row.op == "edit_mention_span":
            # forward moved a manual span's offsets; undo restores the old ones.
            before = _require(row.before, row.op)
            actions.append(
                RestoreMentionSpan(
                    mention_id=row.target_id,
                    span_start=int(str(before["span_start"])),
                    span_end=int(str(before["span_end"])),
                )
            )
        else:
            raise UndoNotInvertible(row.op)

    return InversePlan(actions=actions, drift=drift)


def fields_match(entity: GraphEntity, expected: dict[str, object]) -> bool:
    """Does the live entity still carry the field values the operation produced? The comparison is
    field-by-field over `expected` only (a partial after-image), so unrelated fields don't matter.
    JSON round-tripping turned the snapshot's values into plain types, so compare in that shape."""
    current = entity.model_dump(mode="json")
    return all(current.get(key) == value for key, value in expected.items())


def _require(image: dict[str, object] | None, op: str) -> dict[str, object]:
    if image is None:
        raise UndoNotInvertible(f"{op} row has no before/after image to invert")
    return image


def _list_of(image: dict[str, object], key: str) -> list[Any]:
    """A list value out of a JSON before-image (the snapshot stores lists of edge/mention dicts)."""
    value = image.get(key, [])
    return value if isinstance(value, list) else []
