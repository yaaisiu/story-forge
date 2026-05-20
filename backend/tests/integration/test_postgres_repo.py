"""Repository CRUD against the real `story_forge_test` database.

Each test runs inside the `db_conn` transaction, which is rolled back on
teardown — so the assertions below never need to clean up after themselves.
"""

from __future__ import annotations

import psycopg
import pytest

from story_forge.adapters import postgres_repo as repo
from story_forge.domain.models import Chapter, Paragraph, Project, Scene, Story

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
    from uuid import uuid4

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
