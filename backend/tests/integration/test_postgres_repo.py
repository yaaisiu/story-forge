"""Repository CRUD against the real `story_forge_test` database.

Each test runs inside the `db_conn` transaction, which is rolled back on
teardown — so the assertions below never need to clean up after themselves.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import psycopg
import pytest
from pgvector import Vector

from story_forge.adapters import postgres_repo as repo
from story_forge.domain.models import (
    Chapter,
    EntityMention,
    MentionSuppression,
    Paragraph,
    Project,
    Scene,
    Story,
)

pytestmark = pytest.mark.integration


async def _make_tree(conn: psycopg.AsyncConnection) -> tuple[Project, Story, Chapter, Scene]:
    """Persist a Project → Story → Chapter → Scene spine and return the nodes."""
    project = Project(name="Test Saga", language="en")
    await repo.insert_project(conn, project)
    story = Story(project_id=project.id, title="Book One", raw_text="Once upon a time.")
    await repo.insert_story(conn, story)
    chapter = Chapter(story_id=story.id, order_index=0, title="Chapter 1")
    await repo.insert_chapter(conn, chapter)
    scene = Scene(chapter_id=chapter.id, order_index=0, title="Opening")
    await repo.insert_scene(conn, scene)
    return project, story, chapter, scene


async def test_project_round_trip(db_conn: psycopg.AsyncConnection) -> None:
    project = Project(name="Test Saga", language="pl", style_anchor="terse")
    await repo.insert_project(db_conn, project)
    assert await repo.get_project(db_conn, project.id) == project


async def test_story_round_trip(db_conn: psycopg.AsyncConnection) -> None:
    project, story, _, _ = await _make_tree(db_conn)
    assert await repo.get_story(db_conn, story.id) == story


async def test_paragraph_round_trip(db_conn: psycopg.AsyncConnection) -> None:
    _, _, _, scene = await _make_tree(db_conn)
    para = Paragraph(scene_id=scene.id, order_index=0, content="Hello.")
    await repo.insert_paragraph(db_conn, para)
    assert await repo.get_paragraph(db_conn, para.id) == para


async def test_get_missing_returns_none(db_conn: psycopg.AsyncConnection) -> None:
    assert await repo.get_project(db_conn, uuid4()) is None


async def test_list_children_ordered_by_order_index(db_conn: psycopg.AsyncConnection) -> None:
    _, story, _, _ = await _make_tree(db_conn)
    # Insert out of order; expect them back sorted by order_index.
    await repo.insert_chapter(db_conn, Chapter(story_id=story.id, order_index=2, title="C2"))
    await repo.insert_chapter(db_conn, Chapter(story_id=story.id, order_index=1, title="C1"))
    chapters = await repo.list_chapters(db_conn, story.id)
    # _make_tree already inserted order_index=0, so we expect 0, 1, 2.
    assert [c.order_index for c in chapters] == [0, 1, 2]
    assert [c.title for c in chapters] == ["Chapter 1", "C1", "C2"]


async def test_delete_project_cascades(db_conn: psycopg.AsyncConnection) -> None:
    project, story, chapter, scene = await _make_tree(db_conn)
    para = Paragraph(scene_id=scene.id, order_index=0, content="leaf")
    await repo.insert_paragraph(db_conn, para)

    await repo.delete_project(db_conn, project.id)

    assert await repo.get_project(db_conn, project.id) is None
    assert await repo.get_story(db_conn, story.id) is None
    assert await repo.get_chapter(db_conn, chapter.id) is None
    assert await repo.get_scene(db_conn, scene.id) is None
    assert await repo.get_paragraph(db_conn, para.id) is None


# --- entity_mentions (the cross-store seam, §6.4 / OQ-1) -------------------


async def _make_paragraph(conn: psycopg.AsyncConnection) -> Paragraph:
    _, _, _, scene = await _make_tree(conn)
    para = Paragraph(scene_id=scene.id, order_index=0, content="Bronek walked in.")
    await repo.insert_paragraph(conn, para)
    return para


async def test_entity_mention_round_trip(db_conn: psycopg.AsyncConnection) -> None:
    # `entity_id` is a free UUID pointing at a Neo4j node — there is deliberately
    # NO Postgres FK on it (the two stores can't share a transaction, OQ-1), so a
    # mention persists against an id Postgres has never seen. That this inserts at
    # all is the cross-store seam working as designed.
    para = await _make_paragraph(db_conn)
    mention = EntityMention(
        paragraph_id=para.id,
        entity_id=uuid4(),
        span_start=0,
        span_end=6,
        confidence=0.9,
    )
    await repo.insert_entity_mention(db_conn, mention)
    assert await repo.list_entity_mentions_for_paragraph(db_conn, para.id) == [mention]


async def test_repoint_entity_mentions_moves_only_the_absorbed_entitys_rows(
    db_conn: psycopg.AsyncConnection,
) -> None:
    """The merge cross-store re-point (M4.S3b, DM-S3b-4): B's mentions move onto A; an unrelated
    entity's mention is untouched; the ids of the moved rows are returned; a re-run is a no-op."""
    para = await _make_paragraph(db_conn)
    absorbed, survivor, bystander = uuid4(), uuid4(), uuid4()
    b1 = EntityMention(paragraph_id=para.id, entity_id=absorbed, span_start=0, span_end=6)
    b2 = EntityMention(paragraph_id=para.id, entity_id=absorbed, span_start=7, span_end=12)
    other = EntityMention(paragraph_id=para.id, entity_id=bystander, span_start=13, span_end=18)
    for mention in (b1, b2, other):
        await repo.insert_entity_mention(db_conn, mention)

    moved = await repo.repoint_entity_mentions(
        db_conn, from_entity_id=absorbed, to_entity_id=survivor
    )
    assert sorted(moved) == sorted([b1.id, b2.id])  # exactly B's rows, by id (for undo)

    by_entity: dict[UUID, int] = {}
    for mention in await repo.list_entity_mentions_for_paragraph(db_conn, para.id):
        by_entity[mention.entity_id] = by_entity.get(mention.entity_id, 0) + 1
    assert by_entity == {survivor: 2, bystander: 1}  # B's two moved to A; bystander untouched

    # Idempotent: a re-run after the move matches no rows.
    assert (
        await repo.repoint_entity_mentions(db_conn, from_entity_id=absorbed, to_entity_id=survivor)
        == []
    )


