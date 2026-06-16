"""Integration tests for `GET /stories/{id}/entities?q=` (manual handpick, M3.S4d).

The Stage-4 reviewer can search *all* accepted entities in the project and pick any
one as the merge target — the safety net for a true duplicate the cascade missed
(spec §3.3 *Manual handpick*). Like the graph route, this exercises the HTTP contract
against the throwaway test DB with a *stub* Neo4j repo injected via override: the
repo's real query is covered by `test_neo4j_repo`; here we prove the route resolves
the story to its **project** (the §6.4 tenancy key), ranks by the matcher's RapidFuzz
signal, projects to the search shape, and 404s an unknown story.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from story_forge.adapters.db import get_connection
from story_forge.adapters.postgres_repo import insert_project, insert_story
from story_forge.api.stories import get_neo4j_repo
from story_forge.domain.graph import GraphEntity
from story_forge.domain.models import Project, Story
from story_forge.main import app

pytestmark = pytest.mark.integration


class _StubRepo:
    """Returns canned entities and records the project_id it was asked for."""

    def __init__(self, entities: list[GraphEntity]) -> None:
        self._entities = entities
        self.asked_project: UUID | None = None

    async def list_entities(self, project_id: UUID) -> list[GraphEntity]:
        self.asked_project = project_id
        return self._entities


async def _make_story(conn: psycopg.AsyncConnection) -> Story:
    project = Project(name="t", language="pl")
    story = Story(project_id=project.id, title="t", raw_text="x")
    await insert_project(conn, project)
    await insert_story(conn, story)
    return story


@pytest_asyncio.fixture
async def make_client(db_conn: psycopg.AsyncConnection) -> AsyncIterator[object]:
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


async def test_search_returns_project_entities_ranked(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    janek = GraphEntity(
        type="Character",
        canonical_name_pl="Janek",
        aliases=["młynarczyk z lasu"],  # an alias that does NOT outrank "Jan" for q="Jan"
        project_id=story.project_id,
    )
    jan = GraphEntity(type="Character", canonical_name_pl="Jan", project_id=story.project_id)
    repo = _StubRepo([janek, jan])
    client: AsyncClient = make_client(repo)  # type: ignore[operator]

    resp = await client.get(f"/stories/{story.id}/entities", params={"q": "Jan"})

    assert resp.status_code == 200, resp.text
    # Project-scoped: the route resolved the story to its project before reading.
    assert repo.asked_project == story.project_id
    results = resp.json()["entities"]
    ids = {r["entity_id"] for r in results}
    assert ids == {str(janek.id), str(jan.id)}  # both surfaced (id + name + type)
    by_id = {r["entity_id"]: r for r in results}
    assert by_id[str(jan.id)]["canonical_name"] == "Jan"
    assert by_id[str(jan.id)]["type"] == "Character"
    # The full search row: aliases round-trip (so the card shows *why* it matched), score present.
    assert by_id[str(janek.id)]["aliases"] == ["młynarczyk z lasu"]
    assert isinstance(by_id[str(jan.id)]["score"], (int, float))
    # Ranked best-first: the exact "Jan" outranks the longer "Janek".
    assert results[0]["entity_id"] == str(jan.id)


async def test_search_blank_query_returns_empty(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    repo = _StubRepo(
        [GraphEntity(type="Character", canonical_name_pl="Jan", project_id=story.project_id)]
    )
    client: AsyncClient = make_client(repo)  # type: ignore[operator]

    resp = await client.get(f"/stories/{story.id}/entities", params={"q": "  "})

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"entities": []}


async def test_search_unknown_story_404(make_client: object) -> None:
    repo = _StubRepo([])
    client: AsyncClient = make_client(repo)  # type: ignore[operator]

    resp = await client.get(f"/stories/{uuid4()}/entities", params={"q": "Jan"})

    assert resp.status_code == 404, resp.text
