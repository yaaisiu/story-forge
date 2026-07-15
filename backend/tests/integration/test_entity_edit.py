"""Integration: the entity-&-relation edit path against real Neo4j + the throwaway Postgres.

`EntityEditService` mutates committed graph state (real `Neo4jRepo`) and records the before→after
evidence (real `PostgresEditStore` on the test DB). These tests pin that the node/edge change
*lands in Neo4j* and that a `graph_edits` row lands *per change* (DM-S3a-2, INV-3). `graph_edits`
has no FK (`target_id` is a soft Neo4j ref), so no project/story tree is needed; the Neo4j side is
scoped to a fresh `project_id` and DETACH-DELETEd on teardown, and the test DB is dropped at session
end.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from psycopg.rows import dict_row

from story_forge.adapters import postgres_repo as repo
from story_forge.adapters.db import libpq_kwargs
from story_forge.adapters.neo4j_repo import Neo4jRepo
from story_forge.adapters.postgres_edit_store import PostgresEditStore
from story_forge.adapters.postgres_mention_store import PostgresMentionStore
from story_forge.agents.entity_edit import (
    EntityEditService,
    NothingToUndo,
    RelationEdgeNotFound,
    SelfMergeError,
    UndoConflict,
)
from story_forge.config import settings
from story_forge.domain.candidates import relation_edge_id
from story_forge.domain.entity_edits import EntityEditPatch
from story_forge.domain.graph import GraphEntity
from story_forge.domain.models import Chapter, EntityMention, Paragraph, Project, Scene, Story

pytestmark = pytest.mark.integration


@dataclass
class _Live:
    graph: Neo4jRepo
    service: EntityEditService
    project_id: UUID
    conninfo: dict[str, object]


@pytest_asyncio.fixture
async def live(_migrated_test_db: None) -> AsyncIterator[_Live]:
    conninfo = libpq_kwargs(settings.test_database_url)
    graph = await Neo4jRepo.connect(
        uri=settings.neo4j_uri, user=settings.neo4j_user, password=settings.neo4j_password
    )
    project_id = uuid4()
    service = EntityEditService(graph, PostgresEditStore(conninfo), PostgresMentionStore(conninfo))
    try:
        yield _Live(graph, service, project_id, conninfo)
    finally:
        await graph.delete_project_graph(project_id)
        await graph.close()


async def _edits_for(live: _Live, target_id: UUID) -> list[dict[str, object]]:
    async with await psycopg.AsyncConnection.connect(autocommit=True, **live.conninfo) as conn:  # type: ignore[arg-type]
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            "SELECT target_kind, op, before, after FROM graph_edits "
            "WHERE target_id = %s ORDER BY created_at",
            (target_id,),
        )
        return await cur.fetchall()


async def test_edit_entity_updates_node_and_logs_evidence(live: _Live) -> None:
    entity = GraphEntity(
        type="Character",
        canonical_name_pl="Janek",
        properties={"age": 23},
        project_id=live.project_id,
    )
    await live.graph.create_entity(entity)

    await live.service.edit_entity(
        live.project_id,
        entity.id,
        EntityEditPatch(type="Deity", properties={"role": "priestess"}),
    )

    updated = await live.graph.get_entity(entity.id)
    assert updated is not None
    assert updated.type == "Deity"
    assert updated.properties == {"role": "priestess"}

    edits = await _edits_for(live, entity.id)
    assert len(edits) == 1
    assert edits[0]["target_kind"] == "entity"
    assert edits[0]["op"] == "edit_fields"
    assert edits[0]["before"] == {"type": "Character", "properties": {"age": 23}}
    assert edits[0]["after"] == {"type": "Deity", "properties": {"role": "priestess"}}


async def test_add_then_remove_relation_logs_each_change(live: _Live) -> None:
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=live.project_id)
    maria = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=live.project_id)
    await live.graph.create_entity(janek)
    await live.graph.create_entity(maria)

    add = await live.service.add_relation(live.project_id, janek.id, "LOVES", maria.id)
    assert add.merged_into_existing is False
    assert [r.id for r in await live.graph.get_relations(live.project_id)] == [add.edge_id]
    add_rows = await _edits_for(live, add.edge_id)
    assert [r["op"] for r in add_rows] == ["add_relation"]
    assert add_rows[0]["target_kind"] == "relation"

    await live.service.remove_relation(live.project_id, add.edge_id)
    assert await live.graph.get_relations(live.project_id) == []
    ops = [r["op"] for r in await _edits_for(live, add.edge_id)]
    assert ops == ["add_relation", "remove_relation"]


async def test_remove_unknown_edge_is_not_found(live: _Live) -> None:
    with pytest.raises(RelationEdgeNotFound):
        await live.service.remove_relation(live.project_id, uuid4())


async def test_retarget_preserves_the_edge_uid_across_a_real_re_key_then_undo(live: _Live) -> None:
    """End-to-end against real Neo4j + Postgres (Graph-quality S5b-be): a re-predicate re-keys the
    content id but the §4 handle survives (INV-10), and undo restores the exact prior edge — its
    predicate AND its handle (INV-3 widened by the handle)."""
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=live.project_id)
    maria = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=live.project_id)
    await live.graph.create_entity(janek)
    await live.graph.create_entity(maria)
    add = await live.service.add_relation(live.project_id, janek.id, "PASSENGER_ON", maria.id)
    original = await live.graph.get_relation(live.project_id, add.edge_id)
    assert original is not None and original.edge_uid is not None  # minted forward on add
    handle = original.edge_uid

    result = await live.service.retarget_relation(live.project_id, add.edge_id, predicate="ON_SHIP")

    # the content id re-keyed, the old edge is gone, the new one carries the SAME handle
    new_id = relation_edge_id(janek.id, "ON_SHIP", maria.id)
    assert result.edge_id == new_id
    assert result.merged_into_existing is False
    assert await live.graph.get_relation(live.project_id, add.edge_id) is None
    rekeyed = await live.graph.get_relation(live.project_id, new_id)
    assert rekeyed is not None
    assert rekeyed.type == "ON_SHIP"
    assert rekeyed.edge_uid == handle

    await live.service.undo_last(live.project_id)

    # the new edge is gone; the original is restored — predicate and handle both
    assert await live.graph.get_relation(live.project_id, new_id) is None
    restored = await live.graph.get_relation(live.project_id, add.edge_id)
    assert restored is not None
    assert restored.type == "PASSENGER_ON"
    assert restored.edge_uid == handle


async def _seed_mention(live: _Live, entity_id: UUID) -> UUID:
    """Build a minimal Postgres tree + a mention of `entity_id`, returning the project id to
    cascade-delete on cleanup. `entity_mentions.paragraph_id` is a real FK, so a paragraph must
    exist; `entity_id` is a soft Neo4j ref (no FK)."""
    async with await psycopg.AsyncConnection.connect(autocommit=True, **live.conninfo) as conn:  # type: ignore[arg-type]
        project = Project(name="Merge IT", language="en")
        await repo.insert_project(conn, project)
        story = Story(project_id=project.id, title="B1", raw_text="x")
        await repo.insert_story(conn, story)
        chapter = Chapter(story_id=story.id, order_index=0, title="C1")
        await repo.insert_chapter(conn, chapter)
        scene = Scene(chapter_id=chapter.id, order_index=0, title="S1")
        await repo.insert_scene(conn, scene)
        para = Paragraph(scene_id=scene.id, order_index=0, content="Broniek walked in.")
        await repo.insert_paragraph(conn, para)
        await repo.insert_entity_mention(
            conn, EntityMention(paragraph_id=para.id, entity_id=entity_id)
        )
    return project.id


async def _delete_project_tree(live: _Live, project_id: UUID) -> None:
    async with await psycopg.AsyncConnection.connect(autocommit=True, **live.conninfo) as conn:  # type: ignore[arg-type]
        await conn.execute("DELETE FROM projects WHERE id = %s", (project_id,))


async def _mentions_for(live: _Live, entity_id: UUID) -> int:
    async with await psycopg.AsyncConnection.connect(autocommit=True, **live.conninfo) as conn:  # type: ignore[arg-type]
        cur = await conn.execute(
            "SELECT count(*) FROM entity_mentions WHERE entity_id = %s", (entity_id,)
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def _operation_rows(live: _Live) -> list[dict[str, object]]:
    async with await psycopg.AsyncConnection.connect(autocommit=True, **live.conninfo) as conn:  # type: ignore[arg-type]
        cur = conn.cursor(row_factory=dict_row)
        # grouped operations only (operation_id IS NOT NULL) — a singleton S3a edit/add now also
        # carries project_id, so scope to the merge/delete group the caller is inspecting.
        await cur.execute(
            "SELECT seq, op, op_kind, description, operation_id "
            "FROM graph_edits WHERE project_id = %s AND operation_id IS NOT NULL ORDER BY seq",
            (live.project_id,),
        )
        return await cur.fetchall()


async def test_merge_round_trip_across_neo4j_and_postgres(live: _Live) -> None:
    """End-to-end: merging B into A folds B's name into A, re-points B's edge onto A, deletes B
    (Neo4j), moves B's mention onto A (Postgres), and records one grouped, reversible operation."""
    survivor = GraphEntity(
        type="Character", canonical_name_pl="Bronisław", project_id=live.project_id
    )
    absorbed = GraphEntity(
        type="Character", canonical_name_pl="Broniek", project_id=live.project_id
    )
    other = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=live.project_id)
    for entity in (survivor, absorbed, other):
        await live.graph.create_entity(entity)
    add = await live.service.add_relation(live.project_id, absorbed.id, "LOVES", other.id)
    pg_project = await _seed_mention(live, absorbed.id)

    try:
        summary = await live.service.merge_entities(live.project_id, absorbed.id, survivor.id, {})

        # Neo4j: B folded into A, its edge re-pointed onto A, B gone
        merged = await live.graph.get_entity(survivor.id)
        assert merged is not None and "Broniek" in merged.aliases
        assert await live.graph.get_entity(absorbed.id) is None
        new_edge_id = relation_edge_id(survivor.id, "LOVES", other.id)
        assert {r.id for r in await live.graph.get_relations(live.project_id)} == {new_edge_id}
        assert add.edge_id != new_edge_id  # content-addressed id changed on re-point

        # Postgres: the mention followed B onto A
        assert await _mentions_for(live, absorbed.id) == 0
        assert await _mentions_for(live, survivor.id) == 1
        assert summary.mentions_repointed == 1
        assert summary.repointed_count == 1

        # one grouped, reversible operation recorded (consolidate + edge + delete-B + mentions)
        rows = await _operation_rows(live)
        assert [r["op"] for r in rows] == [
            "merge_consolidate",
            "repoint_relation",
            "repoint_mentions",
            "delete_absorbed",
        ]
        assert len({r["operation_id"] for r in rows}) == 1
        assert {r["description"] for r in rows} == {"merged Broniek into Bronisław"}
    finally:
        await _delete_project_tree(live, pg_project)


