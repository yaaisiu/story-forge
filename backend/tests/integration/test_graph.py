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
from story_forge.adapters.postgres_repo import (
    insert_chapter,
    insert_entity_mention,
    insert_paragraph,
    insert_project,
    insert_scene,
    insert_story,
)
from story_forge.api.stories import get_neo4j_repo
from story_forge.domain.graph import GraphEntity, GraphRelation
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


async def _add_story_with_paragraph(
    conn: psycopg.AsyncConnection, project_id: UUID
) -> tuple[Story, Paragraph]:
    """Add a story (with a one-paragraph document tree) under an existing project.

    Returns the story and its paragraph so a test can seed `entity_mentions` rolling up to it —
    the real Postgres side the story-scope filter reads (the Neo4j graph stays stubbed).
    """
    story = Story(project_id=project_id, title="t", raw_text="x")
    await insert_story(conn, story)
    chapter = Chapter(story_id=story.id, order_index=0)
    await insert_chapter(conn, chapter)
    scene = Scene(chapter_id=chapter.id, order_index=0)
    await insert_scene(conn, scene)
    para = Paragraph(scene_id=scene.id, order_index=0, content="...")
    await insert_paragraph(conn, para)
    return story, para


async def _mention(conn: psycopg.AsyncConnection, paragraph_id: UUID, entity_id: UUID) -> None:
    """Seed an accepted mention of `entity_id` in `paragraph_id` (the membership signal)."""
    await insert_entity_mention(
        conn,
        EntityMention(paragraph_id=paragraph_id, entity_id=entity_id, source="extraction"),
    )


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

    # scope=project returns the whole project graph (the mapping/shape assertion here is
    # scope-independent; the default scope=story narrowing is covered by the tests below).
    resp = await client.get(f"/stories/{story.id}/graph?scope=project")

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


async def test_graph_scope_story_narrows_to_story_members_and_subset_of_project(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # One project, two stories. janek is mentioned in story A; mill only in story B. The project
    # graph (stub) holds both entities and the janek→mill edge asserted in A.
    project = Project(name="t", language="pl")
    await insert_project(db_conn, project)
    story_a, para_a = await _add_story_with_paragraph(db_conn, project.id)
    _story_b, para_b = await _add_story_with_paragraph(db_conn, project.id)
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=project.id)
    mill = GraphEntity(type="Location", canonical_name_pl="Młyn", project_id=project.id)
    rel = GraphRelation(
        type="LIVES_IN",
        subject_id=janek.id,
        object_id=mill.id,
        confidence=0.9,
        source_paragraph_id=para_a.id,
    )
    await _mention(db_conn, para_a.id, janek.id)
    await _mention(db_conn, para_b.id, mill.id)
    repo = _StubRepo([janek, mill], [rel])
    client: AsyncClient = make_client(repo)  # type: ignore[operator]

    story_scope = (await client.get(f"/stories/{story_a.id}/graph?scope=story")).json()
    project_scope = (await client.get(f"/stories/{story_a.id}/graph?scope=project")).json()

    # story A: only janek is a member; mill is not, so the janek→mill edge has a dangling
    # endpoint and is excluded — a clean self-contained subgraph.
    assert {n["id"] for n in story_scope["nodes"]} == {str(janek.id)}
    assert story_scope["edges"] == []
    # project scope is the whole graph; "this story" ⊆ "whole project" (the build-time property).
    assert {n["id"] for n in project_scope["nodes"]} == {str(janek.id), str(mill.id)}
    assert {n["id"] for n in story_scope["nodes"]} <= {n["id"] for n in project_scope["nodes"]}