async def test_entity_mention_nullable_spans_and_confidence(
    db_conn: psycopg.AsyncConnection,
) -> None:
    # The LLM path yields an evidence quote, not reliable offsets, so a mention may
    # carry no spans/confidence (the columns are nullable per the migration).
    para = await _make_paragraph(db_conn)
    mention = EntityMention(paragraph_id=para.id, entity_id=uuid4())
    await repo.insert_entity_mention(db_conn, mention)
    [back] = await repo.list_entity_mentions_for_paragraph(db_conn, para.id)
    assert back == mention
    assert back.span_start is None and back.span_end is None and back.confidence is None


# --- embedding columns (the §3.3 Stage-2 pgvector read/write path, M3.S2) ---

# Values are multiples of 1/8 — exactly representable in pgvector's float32 storage —
# so the round-trip is bit-exact and we can assert plain equality, not approx.
_EXACT_VEC = [(i % 8) / 8.0 for i in range(768)]


async def test_entity_mention_embedding_round_trips_as_vector(
    db_conn: psycopg.AsyncConnection,
) -> None:
    # The per-mention context vector (DM3/DM4): proves the write (pgvector Vector
    # dumper) and the read (vector → list[float]) work end-to-end, which only happens
    # because db.connect registered the type on this connection.
    para = await _make_paragraph(db_conn)
    mention = EntityMention(paragraph_id=para.id, entity_id=uuid4(), embedding=_EXACT_VEC)
    await repo.insert_entity_mention(db_conn, mention)
    [back] = await repo.list_entity_mentions_for_paragraph(db_conn, para.id)
    assert back.embedding == _EXACT_VEC
    assert back == mention


async def test_paragraph_embedding_reads_back_as_vector(
    db_conn: psycopg.AsyncConnection,
) -> None:
    # paragraphs.embedding has no producer yet (foundation-only), so set it directly to
    # prove the un-stubbed read path deserializes a real vector — not None, not a string.
    _, _, _, scene = await _make_tree(db_conn)
    para = Paragraph(scene_id=scene.id, order_index=0, content="x")
    await repo.insert_paragraph(db_conn, para)
    await db_conn.execute(
        "UPDATE paragraphs SET embedding = %s WHERE id = %s", (Vector(_EXACT_VEC), para.id)
    )
    back = await repo.get_paragraph(db_conn, para.id)
    assert back is not None
    assert back.embedding == _EXACT_VEC


async def test_entity_mention_cascades_with_paragraph(db_conn: psycopg.AsyncConnection) -> None:
    # paragraph_id IS a real FK (ON DELETE CASCADE), so deleting the project's tree
    # takes the mention with it — unlike the FK-less entity_id.
    project = Project(name="Cascade Saga", language="en")
    await repo.insert_project(db_conn, project)
    story = Story(project_id=project.id, title="Book", raw_text="x")
    await repo.insert_story(db_conn, story)
    chapter = Chapter(story_id=story.id, order_index=0)
    await repo.insert_chapter(db_conn, chapter)
    scene = Scene(chapter_id=chapter.id, order_index=0)
    await repo.insert_scene(db_conn, scene)
    para = Paragraph(scene_id=scene.id, order_index=0, content="leaf")
    await repo.insert_paragraph(db_conn, para)
    await repo.insert_entity_mention(
        db_conn, EntityMention(paragraph_id=para.id, entity_id=uuid4())
    )

    await repo.delete_project(db_conn, project.id)

    assert await repo.list_entity_mentions_for_paragraph(db_conn, para.id) == []