async def test_merge_into_self_is_rejected(live: _Live) -> None:
    sole = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=live.project_id)
    await live.graph.create_entity(sole)
    with pytest.raises(SelfMergeError):
        await live.service.merge_entities(live.project_id, sole.id, sole.id, {})


# --- M4.S3b-be2: whole-entity delete + the general undo executor ------------------------


async def _relation_ids(live: _Live) -> set[UUID]:
    return {r.id for r in await live.graph.get_relations(live.project_id)}


async def test_merge_then_undo_restores_the_exact_prior_graph(live: _Live) -> None:
    """The round-trip the slice exists for: undo a merge and the graph + mentions return to their
    pre-merge shape — B back with its fields, its edge re-pointed onto B, its mention re-homed, and
    the survivor's folded aliases un-folded."""
    survivor = GraphEntity(
        type="Character", canonical_name_pl="Bronisław", project_id=live.project_id
    )
    absorbed = GraphEntity(
        type="Character", canonical_name_pl="Broniek", project_id=live.project_id
    )
    other = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=live.project_id)
    for entity in (survivor, absorbed, other):
        await live.graph.create_entity(entity)
    add = await live.service.add_relation(live.project_id, absorbed.id, "LOVES", other.id)
    pg_project = await _seed_mention(live, absorbed.id)

    try:
        await live.service.merge_entities(live.project_id, absorbed.id, survivor.id, {})
        # sanity: the merge happened (B gone, mention on A, edge re-pointed)
        assert await live.graph.get_entity(absorbed.id) is None

        result = await live.service.undo_last(live.project_id)
        assert result.applied is True
        assert result.description == "merged Broniek into Bronisław"

        # B is back with its original identity; the survivor's aliases un-folded.
        restored_b = await live.graph.get_entity(absorbed.id)
        assert restored_b is not None and restored_b.canonical_name_pl == "Broniek"
        restored_a = await live.graph.get_entity(survivor.id)
        assert restored_a is not None and "Broniek" not in restored_a.aliases
        # the edge is back on B with its original content-addressed id.
        assert await _relation_ids(live) == {add.edge_id}
        # the mention followed B home; the survivor has none.
        assert await _mentions_for(live, absorbed.id) == 1
        assert await _mentions_for(live, survivor.id) == 0
    finally:
        await _delete_project_tree(live, pg_project)


