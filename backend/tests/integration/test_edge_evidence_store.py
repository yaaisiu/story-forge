"""Integration: `PostgresRelationStore.get_written_by_edge_id` (graph-quality S3, DM-EE-2).

The store reads on its **own** short-lived connection, so (like `test_relations`) the fixture
commits its seed to the throwaway test DB and cleans up by deleting the project (staged rows
cascade off the `paragraph_id` FK). Proves the by-`edge_id` read returns the complete one-to-many
`written` set for a story, ordered by staging time, and excludes non-`written`, other-edge, and
other-story rows.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio

from story_forge.adapters import postgres_repo as repo
from story_forge.adapters.db import libpq_kwargs
from story_forge.adapters.postgres_relation_store import PostgresRelationStore
from story_forge.config import settings
from story_forge.domain.candidates import StagedRelation
from story_forge.domain.models import Chapter, Paragraph, Project, Scene, Story

pytestmark = pytest.mark.integration


@dataclass
class _Seed:
    store: PostgresRelationStore
    story: Story
    paragraphs: list[Paragraph]
    project_id: UUID


@pytest_asyncio.fixture
async def seed(_migrated_test_db: None) -> AsyncIterator[_Seed]:
    conninfo = libpq_kwargs(settings.test_database_url)
    project = Project(name="Edge Evidence Test", language="pl")
    story = Story(project_id=project.id, title="Book", raw_text="x")
    chapter = Chapter(story_id=story.id, order_index=0)
    scene = Scene(chapter_id=chapter.id, order_index=0)
    paragraphs = [
        Paragraph(scene_id=scene.id, order_index=0, content="Janek knew Mokosz."),
        Paragraph(scene_id=scene.id, order_index=1, content="Again, Janek knew Mokosz."),
    ]
    async with await psycopg.AsyncConnection.connect(autocommit=True, **conninfo) as conn:  # type: ignore[arg-type]
        await repo.insert_project(conn, project)
        await repo.insert_story(conn, story)
        await repo.insert_chapter(conn, chapter)
        await repo.insert_scene(conn, scene)
        for paragraph in paragraphs:
            await repo.insert_paragraph(conn, paragraph)
    try:
        yield _Seed(PostgresRelationStore(conninfo), story, paragraphs, project.id)
    finally:
        async with await psycopg.AsyncConnection.connect(autocommit=True, **conninfo) as conn:  # type: ignore[arg-type]
            await repo.delete_project(conn, project.id)  # cascades staged relations


def _written(story: Story, paragraph_id: UUID, edge_id: UUID, quote: str) -> StagedRelation:
    return StagedRelation(
        id=uuid4(),
        story_id=story.id,
        paragraph_id=paragraph_id,
        subject="Janek",
        predicate="KNOWS",
        object="Mokosz",
        evidence_quote=quote,
        edge_id=edge_id,
        status="written",
    )


async def _insert(seed: _Seed, *rows: StagedRelation) -> None:
    conninfo = libpq_kwargs(settings.test_database_url)
    async with await psycopg.AsyncConnection.connect(autocommit=True, **conninfo) as conn:  # type: ignore[arg-type]
        for row in rows:
            await PostgresRelationStore.insert(conn, row)


async def test_returns_all_written_rows_for_the_edge_ordered(seed: _Seed) -> None:
    edge_id = uuid4()
    r0 = _written(seed.story, seed.paragraphs[0].id, edge_id, "Janek knew her.")
    r1 = _written(seed.story, seed.paragraphs[1].id, edge_id, "He knew her still.")
    await _insert(seed, r0, r1)

    got = await seed.store.get_written_by_edge_id(seed.story.id, edge_id)

    assert [r.id for r in got] == [r0.id, r1.id]  # ordered by created_at
    assert {r.paragraph_id for r in got} == {seed.paragraphs[0].id, seed.paragraphs[1].id}
    assert all(r.status == "written" and r.edge_id == edge_id for r in got)


async def test_excludes_non_written_other_edge_and_other_story_rows(seed: _Seed) -> None:
    edge_id = uuid4()
    keep = _written(seed.story, seed.paragraphs[0].id, edge_id, "kept")
    # a staged (not written) row on the same edge
    staged = _written(seed.story, seed.paragraphs[1].id, edge_id, "not yet")
    staged.status = "staged"
    # a written row on a *different* edge
    other_edge = _written(seed.story, seed.paragraphs[1].id, uuid4(), "other edge")
    await _insert(seed, keep, staged, other_edge)

    got = await seed.store.get_written_by_edge_id(seed.story.id, edge_id)
    assert [r.id for r in got] == [keep.id]

    # the same edge id, queried under a different story, sees nothing
    assert await seed.store.get_written_by_edge_id(uuid4(), edge_id) == []


async def test_unknown_edge_yields_empty_list(seed: _Seed) -> None:
    assert await seed.store.get_written_by_edge_id(seed.story.id, uuid4()) == []
