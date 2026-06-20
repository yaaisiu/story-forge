"""Integration tests for `GET /stories/{id}/entities/{eid}` (spec §3.4/§3.5 side panel, M4.S2a).

The read behind the reader side panel: resolve the story → its project (the §3.4 tenancy seam),
confirm the entity belongs to that project, and return its display fields + free-form `properties`
+ the 1-hop ego-graph (`build_ego_graph` over the repo's `get_neighbourhood`). Postgres is real
(the throwaway test DB, for the story→project resolution); the Neo4j repo is a *stub* returning
canned entity + neighbourhood, the same shape `test_reader.py` uses. Read-only — no graph write.
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
    """Returns a canned entity (by id) + a canned incident neighbourhood."""

    def __init__(
        self,
        entity: GraphEntity | None,
        incident: list[tuple[GraphRelation, GraphEntity]] | None = None,
    ) -> None:
        self._entity = entity
        self._incident = incident or []

    async def get_entity(self, entity_id: UUID) -> GraphEntity | None:
        if self._entity is not None and self._entity.id == entity_id:
            return self._entity
        return None

    async def get_neighbourhood(self, entity_id: UUID) -> list[tuple[GraphRelation, GraphEntity]]:
        return self._incident


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


async def test_entity_detail_returns_details_properties_and_ego_graph(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    janek = GraphEntity(
        type="Character",
        canonical_name_pl="Janek",
        aliases=["Janek z młyna"],
        properties={"role": "miller", "age": 23},
        project_id=story.project_id,
    )
    maria = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=story.project_id)
    garret = GraphEntity(type="Character", canonical_name_pl="Garret", project_id=story.project_id)
    out_edge = GraphRelation(type="LOVES", subject_id=janek.id, object_id=maria.id, confidence=0.9)
    in_edge = GraphRelation(
        type="EMPLOYS", subject_id=garret.id, object_id=janek.id, confidence=0.8
    )
    repo = _StubRepo(janek, [(out_edge, maria), (in_edge, garret)])
    client: AsyncClient = make_client(repo)  # type: ignore[operator]

    resp = await client.get(f"/stories/{story.id}/entities/{janek.id}")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["entity_id"] == str(janek.id)
    assert body["canonical_name"] == "Janek"
    # The project's working language, so the editable side panel (M4.S3a-fe) knows which
    # canonical-name slot a single-field name edit writes to (one language per project at PoC).
    assert body["language"] == "pl"
    assert body["type"] == "Character"
    assert body["aliases"] == ["Janek z młyna"]
    assert body["properties"] == {"role": "miller", "age": 23}
    neighbours = {n["entity_id"]: n for n in body["ego_graph"]["neighbours"]}
    assert set(neighbours) == {str(maria.id), str(garret.id)}
    edges = {e["id"]: e for e in body["ego_graph"]["edges"]}
    assert edges[str(out_edge.id)]["direction"] == "out"
    assert edges[str(out_edge.id)]["neighbour_id"] == str(maria.id)
    assert edges[str(in_edge.id)]["direction"] == "in"
    assert edges[str(in_edge.id)]["neighbour_id"] == str(garret.id)


async def test_entity_detail_unknown_story_404(make_client: object) -> None:
    client: AsyncClient = make_client(_StubRepo(None))  # type: ignore[operator]
    resp = await client.get(f"/stories/{uuid4()}/entities/{uuid4()}")
    assert resp.status_code == 404, resp.text


async def test_entity_detail_entity_in_other_project_404(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # The story exists and the entity exists, but it belongs to a *different* project — the
    # route must 404 (never leak another project's node), exercising the project_id guard.
    story = await _make_story(db_conn)
    foreign = GraphEntity(type="Character", canonical_name_pl="Obcy", project_id=uuid4())
    client: AsyncClient = make_client(_StubRepo(foreign))  # type: ignore[operator]
    resp = await client.get(f"/stories/{story.id}/entities/{foreign.id}")
    assert resp.status_code == 404, resp.text