async def test_delete_then_undo_restores_node_edges_and_mentions(live: _Live) -> None:
    victim = GraphEntity(type="Artifact", canonical_name_pl="Czerep", project_id=live.project_id)
    other = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=live.project_id)
    await live.graph.create_entity(victim)
    await live.graph.create_entity(other)
    edge = await live.service.add_relation(live.project_id, victim.id, "GUARDS", other.id)
    pg_project = await _seed_mention(live, victim.id)

    try:
        summary = await live.service.delete_entity(live.project_id, victim.id)
        assert (summary.edges_removed, summary.mentions_removed) == (1, 1)
        # gone from both stores
        assert await live.graph.get_entity(victim.id) is None
        assert await _relation_ids(live) == set()
        assert await _mentions_for(live, victim.id) == 0

        result = await live.service.undo_last(live.project_id)
        assert result.applied is True and result.description == "deleted Czerep"

        # node, its incident edge, and its mention all restored
        restored = await live.graph.get_entity(victim.id)
        assert restored is not None and restored.type == "Artifact"
        assert await _relation_ids(live) == {edge.edge_id}
        assert await _mentions_for(live, victim.id) == 1
    finally:
        await _delete_project_tree(live, pg_project)


async def test_edit_then_undo_restores_fields_via_singleton_coalesce(live: _Live) -> None:
    """A legacy-shape S3a singleton edit (NULL operation_id) is undoable — the read path groups it
    under its own id (`COALESCE(operation_id, id)`)."""
    entity = GraphEntity(
        type="Character",
        canonical_name_pl="Janek",
        properties={"age": 23},
        project_id=live.project_id,
    )
    await live.graph.create_entity(entity)
    await live.service.edit_entity(
        live.project_id, entity.id, EntityEditPatch(type="Deity", properties={"role": "priestess"})
    )

    result = await live.service.undo_last(live.project_id)
    assert result.applied is True

    restored = await live.graph.get_entity(entity.id)
    assert restored is not None
    assert restored.type == "Character"
    assert restored.properties == {"age": 23}