async def test_graph_scope_defaults_to_story(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    project = Project(name="t", language="pl")
    await insert_project(db_conn, project)
    story_a, para_a = await _add_story_with_paragraph(db_conn, project.id)
    _story_b, _para_b = await _add_story_with_paragraph(db_conn, project.id)
    janek = GraphEntity(type="Character", project_id=project.id)
    mill = GraphEntity(type="Location", project_id=project.id)  # mentioned nowhere in A
    await _mention(db_conn, para_a.id, janek.id)
    repo = _StubRepo([janek, mill], [])
    client: AsyncClient = make_client(repo)  # type: ignore[operator]

    default = (await client.get(f"/stories/{story_a.id}/graph")).json()
    explicit = (await client.get(f"/stories/{story_a.id}/graph?scope=story")).json()

    assert default == explicit
    assert {n["id"] for n in default["nodes"]} == {str(janek.id)}


async def test_graph_scope_story_is_noop_for_single_story_project_incl_manual_edge(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # The DM-MS-2 verify-at-build: for a single-story project, scope=story == scope=project.
    project = Project(name="t", language="pl")
    await insert_project(db_conn, project)
    story, para = await _add_story_with_paragraph(db_conn, project.id)
    janek = GraphEntity(type="Character", project_id=project.id)
    mill = GraphEntity(type="Location", project_id=project.id)
    extracted = GraphRelation(
        type="LIVES_IN",
        subject_id=janek.id,
        object_id=mill.id,
        confidence=0.9,
        source_paragraph_id=para.id,
    )
    # A hand-added edge has no source paragraph; it must still show in the story view.
    manual = GraphRelation(type="KNOWS", subject_id=mill.id, object_id=janek.id, confidence=1.0)
    await _mention(db_conn, para.id, janek.id)
    await _mention(db_conn, para.id, mill.id)
    repo = _StubRepo([janek, mill], [extracted, manual])
    client: AsyncClient = make_client(repo)  # type: ignore[operator]

    story_scope = (await client.get(f"/stories/{story.id}/graph?scope=story")).json()
    project_scope = (await client.get(f"/stories/{story.id}/graph?scope=project")).json()

    assert story_scope == project_scope
    assert {e["id"] for e in story_scope["edges"]} == {str(extracted.id), str(manual.id)}


async def test_graph_scope_story_excludes_edge_asserted_in_another_story(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # Both endpoints are members of story A, but the edge was asserted in story B's paragraph —
    # the source-paragraph rule excludes it from A's view even though both nodes are present.
    project = Project(name="t", language="pl")
    await insert_project(db_conn, project)
    story_a, para_a = await _add_story_with_paragraph(db_conn, project.id)
    _story_b, para_b = await _add_story_with_paragraph(db_conn, project.id)
    janek = GraphEntity(type="Character", project_id=project.id)
    mill = GraphEntity(type="Location", project_id=project.id)
    rel = GraphRelation(
        type="LIVES_IN",
        subject_id=janek.id,
        object_id=mill.id,
        confidence=0.9,
        source_paragraph_id=para_b.id,  # asserted in the *other* story
    )
    await _mention(db_conn, para_a.id, janek.id)
    await _mention(db_conn, para_a.id, mill.id)
    repo = _StubRepo([janek, mill], [rel])
    client: AsyncClient = make_client(repo)  # type: ignore[operator]

    story_scope = (await client.get(f"/stories/{story_a.id}/graph?scope=story")).json()

    assert {n["id"] for n in story_scope["nodes"]} == {str(janek.id), str(mill.id)}
    assert story_scope["edges"] == []


async def test_graph_scope_story_empty_for_zero_mention_story(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    project = Project(name="t", language="pl")
    await insert_project(db_conn, project)
    story, _para = await _add_story_with_paragraph(db_conn, project.id)
    janek = GraphEntity(type="Character", project_id=project.id)
    repo = _StubRepo([janek], [])  # project graph is non-empty, but the story has no mentions
    client: AsyncClient = make_client(repo)  # type: ignore[operator]

    body = (await client.get(f"/stories/{story.id}/graph?scope=story")).json()

    assert body == {"nodes": [], "edges": []}
