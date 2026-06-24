"""Unit tests for the pure story-scope graph filter (`domain/story_scope.py`).

Pure function: a project's entities + relations, plus the story's *member entity-id set* and its
*paragraph-id set*, in — the subgraph "for this story" out. No store, no I/O — the first failing
test of the M4 multi-story backend slice. This encodes the DM-MS-1 membership property
("entity E ∈ story S ⟺ E has an accepted mention whose paragraph rolls up to S" — the membership
set is supplied by the caller, derived upstream from `entity_mentions`) and the DM-MS-2 edge rule:

- a node shows iff its id is in the member set;
- an edge shows iff **both** endpoints are members **and** (its `source_paragraph_id` is in the
  story's paragraphs **or** it has no source paragraph — a hand-added manual edge, owner's call:
  null-source edges are story-agnostic, shown whenever both ends are members).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from story_forge.domain.graph import GraphEntity, GraphRelation
from story_forge.domain.story_scope import filter_graph_to_story


def _entity(entity_id: UUID, project_id: UUID) -> GraphEntity:
    return GraphEntity(id=entity_id, type="Character", project_id=project_id)


def _relation(
    subject_id: UUID,
    object_id: UUID,
    *,
    source_paragraph_id: UUID | None,
) -> GraphRelation:
    return GraphRelation(
        id=uuid4(),
        type="KNOWS",
        subject_id=subject_id,
        object_id=object_id,
        confidence=0.9,
        source_paragraph_id=source_paragraph_id,
    )


def test_nodes_filtered_to_members() -> None:
    project = uuid4()
    member, outsider = uuid4(), uuid4()
    entities = [_entity(member, project), _entity(outsider, project)]

    nodes, _ = filter_graph_to_story(entities, [], {member}, set())

    assert [n.id for n in nodes] == [member]


def test_edge_kept_when_both_endpoints_members_and_source_in_story() -> None:
    project = uuid4()
    a, b = uuid4(), uuid4()
    para = uuid4()
    entities = [_entity(a, project), _entity(b, project)]
    rel = _relation(a, b, source_paragraph_id=para)

    _, edges = filter_graph_to_story(entities, [rel], {a, b}, {para})

    assert [e.id for e in edges] == [rel.id]


def test_edge_dropped_when_an_endpoint_is_not_a_member() -> None:
    project = uuid4()
    a, b = uuid4(), uuid4()
    para = uuid4()
    entities = [_entity(a, project), _entity(b, project)]
    rel = _relation(a, b, source_paragraph_id=para)

    # b is not a member of this story — the edge has a dangling endpoint, so it is excluded.
    _, edges = filter_graph_to_story(entities, [rel], {a}, {para})

    assert edges == []


def test_edge_dropped_when_asserted_in_another_story() -> None:
    project = uuid4()
    a, b = uuid4(), uuid4()
    other_story_para = uuid4()
    entities = [_entity(a, project), _entity(b, project)]
    # Both endpoints are members of this story, but the edge was asserted in a paragraph of a
    # *different* story (its source paragraph is not in this story's paragraph set).
    rel = _relation(a, b, source_paragraph_id=other_story_para)

    _, edges = filter_graph_to_story(entities, [rel], {a, b}, set())

    assert edges == []


def test_manual_edge_with_no_source_kept_when_both_endpoints_members() -> None:
    project = uuid4()
    a, b = uuid4(), uuid4()
    entities = [_entity(a, project), _entity(b, project)]
    # A hand-added relation carries no source_paragraph_id — story-agnostic, shown when both
    # endpoints are members (owner decision; preserves single-story scope==scope parity).
    rel = _relation(a, b, source_paragraph_id=None)

    _, edges = filter_graph_to_story(entities, [rel], {a, b}, set())

    assert [e.id for e in edges] == [rel.id]


def test_empty_membership_yields_empty_graph() -> None:
    project = uuid4()
    a, b = uuid4(), uuid4()
    entities = [_entity(a, project), _entity(b, project)]
    rel = _relation(a, b, source_paragraph_id=uuid4())

    nodes, edges = filter_graph_to_story(entities, [rel], set(), set())

    assert nodes == []
    assert edges == []