async def test_re_undo_does_not_re_apply(live: _Live) -> None:
    """Undoing the same operation twice can't recur: once undone it is off the live stack, so a
    second undo finds nothing (rather than re-applying the inverse and corrupting state)."""
    entity = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=live.project_id)
    await live.graph.create_entity(entity)
    await live.service.edit_entity(live.project_id, entity.id, EntityEditPatch(type="Deity"))

    await live.service.undo_last(live.project_id)
    with pytest.raises(NothingToUndo):
        await live.service.undo_last(live.project_id)
    # state stayed at the restored value — the second (failed) undo changed nothing
    restored = await live.graph.get_entity(entity.id)
    assert restored is not None and restored.type == "Character"


async def test_undo_refuses_when_the_survivor_drifted(live: _Live) -> None:
    """A merge's undo refuses (→409) if the survivor was edited since — undoing would clobber that
    newer change (lost update in reverse, ADR 0007)."""
    survivor = GraphEntity(
        type="Character", canonical_name_pl="Bronisław", project_id=live.project_id
    )
    absorbed = GraphEntity(
        type="Character", canonical_name_pl="Broniek", project_id=live.project_id
    )
    await live.graph.create_entity(survivor)
    await live.graph.create_entity(absorbed)
    await live.service.merge_entities(live.project_id, absorbed.id, survivor.id, {})

    # drift the survivor *outside* the service (no newer undo-op), so the merge stays the live top.
    current = await live.graph.get_entity(survivor.id)
    assert current is not None
    await live.graph.update_entity(current.model_copy(update={"properties": {"era": "late"}}))

    with pytest.raises(UndoConflict):
        await live.service.undo_last(live.project_id)


