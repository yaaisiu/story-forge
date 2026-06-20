"""Pure unit tests for `domain/graph_undo.invert_operation` — turning a recorded operation's
grouped `graph_edits` rows back into an ordered inverse plan + drift guard (M4.S3b-be2, INV-3).

No store, no I/O: rows in, an `InversePlan` of action dataclasses out. These pin the inverse of
each `op` the forward writers emit and the reverse-`seq` ordering rule.
"""

from __future__ import annotations

from uuid import uuid4

from story_forge.domain.graph import GraphEntity, GraphRelation
from story_forge.domain.graph_edit import GraphEdit
from story_forge.domain.graph_undo import (
    DriftCheck,
    ReassignMentions,
    RecreateEntity,
    RecreateRelation,
    RemoveRelation,
    RestoreEntityFields,
    UndoNotInvertible,
    fields_match,
    invert_operation,
)
from story_forge.domain.models import EntityMention

PROJECT = uuid4()


def _entity(**overrides: object) -> GraphEntity:
    base: dict[str, object] = {
        "type": "Character",
        "canonical_name_pl": "Broniek",
        "aliases": [],
        "properties": {},
        "project_id": PROJECT,
    }
    base.update(overrides)
    return GraphEntity(**base)


def _edge(subject_id: object, object_id: object, predicate: str = "LOVES") -> GraphRelation:
    return GraphRelation(type=predicate, subject_id=subject_id, object_id=object_id, confidence=1.0)


# --- merge inverse -----------------------------------------------------------------


def _merge_rows(
    survivor: GraphEntity, absorbed: GraphEntity, edge: GraphRelation
) -> list[GraphEdit]:
    """A minimal grouped merge log: consolidate(0) → repoint(1) → mentions(2) → delete(3)."""
    op = uuid4()
    new_edge = _edge(survivor.id, edge.object_id)
    mention_id = uuid4()
    return (
        [
            GraphEdit(
                operation_id=op,
                seq=0,
                op_kind="merge",
                project_id=PROJECT,
                target_id=survivor.id,
                target_kind="entity",
                op="merge_consolidate",
                before={"aliases": survivor.aliases, "properties": survivor.properties},
                after={"aliases": ["Broniek"], "properties": {}},
            ),
            GraphEdit(
                operation_id=op,
                seq=1,
                op_kind="merge",
                project_id=PROJECT,
                target_id=edge.id,
                target_kind="relation",
                op="repoint_relation",
                before=edge.model_dump(mode="json"),
                after=new_edge.model_dump(mode="json"),
            ),
            GraphEdit(
                operation_id=op,
                seq=2,
                op_kind="merge",
                project_id=PROJECT,
                target_id=absorbed.id,
                target_kind="entity",
                op="repoint_mentions",
                before={
                    "from_entity_id": str(absorbed.id),
                    "to_entity_id": str(survivor.id),
                    "mention_ids": [str(mention_id)],
                },
            ),
            GraphEdit(
                operation_id=op,
                seq=3,
                op_kind="merge",
                project_id=PROJECT,
                target_id=absorbed.id,
                target_kind="entity",
                op="delete_absorbed",
                before=absorbed.model_dump(mode="json"),
            ),
        ],
        new_edge,
        mention_id,
    )


def test_merge_inverse_is_reverse_seq_and_recreates_b_first() -> None:
    survivor, absorbed = _entity(canonical_name_pl="Bronisław"), _entity()
    edge = _edge(absorbed.id, uuid4())
    rows, new_edge, mention_id = _merge_rows(survivor, absorbed, edge)

    plan = invert_operation(rows)

    # reverse seq: delete_absorbed (3) first → recreate B before re-pointing its mentions to it.
    assert isinstance(plan.actions[0], RecreateEntity)
    assert plan.actions[0].entity.id == absorbed.id
    # the repointed edge: remove the new (survivor) edge, recreate the old (absorbed) one.
    remove = next(a for a in plan.actions if isinstance(a, RemoveRelation))
    assert remove.edge_id == new_edge.id
    recreate = next(a for a in plan.actions if isinstance(a, RecreateRelation))
    assert recreate.relation.id == edge.id
    # mentions move back to B (the absorbed), by exact id.
    reassign = next(a for a in plan.actions if isinstance(a, ReassignMentions))
    assert reassign.to_entity_id == absorbed.id
    assert reassign.mention_ids == [mention_id]
    # survivor's aliases/properties un-folded.
    restore = next(a for a in plan.actions if isinstance(a, RestoreEntityFields))
    assert restore.entity_id == survivor.id
    assert restore.fields == {"aliases": [], "properties": {}}


def test_merge_inverse_drift_guards_the_survivor_after_image() -> None:
    survivor, absorbed = _entity(canonical_name_pl="Bronisław"), _entity()
    rows, _, _ = _merge_rows(survivor, absorbed, _edge(absorbed.id, uuid4()))

    plan = invert_operation(rows)

    assert plan.drift == DriftCheck(
        entity_id=survivor.id,
        expect_present=True,
        expected_fields={"aliases": ["Broniek"], "properties": {}},
    )


