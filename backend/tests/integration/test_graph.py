"""Integration tests for `GET /stories/{id}/graph` (spec §3.4 viewer read path).

Exercise the route's HTTP contract against the throwaway test DB with a *stub*
Neo4j repo injected via dependency override — the repo's real graph behaviour is
covered by `test_neo4j_repo`. Here we prove the route resolves the story to its
project, reads the project's nodes/edges, projects them to the viewer shape, and
404s an unknown story.
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
from story_forge.domain.graph import GraphEntity, GraphRelation
from story_forge.domain.models import Project, Story
from story_forge.main import app

pytestmark = pytest.mark.integration


class _StubRepo:
    """Returns canned entities/relations and records the project_id it was asked for."""

    def __init__(self, entities: list[GraphEntity], relations: list[GraphRelation]) -> None:
        self._entities = entities
        self._relations = relations
        self.asked_project: UUID | None = None

    async def list_entities(self, project_id: UUID) -> list[GraphEntity]:
        self.asked_project = project_id
        return self._entities

    async def get_relations(self, project_id: UUID) -> list[GraphRelation]:
        return self._relations


async def _make_story(conn: psycopg.AsyncConnection) -> Story:
    project = Project(name="t", language="pl")
    story = Story(project_id=project.id, title="t", raw_text="x")
    await insert_project(conn, project)
    await insert_story(conn, story)
    return story


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


async def test_graph_returns_nodes_and_edges_for_the_story_project(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    para = uuid4()
    janek = GraphEntity(
        type="Character",
        canonical_name_pl="Janek",
        aliases=["Janek z młyna"],
        first_seen_paragraph_id=para,
        project_id=story.project_id,
    )
    mill = GraphEntity(type="Location", canonical_name_pl="Młyn", project_id=story.project_id)
    rel = GraphRelation(type="LIVES_IN", subject_id=janek.id, object_id=mill.id, confidence=0.9)
    repo = _StubRepo([janek, mill], [rel])
    client: AsyncClient = make_client(repo)  # type: ignore[operator]

    resp = await client.get(f"/stories/{story.id}/graph")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # The route resolved the story to its project before reading the graph.
    assert repo.asked_project == story.project_id
    nodes = {n["id"]: n for n in body["nodes"]}
    assert set(nodes) == {str(janek.id), str(mill.id)}
    assert nodes[str(janek.id)]["type"] == "Character"
    assert nodes[str(janek.id)]["canonical_name_pl"] == "Janek"
    assert nodes[str(janek.id)]["aliases"] == ["Janek z młyna"]
    assert nodes[str(janek.id)]["first_seen_paragraph_id"] == str(para)
    assert body["edges"] == [
        {
            "id": str(rel.id),
            "type": "LIVES_IN",
            "subject_id": str(janek.id),
            "object_id": str(mill.id),
            "confidence": 0.9,
        }
    ]


async def test_graph_empty_for_a_story_with_no_extraction(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    repo = _StubRepo([], [])
    client: AsyncClient = make_client(repo)  # type: ignore[operator]

    resp = await client.get(f"/stories/{story.id}/graph")

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"nodes": [], "edges": []}


async def test_graph_unknown_story_404(make_client: object) -> None:
    repo = _StubRepo([], [])
    client: AsyncClient = make_client(repo)  # type: ignore[operator]

    resp = await client.get(f"/stories/{uuid4()}/graph")

    assert resp.status_code == 404, resp.text