async def test_remerge_after_undo_is_not_dropped_by_the_id_collision(live: _Live) -> None:
    """ADR 0007's known design point: a second, genuine merge of the same pair after an undo must
    get a fresh operation id (generation discriminator) or `ON CONFLICT (id) DO NOTHING` would
    silently drop its evidence — leaving the merge un-undoable."""
    survivor = GraphEntity(
        type="Character", canonical_name_pl="Bronisław", project_id=live.project_id
    )
    absorbed = GraphEntity(
        type="Character", canonical_name_pl="Broniek", project_id=live.project_id
    )
    await live.graph.create_entity(survivor)
    await live.graph.create_entity(absorbed)

    await live.service.merge_entities(live.project_id, absorbed.id, survivor.id, {})
    await live.service.undo_last(live.project_id)  # B is back

    # second genuine merge of the same pair — must record fresh evidence and be undoable again.
    await live.service.merge_entities(live.project_id, absorbed.id, survivor.id, {})
    assert await live.graph.get_entity(absorbed.id) is None
    result = await live.service.undo_last(live.project_id)
    assert result.applied is True and result.description == "merged Broniek into Bronisław"
    assert await live.graph.get_entity(absorbed.id) is not None  # the re-merge's undo worked


async def test_merge_with_a_folded_edge_then_undo_keeps_the_survivors_own_edge(live: _Live) -> None:
    """When B and A both relate to a common neighbour, B's edge folds onto A's existing one. Undo
    must restore B's edge **without** deleting A's pre-existing edge (the fold-undo data-loss)."""
    survivor = GraphEntity(
        type="Character", canonical_name_pl="Bronisław", project_id=live.project_id
    )
    absorbed = GraphEntity(
        type="Character", canonical_name_pl="Broniek", project_id=live.project_id
    )
    common = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=live.project_id)
    for entity in (survivor, absorbed, common):
        await live.graph.create_entity(entity)
    a_edge = await live.service.add_relation(live.project_id, survivor.id, "KNOWS", common.id)
    b_edge = await live.service.add_relation(live.project_id, absorbed.id, "KNOWS", common.id)

    # merge folds B's KNOWS edge onto A's existing one (A keeps a single A→Maria edge, B gone)
    summary = await live.service.merge_entities(live.project_id, absorbed.id, survivor.id, {})
    assert summary.folded_count == 1
    assert await _relation_ids(live) == {a_edge.edge_id}

    await live.service.undo_last(live.project_id)

    # B is back with its own edge, AND A still has the edge it owned before the merge
    assert await live.graph.get_entity(absorbed.id) is not None
    assert await _relation_ids(live) == {a_edge.edge_id, b_edge.edge_id}


