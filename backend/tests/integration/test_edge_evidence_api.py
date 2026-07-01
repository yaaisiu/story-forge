"""HTTP-contract tests for `GET /stories/{id}/relations/{edge_id}/evidence` (graph-quality S3).

Stub the relation store (its read is covered by `test_edge_evidence_store`) via a dependency
override and seed real paragraphs in the test transaction (the route resolves the rows' texts in one
batched read on the injected connection). Prove the assembled shape, the one-to-many resolution, the
zero-provenance "manually added" edge → 200 + empty list, and the unknown-story 404.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from story_forge.adapters.db import get_connection
from story_forge.adapters.postgres_repo import (
    insert_chapter,
    insert_paragraph,
    insert_project,
    insert_scene,
    insert_story,
)
from story_forge.api.stories import get_relation_store
from story_forge.domain.candidates import StagedRelation
from story_forge.domain.models import Chapter, Paragraph, Project, Scene, Story
from story_forge.main import app

pytestmark = pytest.mark.integration


class _StubRelationStore:
    def __init__(self, rows: list[StagedRelation]) -> None:
        self._rows = rows

    async def get_written_by_edge_id(self, story_id: UUID, edge_id: UUID) -> list[StagedRelation]:
        return self._rows


async def _make_story_with_paragraph(conn: psycopg.AsyncConnection) -> tuple[Story, Paragraph]:
    project = Project(name="t", language="pl")
    story = Story(project_id=project.id, title="t", raw_text="x")
    await insert_project(conn, project)
    await insert_story(conn, story)
    chapter = Chapter(story_id=story.id, order_index=0)
    await insert_chapter(conn, chapter)
    scene = Scene(chapter_id=chapter.id, order_index=0)
    await insert_scene(conn, scene)
    para = Paragraph(scene_id=scene.id, order_index=0, content="Janek knew Mokosz well.")
    await insert_paragraph(conn, para)
    return story, para


def _written(story: Story, paragraph_id: UUID, quote: str | None) -> StagedRelation:
    return StagedRelation(
        id=uuid4(),
        story_id=story.id,
        paragraph_id=paragraph_id,
        subject="Janek",
        predicate="KNOWS",
        object="Mokosz",
        evidence_quote=quote,
        edge_id=uuid4(),
        status="written",
    )


@pytest_asyncio.fixture
async def client(db_conn: psycopg.AsyncConnection) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator[psycopg.AsyncConnection]:
        yield db_conn

    app.dependency_overrides[get_connection] = _override
    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        yield ac
    finally:
        await ac.aclose()
        app.dependency_overrides.clear()


def _with_store(rows: list[StagedRelation]) -> None:
    app.dependency_overrides[get_relation_store] = lambda: _StubRelationStore(rows)


async def test_evidence_assembles_predicate_and_paragraph_text(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story, para = await _make_story_with_paragraph(db_conn)
    _with_store([_written(story, para.id, "Janek knew her.")])

    resp = await client.get(f"/stories/{story.id}/relations/{uuid4()}/evidence")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["predicate"] == "KNOWS"
    assert body["source_provenance"] == [
        {
            "paragraph_id": str(para.id),
            "paragraph_text": "Janek knew Mokosz well.",
            "evidence_quote": "Janek knew her.",
        }
    ]


async def test_evidence_resolves_each_source_paragraph_one_to_many(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    # An edge asserted in two paragraphs → two rows; the batched fetch must map each row to its
    # own paragraph text (not conflate them).
    story, para1 = await _make_story_with_paragraph(db_conn)
    para2 = Paragraph(scene_id=para1.scene_id, order_index=1, content="Second mention of the bond.")
    await insert_paragraph(db_conn, para2)
    edge = uuid4()
    r1 = _written(story, para1.id, "quote one")
    r1.edge_id = edge
    r2 = _written(story, para2.id, "quote two")
    r2.edge_id = edge
    _with_store([r1, r2])

    resp = await client.get(f"/stories/{story.id}/relations/{edge}/evidence")

    assert resp.status_code == 200, resp.text
    by_para = {s["paragraph_id"]: s for s in resp.json()["source_provenance"]}
    assert by_para[str(para1.id)]["paragraph_text"] == "Janek knew Mokosz well."
    assert by_para[str(para2.id)]["paragraph_text"] == "Second mention of the bond."
    assert {s["evidence_quote"] for s in resp.json()["source_provenance"]} == {
        "quote one",
        "quote two",
    }


async def test_zero_provenance_edge_returns_empty_not_404(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story, _para = await _make_story_with_paragraph(db_conn)
    _with_store([])  # a manually-added edge has no staged rows

    resp = await client.get(f"/stories/{story.id}/relations/{uuid4()}/evidence")

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"predicate": None, "source_provenance": []}


async def test_unknown_story_404(client: AsyncClient) -> None:
    _with_store([])
    resp = await client.get(f"/stories/{uuid4()}/relations/{uuid4()}/evidence")
    assert resp.status_code == 404, resp.text