# --- whole-entity delete inverse --------------------------------------------------


def test_delete_inverse_recreates_node_then_edges_then_mentions() -> None:
    victim = _entity(canonical_name_pl="The Shard")
    other = uuid4()
    edge = _edge(victim.id, other)
    mention = EntityMention(paragraph_id=uuid4(), entity_id=victim.id)
    op = uuid4()
    rows = [
        GraphEdit(
            operation_id=op,
            seq=0,
            op_kind="delete",
            project_id=PROJECT,
            target_id=victim.id,
            target_kind="entity",
            op="delete_mentions",
            before={"mentions": [mention.model_dump(mode="json")]},
        ),
        GraphEdit(
            operation_id=op,
            seq=1,
            op_kind="delete",
            project_id=PROJECT,
            target_id=victim.id,
            target_kind="entity",
            op="delete_relations",
            before={"edges": [edge.model_dump(mode="json")]},
        ),
        GraphEdit(
            operation_id=op,
            seq=2,
            op_kind="delete",
            project_id=PROJECT,
            target_id=victim.id,
            target_kind="entity",
            op="delete_entity",
            before=victim.model_dump(mode="json"),
        ),
    ]

    plan = invert_operation(rows)

    kinds = [type(a).__name__ for a in plan.actions]
    assert kinds == ["RecreateEntity", "RecreateRelation", "RestoreMentions"]
    assert plan.actions[0].entity.id == victim.id  # node recreated first (edges need endpoints)
    assert plan.actions[1].relation.id == edge.id
    assert plan.actions[2].mentions[0].id == mention.id
    # undo of a delete refuses if the id has been re-used since.
    assert plan.drift == DriftCheck(entity_id=victim.id, expect_present=False)


# --- singleton (S3a) edits --------------------------------------------------------


def test_edit_fields_singleton_inverse_restores_before_and_guards_after() -> None:
    eid = uuid4()
    row = GraphEdit(
        target_id=eid,
        target_kind="entity",
        op="edit_fields",
        before={"type": "Character", "properties": {"age": 23}},
        after={"type": "Deity", "properties": {"role": "priestess"}},
    )

    plan = invert_operation([row])

    assert plan.actions == [
        RestoreEntityFields(entity_id=eid, fields={"type": "Character", "properties": {"age": 23}})
    ]
    assert plan.drift == DriftCheck(
        entity_id=eid,
        expect_present=True,
        expected_fields={"type": "Deity", "properties": {"role": "priestess"}},
    )


def test_add_relation_singleton_inverse_removes_the_edge() -> None:
    edge_id = uuid4()
    row = GraphEdit(
        target_id=edge_id,
        target_kind="relation",
        op="add_relation",
        after={"subject_id": str(uuid4()), "predicate": "LOVES", "object_id": str(uuid4())},
    )
    plan = invert_operation([row])
    assert plan.actions == [RemoveRelation(edge_id=edge_id)]
    assert plan.drift is None  # relation-only singleton: best-effort, no entity guard


def test_remove_relation_singleton_inverse_recreates_the_edge() -> None:
    edge_id, subject, obj = uuid4(), uuid4(), uuid4()
    row = GraphEdit(
        target_id=edge_id,
        target_kind="relation",
        op="remove_relation",
        before={"subject_id": str(subject), "predicate": "LOVES", "object_id": str(obj)},
    )
    plan = invert_operation([row])
    assert len(plan.actions) == 1
    rel = plan.actions[0]
    assert isinstance(rel, RecreateRelation)
    assert (rel.relation.id, rel.relation.subject_id, rel.relation.object_id) == (
        edge_id,
        subject,
        obj,
    )


def test_discard_self_loop_inverse_recreates_the_dropped_edge() -> None:
    survivor = _entity()
    loop = _edge(survivor.id, survivor.id)
    row = GraphEdit(
        target_id=loop.id,
        target_kind="relation",
        op="discard_self_loop",
        before=loop.model_dump(mode="json"),
        after=None,
    )
    plan = invert_operation([row])
    assert plan.actions == [RecreateRelation(relation=loop)]


# --- guards -----------------------------------------------------------------------


def test_empty_operation_is_an_empty_plan() -> None:
    plan = invert_operation([])
    assert plan.actions == [] and plan.drift is None


def test_unknown_op_is_not_invertible() -> None:
    row = GraphEdit(target_id=uuid4(), target_kind="entity", op="teleport")
    import pytest

    with pytest.raises(UndoNotInvertible):
        invert_operation([row])


def test_fields_match_compares_only_expected_keys() -> None:
    entity = _entity(type="Deity", properties={"role": "priestess"})
    assert fields_match(entity, {"type": "Deity"})
    assert not fields_match(entity, {"type": "Character"})
    assert fields_match(entity, {"properties": {"role": "priestess"}})