async def test_undo_of_a_folded_add_does_not_delete_the_pre_existing_edge(live: _Live) -> None:
    """Re-adding a relation that already exists MERGE-folds (creates nothing); undoing that add must
    be a no-op, not a deletion of the edge that was already there."""
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=live.project_id)
    maria = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=live.project_id)
    await live.graph.create_entity(janek)
    await live.graph.create_entity(maria)
    first = await live.service.add_relation(live.project_id, janek.id, "LOVES", maria.id)
    folded = await live.service.add_relation(live.project_id, janek.id, "LOVES", maria.id)
    assert folded.merged_into_existing is True

    result = await live.service.undo_last(live.project_id)  # undoes the folded (no-op) add

    assert result.applied is True
    assert await _relation_ids(live) == {first.edge_id}  # the edge survives


async def test_undo_with_empty_stack_is_not_found(live: _Live) -> None:
    with pytest.raises(NothingToUndo):
        await live.service.undo_last(live.project_id)


async def test_undo_preview_reports_without_applying(live: _Live) -> None:
    entity = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=live.project_id)
    await live.graph.create_entity(entity)
    await live.service.edit_entity(live.project_id, entity.id, EntityEditPatch(type="Deity"))

    preview = await live.service.undo_last(live.project_id, preview_only=True)
    assert preview.applied is False
    # nothing changed — the edit still stands
    still = await live.graph.get_entity(entity.id)
    assert still is not None and still.type == "Deity"
    # and the operation is still live (a real undo afterwards works)
    assert (await live.service.undo_last(live.project_id)).applied is True


async def test_rename_predicate_re_keys_all_bearing_edges_then_undo(live: _Live) -> None:
    """Verify-at-build (DM-NN-4): a graph-wide predicate rename re-keys EVERY bearing edge in one
    grouped op, preserving each `edge_uid` (INV-10), and `undo_last` restores the whole N-edge
    operation as one atom (the graph-wide analogue of S5b's one-edge / merge's fan-out proofs)."""
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=live.project_id)
    maria = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=live.project_id)
    zofia = GraphEntity(type="Character", canonical_name_pl="Zofia", project_id=live.project_id)
    for e in (janek, maria, zofia):
        await live.graph.create_entity(e)
    p1 = await live.service.add_relation(live.project_id, janek.id, "PASSENGER_ON", maria.id)
    p2 = await live.service.add_relation(live.project_id, janek.id, "PASSENGER_ON", zofia.id)
    keep = await live.service.add_relation(live.project_id, maria.id, "LOVES", zofia.id)
    h1 = (await live.graph.get_relation(live.project_id, p1.edge_id)).edge_uid  # type: ignore[union-attr]

    summary = await live.service.rename_predicate(live.project_id, "PASSENGER_ON", "ON_SHIP")

    assert (summary.renamed_count, summary.folded_count) == (2, 0)
    n1 = relation_edge_id(janek.id, "ON_SHIP", maria.id)
    n2 = relation_edge_id(janek.id, "ON_SHIP", zofia.id)
    by_id = {r.id: r for r in await live.graph.get_relations(live.project_id)}
    assert set(by_id) == {n1, n2, keep.edge_id}  # both re-keyed, the LOVES edge untouched
    assert by_id[n1].type == "ON_SHIP" and by_id[n1].edge_uid == h1

    await live.service.undo_last(live.project_id)

    restored = {r.id: r for r in await live.graph.get_relations(live.project_id)}
    assert set(restored) == {p1.edge_id, p2.edge_id, keep.edge_id}
    assert restored[p1.edge_id].type == "PASSENGER_ON"
    assert restored[p1.edge_id].edge_uid == h1


