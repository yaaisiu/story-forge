"""Integration tests for `GET /stories/{id}/reader` (spec §3.5 inline highlights, M4.S1).

Exercise the read-only reader projection against the throwaway test DB with a *stub* Neo4j
repo (entities are project-scoped, the §3.4 seam). The route's job: load the story's
paragraphs (Postgres) + their entity mentions, cross-join each mention to its accepted Neo4j
entity in app code, resolve where each entity's surface forms (canonical + aliases) sit in the
paragraph (`resolve_highlights`, unit-tested separately), and return per-paragraph decorated
ranges + a tooltip catalog of the entities that actually appeared. Fail-closed: an entity whose
forms don't occur is omitted, not guessed.
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
    insert_entity_mention,
    insert_paragraph,
    insert_project,
    insert_scene,
    insert_story,
)
from story_forge.api.stories import get_neo4j_repo
from story_forge.domain.graph import GraphEntity
from story_forge.domain.models import (
    Chapter,
    EntityMention,
    Paragraph,
    Project,
    Scene,
    Story,
)
from story_forge.main import app

pytestmark = pytest.mark.integration


class _StubRepo:
    """Returns canned project entities and records the project_id it was asked for."""

    def __init__(self, entities: list[GraphEntity]) -> None:
        self._entities = entities
        self.asked_project: UUID | None = None

    async def list_entities(self, project_id: UUID) -> list[GraphEntity]:
        self.asked_project = project_id
        return self._entities


async def _make_paragraphs(
    conn: psycopg.AsyncConnection, *contents: str
) -> tuple[Story, list[Paragraph]]:
    """Insert a single-chapter, single-scene story whose scene holds `contents` in order."""
    project = Project(name="t", language="pl")
    story = Story(project_id=project.id, title="t", raw_text="x")
    chapter = Chapter(story_id=story.id, order_index=0)
    scene = Scene(chapter_id=chapter.id, order_index=0)
    await insert_project(conn, project)
    await insert_story(conn, story)
    await insert_chapter(conn, chapter)
    await insert_scene(conn, scene)
    paragraphs = [
        Paragraph(scene_id=scene.id, order_index=i, content=content)
        for i, content in enumerate(contents)
    ]
    for paragraph in paragraphs:
        await insert_paragraph(conn, paragraph)
    return story, paragraphs


async def _mention(
    conn: psycopg.AsyncConnection, paragraph: Paragraph, entity: GraphEntity
) -> None:
    await insert_entity_mention(conn, EntityMention(paragraph_id=paragraph.id, entity_id=entity.id))


@pytest_asyncio.fixture
async def make_client(db_conn: psycopg.AsyncConnection) -> AsyncIterator[object]:
    """Factory: given a repo, return a client sharing the test transaction."""

    async def _override() -> AsyncIterator[psycopg.AsyncConnection]:
        yield db_conn

    app.dependency_overrides[get_connection] = _override
    clients: list[AsyncClient] = []

    def _factory(repo: object) -> AsyncClient:
        app.dependency_overrides[get_neo4j_repo] = lambda: repo
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clients.append(client)
        return client

    yield _factory
    for client in clients:
        await client.aclose()
    app.dependency_overrides.clear()


async def test_reader_highlights_mentioned_entities(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, (para,) = await _make_paragraphs(db_conn, "Janek met Maria.")
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=story.project_id)
    maria = GraphEntity(
        type="Character",
        canonical_name_pl="Maria",
        aliases=["Marysia"],
        project_id=story.project_id,
    )
    await _mention(db_conn, para, janek)
    await _mention(db_conn, para, maria)
    client: AsyncClient = make_client(_StubRepo([janek, maria]))  # type: ignore[operator]

    resp = await client.get(f"/stories/{story.id}/reader")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [p["id"] for p in body["paragraphs"]] == [str(para.id)]
    paragraph = body["paragraphs"][0]
    assert paragraph["text"] == "Janek met Maria."
    assert paragraph["highlights"] == [
        {"start": 0, "end": 5, "entity_id": str(janek.id), "type": "Character"},
        {"start": 10, "end": 15, "entity_id": str(maria.id), "type": "Character"},
    ]
    # The tooltip catalog carries only entities that actually appeared, with display name + aliases.
    catalog = {e["entity_id"]: e for e in body["entities"]}
    assert set(catalog) == {str(janek.id), str(maria.id)}
    assert catalog[str(maria.id)] == {
        "entity_id": str(maria.id),
        "canonical_name": "Maria",
        "type": "Character",
        "aliases": ["Marysia"],
    }


async def test_reader_inflected_mention_matched_via_alias(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # The cross-store join feeds aliases into the resolver, so the inflected surface form
    # "Jankowi" (stored as an alias by a prior merge-accept) is highlighted.
    story, (para,) = await _make_paragraphs(db_conn, "Dał Jankowi książkę.")
    janek = GraphEntity(
        type="Character",
        canonical_name_pl="Janek",
        aliases=["Jankowi"],
        project_id=story.project_id,
    )
    await _mention(db_conn, para, janek)
    client: AsyncClient = make_client(_StubRepo([janek]))  # type: ignore[operator]

    resp = await client.get(f"/stories/{story.id}/reader")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["paragraphs"][0]["highlights"] == [
        {"start": 4, "end": 11, "entity_id": str(janek.id), "type": "Character"},
    ]


async def test_reader_omits_unresolvable_and_unmentioned(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # para0: a mention whose entity's name does not occur in the text → omitted (fail-closed).
    # para1: no mentions at all → plain text, no highlights.
    story, (para0, para1) = await _make_paragraphs(db_conn, "A quiet room.", "Nothing here either.")
    ghost = GraphEntity(type="Character", canonical_name_pl="Zbyszek", project_id=story.project_id)
    await _mention(db_conn, para0, ghost)
    repo = _StubRepo([ghost])
    client: AsyncClient = make_client(repo)  # type: ignore[operator]

    resp = await client.get(f"/stories/{story.id}/reader")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [p["text"] for p in body["paragraphs"]] == ["A quiet room.", "Nothing here either."]
    assert all(p["highlights"] == [] for p in body["paragraphs"])
    # Nothing appeared, so the catalog is empty (no tooltips advertised for absent entities).
    assert body["entities"] == []
    # The route resolved the story to its project before the entity read.
    assert repo.asked_project == story.project_id


async def test_reader_unknown_story_404(make_client: object) -> None:
    client: AsyncClient = make_client(_StubRepo([]))  # type: ignore[operator]

    resp = await client.get(f"/stories/{uuid4()}/reader")

    assert resp.status_code == 404, resp.text