# --- M4.S3c: manual mentions + suppressions (the reader's write path) -------


async def test_manual_mention_round_trips_with_source_and_offsets(
    db_conn: psycopg.AsyncConnection,
) -> None:
    # A human tag persists a stored span carrying real offsets + source='manual' (DM-S3c-1 B).
    para = await _make_paragraph(db_conn)
    mention = EntityMention(
        paragraph_id=para.id, entity_id=uuid4(), span_start=0, span_end=6, source="manual"
    )
    await repo.insert_entity_mention(db_conn, mention)
    back = await repo.get_entity_mention(db_conn, mention.id)
    assert back == mention
    assert back is not None and back.source == "manual"


async def test_get_entity_mention_missing_returns_none(db_conn: psycopg.AsyncConnection) -> None:
    assert await repo.get_entity_mention(db_conn, uuid4()) is None


async def test_update_entity_mention_span_edits_offsets_in_place(
    db_conn: psycopg.AsyncConnection,
) -> None:
    # "change boundaries" on an already-manual span (DM-S3c-4): offsets move, identity stays.
    para = await _make_paragraph(db_conn)
    mention = EntityMention(
        paragraph_id=para.id, entity_id=uuid4(), span_start=0, span_end=6, source="manual"
    )
    await repo.insert_entity_mention(db_conn, mention)
    await repo.update_entity_mention_span(db_conn, mention_id=mention.id, span_start=7, span_end=12)
    back = await repo.get_entity_mention(db_conn, mention.id)
    assert back is not None and (back.span_start, back.span_end) == (7, 12)


async def test_delete_entity_mention_removes_one_row(db_conn: psycopg.AsyncConnection) -> None:
    para = await _make_paragraph(db_conn)
    keep = EntityMention(paragraph_id=para.id, entity_id=uuid4(), source="manual")
    drop = EntityMention(paragraph_id=para.id, entity_id=uuid4(), source="manual")
    for m in (keep, drop):
        await repo.insert_entity_mention(db_conn, m)
    await repo.delete_entity_mention(db_conn, drop.id)
    assert await repo.get_entity_mention(db_conn, drop.id) is None
    assert await repo.get_entity_mention(db_conn, keep.id) is not None


async def test_suppression_insert_list_for_story_and_delete(
    db_conn: psycopg.AsyncConnection,
) -> None:
    _, story, _, scene = await _make_tree(db_conn)
    para = Paragraph(scene_id=scene.id, order_index=0, content="Janek met Maria.")
    await repo.insert_paragraph(db_conn, para)
    all_entities = MentionSuppression(paragraph_id=para.id, span_start=0, span_end=5)  # entity None
    one_entity = MentionSuppression(
        paragraph_id=para.id, entity_id=uuid4(), span_start=10, span_end=15
    )
    await repo.insert_mention_suppression(db_conn, all_entities)
    await repo.insert_mention_suppression(db_conn, one_entity)

    listed = await repo.list_mention_suppressions_for_story(db_conn, story.id)
    assert {s.id for s in listed} == {all_entities.id, one_entity.id}
    assert any(s.entity_id is None for s in listed)  # "not an entity"

    await repo.delete_mention_suppression(db_conn, all_entities.id)
    listed_after = await repo.list_mention_suppressions_for_story(db_conn, story.id)
    assert {s.id for s in listed_after} == {one_entity.id}


async def test_suppression_insert_is_idempotent(db_conn: psycopg.AsyncConnection) -> None:
    # Deterministic-id re-suppress is a no-op (ON CONFLICT DO NOTHING), like the mention insert.
    para = await _make_paragraph(db_conn)
    supp = MentionSuppression(paragraph_id=para.id, span_start=0, span_end=6)
    await repo.insert_mention_suppression(db_conn, supp)
    await repo.insert_mention_suppression(db_conn, supp)  # second write must not raise/duplicate
    cur = await db_conn.execute(
        "SELECT count(*) FROM mention_suppressions WHERE id = %s", (supp.id,)
    )
    row = await cur.fetchone()
    assert row is not None and row[0] == 1


async def test_suppression_cascades_with_paragraph(db_conn: psycopg.AsyncConnection) -> None:
    # paragraph_id is a real FK (ON DELETE CASCADE) — deleting the tree takes suppressions too.
    project, story, _, scene = await _make_tree(db_conn)
    para = Paragraph(scene_id=scene.id, order_index=0, content="leaf")
    await repo.insert_paragraph(db_conn, para)
    await repo.insert_mention_suppression(
        db_conn, MentionSuppression(paragraph_id=para.id, span_start=0, span_end=4)
    )
    await repo.delete_project(db_conn, project.id)
    assert await repo.list_mention_suppressions_for_story(db_conn, story.id) == []