async def test_rename_predicate_folds_a_pre_existing_target_then_undo_unfolds(live: _Live) -> None:
    """Verify-at-build (DM-NN-4, the fold): a bearing edge whose renamed id already exists folds
    onto that survivor (reported, never the goal); the survivor keeps its handle, undo un-folds."""
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=live.project_id)
    maria = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=live.project_id)
    await live.graph.create_entity(janek)
    await live.graph.create_entity(maria)
    doomed = await live.service.add_relation(live.project_id, janek.id, "PASSENGER_ON", maria.id)
    survivor = await live.service.add_relation(live.project_id, janek.id, "ON_SHIP", maria.id)
    survivor_handle = (await live.graph.get_relation(live.project_id, survivor.edge_id)).edge_uid  # type: ignore[union-attr]

    summary = await live.service.rename_predicate(live.project_id, "PASSENGER_ON", "ON_SHIP")

    assert (summary.renamed_count, summary.folded_count) == (0, 1)
    ids = {r.id for r in await live.graph.get_relations(live.project_id)}
    assert ids == {survivor.edge_id}  # doomed folded away; only the survivor remains
    kept = await live.graph.get_relation(live.project_id, survivor.edge_id)
    assert kept is not None and kept.edge_uid == survivor_handle  # survivor keeps its own handle

    await live.service.undo_last(live.project_id)

    ids = {r.id for r in await live.graph.get_relations(live.project_id)}
    assert ids == {doomed.edge_id, survivor.edge_id}  # the folded edge is back


async def test_rename_predicate_to_a_cypher_hostile_label_is_injection_safe(live: _Live) -> None:
    """Verify-at-build (DM-NN-4): the new predicate becomes a Neo4j relationship *type*
    (interpolated, not parameter-bound), so a backtick-bearing label must be `_escape_rel_type`-
    quoted — inherited via `create_relation`. Renaming to it succeeds and reads back verbatim."""
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=live.project_id)
    maria = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=live.project_id)
    await live.graph.create_entity(janek)
    await live.graph.create_entity(maria)
    await live.service.add_relation(live.project_id, janek.id, "PASSENGER_ON", maria.id)
    hostile = "ON`SHIP`]->()"  # backticks would break out of the quoted rel type if unescaped

    summary = await live.service.rename_predicate(live.project_id, "PASSENGER_ON", hostile)

    assert summary.renamed_count == 1
    (edge,) = await live.graph.get_relations(live.project_id)
    assert edge.type == hostile  # the type round-trips exactly, nothing injected


async def test_relabel_entity_type_re_types_matching_nodes_then_undo(live: _Live) -> None:
    """Verify-at-build (DM-NN-5): a bulk type relabel re-sets every matching node's `type`, records
    a complete before-image, and `undo_last` restores every node's original type exactly."""
    a1 = GraphEntity(type="Person", canonical_name_pl="Janek", project_id=live.project_id)
    a2 = GraphEntity(type="Person", canonical_name_pl="Maria", project_id=live.project_id)
    other = GraphEntity(type="Location", canonical_name_pl="Młyn", project_id=live.project_id)
    for e in (a1, a2, other):
        await live.graph.create_entity(e)

    summary = await live.service.relabel_entity_type(live.project_id, "Person", "PERSON")

    assert summary.relabelled_count == 2
    types = {e.id: e.type for e in await live.graph.list_entities(live.project_id)}
    assert types == {a1.id: "PERSON", a2.id: "PERSON", other.id: "Location"}

    await live.service.undo_last(live.project_id)

    restored = {e.id: e.type for e in await live.graph.list_entities(live.project_id)}
    assert restored == {a1.id: "Person", a2.id: "Person", other.id: "Location"}


async def test_relabel_entity_type_to_a_pre_existing_type_never_collapses(live: _Live) -> None:
    """Verify-at-build (DM-NN-5, the asymmetry): relabelling A→B where B already exists does NOT
    merge — the ex-A node and the pre-existing B node coexist as independent nodes both typed B."""
    was_place = GraphEntity(type="Place", canonical_name_pl="Oakhaven", project_id=live.project_id)
    already_loc = GraphEntity(type="LOCATION", canonical_name_pl="Młyn", project_id=live.project_id)
    await live.graph.create_entity(was_place)
    await live.graph.create_entity(already_loc)

    summary = await live.service.relabel_entity_type(live.project_id, "Place", "LOCATION")

    assert summary.relabelled_count == 1
    entities = await live.graph.list_entities(live.project_id)
    assert len(entities) == 2  # nothing collapsed
    assert {e.type for e in entities} == {"LOCATION"}
