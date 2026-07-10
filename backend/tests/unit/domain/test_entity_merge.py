"""Unit tests for the pure merge-consolidation (`domain/entity_merge.py`, M4.S3b).

The first failing test of M4.S3b-be1: given two committed `GraphEntity`s, a survivor choice,
the author's resolved property values, and the absorbed entity's incident edges, produce the
consolidated survivor + the deterministic re-point/fold/discard step list. Pure — no store, no
I/O — so the consolidation rules (alias union, by-hand property-conflict resolution per DM-S3b-2,
edge re-point under the content-addressed `relation_edge_id` per DM-S3b-3) are unit-tested
without a database. The `EntityEditService.merge_entities` orchestration drives the graph/Postgres
writes from this plan; the fold-vs-repoint distinction is kept pure by passing in the survivor's
existing edge ids (`existing_target_edge_ids`).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from story_forge.domain.candidates import relation_edge_id
from story_forge.domain.entity_merge import (
    EntityMergeInvalid,
    PropertyConflict,
    detect_property_conflicts,
    plan_merge,
)
from story_forge.domain.graph import GraphEntity, GraphRelation


def _entity(**overrides: object) -> GraphEntity:
    base: dict[str, object] = {
        "type": "Character",
        "canonical_name_pl": "Bronisław",
        "canonical_name_en": None,
        "aliases": ["Bronek"],
        "properties": {"age": 40, "role": "smith"},
        "project_id": uuid4(),
    }
    base.update(overrides)
    return GraphEntity(**base)  # type: ignore[arg-type]


def _edge(subject_id: object, predicate: str, object_id: object) -> GraphRelation:
    return GraphRelation(
        id=relation_edge_id(subject_id, predicate, object_id),  # type: ignore[arg-type]
        type=predicate,
        subject_id=subject_id,  # type: ignore[arg-type]
        object_id=object_id,  # type: ignore[arg-type]
        confidence=1.0,
    )


# ── consolidation: aliases ───────────────────────────────────────────────────


def test_aliases_union_folds_in_absorbed_names_and_dedups() -> None:
    project = uuid4()
    survivor = _entity(project_id=project, aliases=["Bronek"], canonical_name_pl="Bronisław")
    absorbed = _entity(
        project_id=project,
        canonical_name_pl="Broniek",
        canonical_name_en="Bron",
        aliases=["Bronek", "Bronko"],  # "Bronek" already an A alias → de-duped
    )
    plan = plan_merge(
        survivor, absorbed, [], resolved_properties={}, existing_target_edge_ids=set()
    )

    # A's aliases first (order-preserving), then absorbed aliases + absorbed canonical names,
    # de-duplicated; the absorbed canonical name "Broniek"/"Bron" become aliases of A.
    assert plan.survivor.aliases == ["Bronek", "Bronko", "Broniek", "Bron"]


def test_survivor_canonical_name_never_becomes_its_own_alias() -> None:
    project = uuid4()
    survivor = _entity(project_id=project, canonical_name_pl="Bronisław", aliases=[])
    # The absorbed entity carries A's canonical name as one of its aliases.
    absorbed = _entity(project_id=project, canonical_name_pl="Broniek", aliases=["Bronisław"])
    plan = plan_merge(
        survivor, absorbed, [], resolved_properties={}, existing_target_edge_ids=set()
    )

    assert "Bronisław" not in plan.survivor.aliases  # excluded — it's A's canonical name
    assert plan.survivor.aliases == ["Broniek"]


def test_survivor_identity_fields_are_preserved() -> None:
    project = uuid4()
    survivor = _entity(project_id=project, type="Character", canonical_name_pl="Bronisław")
    absorbed = _entity(project_id=project, type="Deity", canonical_name_pl="Broniek")
    plan = plan_merge(
        survivor, absorbed, [], resolved_properties={}, existing_target_edge_ids=set()
    )

    assert plan.survivor.id == survivor.id
    assert plan.survivor.type == "Character"  # survivor's type wins
    assert plan.survivor.canonical_name_pl == "Bronisław"
    assert plan.survivor.project_id == project


# ── consolidation: properties (DM-S3b-2, by-hand conflict resolution) ─────────


def test_non_conflicting_properties_union_automatically() -> None:
    project = uuid4()
    survivor = _entity(project_id=project, properties={"age": 40, "role": "smith"})
    absorbed = _entity(project_id=project, properties={"town": "Lwów"})  # no key clash
    plan = plan_merge(
        survivor, absorbed, [], resolved_properties={}, existing_target_edge_ids=set()
    )

    assert plan.survivor.properties == {"age": 40, "role": "smith", "town": "Lwów"}


def test_detect_property_conflicts_returns_only_diverging_keys() -> None:
    project = uuid4()
    survivor = _entity(project_id=project, properties={"age": 40, "role": "smith"})
    absorbed = _entity(project_id=project, properties={"age": 41, "role": "smith", "town": "Lwów"})

    conflicts = detect_property_conflicts(survivor, absorbed)

    # "age" diverges; "role" is equal (not a conflict); "town" is absorbed-only (it unions)
    assert conflicts == [PropertyConflict(key="age", survivor_value=40, absorbed_value=41)]


def test_author_resolved_value_wins_the_conflict() -> None:
    project = uuid4()
    survivor = _entity(project_id=project, properties={"age": 40})
    absorbed = _entity(project_id=project, properties={"age": 41})
    plan = plan_merge(
        survivor, absorbed, [], resolved_properties={"age": 41}, existing_target_edge_ids=set()
    )

    assert plan.survivor.properties == {"age": 41}  # author picked the absorbed value


def test_unresolved_property_conflict_is_rejected() -> None:
    project = uuid4()
    survivor = _entity(project_id=project, properties={"age": 40})
    absorbed = _entity(project_id=project, properties={"age": 41})
    with pytest.raises(EntityMergeInvalid):
        plan_merge(survivor, absorbed, [], resolved_properties={}, existing_target_edge_ids=set())


def test_resolved_value_for_a_non_conflict_key_is_ignored() -> None:
    # A merge resolves conflicts; it is not an arbitrary property edit. A `resolved` key that is
    # not a detected conflict must not be injected into the survivor's properties.
    project = uuid4()
    survivor = _entity(project_id=project, properties={"age": 40})
    absorbed = _entity(project_id=project, properties={"age": 41})
    plan = plan_merge(
        survivor,
        absorbed,
        [],
        resolved_properties={"age": 41, "smuggled": "nope"},  # "smuggled" isn't a conflict
        existing_target_edge_ids=set(),
    )
    assert plan.survivor.properties == {"age": 41}  # resolved conflict only; no injection


# ── consolidation: edges (DM-S3b-3, content-addressed re-point) ───────────────


def test_incident_edge_is_repointed_onto_the_survivor() -> None:
    project = uuid4()
    survivor = _entity(project_id=project)
    absorbed = _entity(project_id=project)
    other = uuid4()
    edge = _edge(absorbed.id, "loves", other)  # (B, loves, X)

    plan = plan_merge(
        survivor, absorbed, [edge], resolved_properties={}, existing_target_edge_ids=set()
    )

    assert plan.repointed_count == 1
    assert plan.folded_count == 0
    assert plan.self_loops_dropped == 0
    (step,) = plan.steps
    assert step.kind == "repoint"
    assert step.repoint.direction == "subject"
    assert step.repoint.old_edge.id == edge.id
    # the new edge points at A and carries the recomputed content-addressed id
    assert step.repoint.new_edge.subject_id == survivor.id
    assert step.repoint.new_edge.object_id == other
    assert step.repoint.new_edge.id == relation_edge_id(survivor.id, "loves", other)


def test_repoint_preserves_the_edge_uid_handle_across_the_re_key() -> None:
    # The §4 surrogate handle survives a merge re-point (INV-10): `model_copy` re-keys the id and
    # endpoints but keeps `edge_uid`, so the moved edge stays addressable. The service records the
    # old edge (handle and all) in the before-image, so undo restores it.
    project = uuid4()
    survivor = _entity(project_id=project)
    absorbed = _entity(project_id=project)
    other = uuid4()
    handle = uuid4()
    edge = GraphRelation(
        id=relation_edge_id(absorbed.id, "loves", other),
        type="loves",
        subject_id=absorbed.id,
        object_id=other,
        confidence=1.0,
        edge_uid=handle,
    )

    plan = plan_merge(
        survivor, absorbed, [edge], resolved_properties={}, existing_target_edge_ids=set()
    )

    (step,) = plan.steps
    assert step.repoint.new_edge.id != edge.id  # the content id re-keyed …
    assert step.repoint.new_edge.edge_uid == handle  # … but the handle rode across (INV-10)
    assert step.repoint.old_edge.edge_uid == handle  # and the before-image carries it for undo


def test_repoint_that_collides_with_an_existing_survivor_edge_folds() -> None:
    project = uuid4()
    survivor = _entity(project_id=project)
    absorbed = _entity(project_id=project)
    other = uuid4()
    edge = _edge(absorbed.id, "loves", other)  # (B, loves, X)
    # A already has (A, loves, X) — re-pointing B's edge collides and MERGE-folds.
    existing = {relation_edge_id(survivor.id, "loves", other)}

    plan = plan_merge(
        survivor, absorbed, [edge], resolved_properties={}, existing_target_edge_ids=existing
    )

    assert plan.folded_count == 1  # multiplicity lost — surfaced to the author
    assert plan.repointed_count == 0
    (step,) = plan.steps
    assert step.kind == "fold"


def test_edge_between_absorbed_and_survivor_becomes_a_dropped_self_loop() -> None:
    project = uuid4()
    survivor = _entity(project_id=project)
    absorbed = _entity(project_id=project)
    edge = _edge(absorbed.id, "knows", survivor.id)  # (B, knows, A) → (A, knows, A) → drop

    plan = plan_merge(
        survivor, absorbed, [edge], resolved_properties={}, existing_target_edge_ids=set()
    )

    assert plan.self_loops_dropped == 1
    assert plan.repointed_count == 0
    (step,) = plan.steps
    assert step.kind == "discard_self_loop"


def test_object_side_repoint_sets_direction_object() -> None:
    project = uuid4()
    survivor = _entity(project_id=project)
    absorbed = _entity(project_id=project)
    other = uuid4()
    edge = _edge(other, "fears", absorbed.id)  # (X, fears, B)

    plan = plan_merge(
        survivor, absorbed, [edge], resolved_properties={}, existing_target_edge_ids=set()
    )

    (step,) = plan.steps
    assert step.repoint.direction == "object"
    assert step.repoint.new_edge.subject_id == other
    assert step.repoint.new_edge.object_id == survivor.id


def test_steps_are_ordered_deterministically_by_old_edge_id() -> None:
    project = uuid4()
    survivor = _entity(project_id=project)
    absorbed = _entity(project_id=project)
    edges = [_edge(absorbed.id, f"rel{i}", uuid4()) for i in range(5)]

    plan = plan_merge(
        survivor, absorbed, edges, resolved_properties={}, existing_target_edge_ids=set()
    )

    old_ids = [step.repoint.old_edge.id for step in plan.steps]
    assert old_ids == sorted(old_ids)


# ── guards ───────────────────────────────────────────────────────────────────


def test_self_merge_is_rejected() -> None:
    entity = _entity()
    with pytest.raises(EntityMergeInvalid):
        plan_merge(entity, entity, [], resolved_properties={}, existing_target_edge_ids=set())
