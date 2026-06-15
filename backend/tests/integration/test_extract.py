"""Integration tests for `POST /stories/{id}/extract` (spec §9 M2).

Exercise the route's HTTP contract against the throwaway test DB with a *stub*
coordinator (no real LLM, no Neo4j) injected via dependency override — the
coordinator's own persistence is covered by `test_extraction_persistence`. Here we
prove the route reads the story's paragraphs, maps a hard failure to 502, and turns
the resumable pause into a 202 with partial progress.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
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
from story_forge.agents.extraction_agent import ExtractionError
from story_forge.agents.extraction_coordinator import IngestResult
from story_forge.api.stories import get_extraction_coordinator
from story_forge.domain.models import Chapter, Paragraph, Project, Scene, Story
from story_forge.main import app

pytestmark = pytest.mark.integration


class _StubCoordinator:
    """Returns a canned `IngestResult` (or raises) without touching any store."""

    def __init__(self, result: IngestResult | Exception) -> None:
        self._result = result
        self.seen_paragraphs: int | None = None

    async def ingest_story(
        self, *, paragraphs: list[Paragraph], project_id: object, story_id: object, language: str
    ) -> IngestResult:
        self.seen_paragraphs = len(paragraphs)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


async def _make_story_with_paragraphs(conn: psycopg.AsyncConnection, n: int) -> Story:
    project = Project(name="t", language="pl")
    story = Story(project_id=project.id, title="t", raw_text="x")
    chapter = Chapter(story_id=story.id, order_index=0)
    scene = Scene(chapter_id=chapter.id, order_index=0)
    await insert_project(conn, project)
    await insert_story(conn, story)
    await insert_chapter(conn, chapter)
    await insert_scene(conn, scene)
    for i in range(n):
        await insert_paragraph(conn, Paragraph(scene_id=scene.id, order_index=i, content=f"p{i}"))
    return story


@pytest_asyncio.fixture
async def make_client(db_conn: psycopg.AsyncConnection) -> AsyncIterator[object]:
    """Factory: given a coordinator, return a client sharing the test transaction."""

    async def _override() -> AsyncIterator[psycopg.AsyncConnection]:
        yield db_conn

    app.dependency_overrides[get_connection] = _override
    clients: list[AsyncClient] = []

    def _factory(coordinator: object) -> AsyncClient:
        app.dependency_overrides[get_extraction_coordinator] = lambda: coordinator
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clients.append(client)
        return client

    yield _factory
    for client in clients:
        await client.aclose()
    app.dependency_overrides.clear()


async def test_extract_completes_returns_200_with_counts(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story_with_paragraphs(db_conn, 3)
    coordinator = _StubCoordinator(
        IngestResult(
            paragraphs_total=3,
            paragraphs_done=3,
            candidates_staged=5,
            paused=False,
            pause_reason=None,
        )
    )
    client: AsyncClient = make_client(coordinator)  # type: ignore[operator]

    resp = await client.post(f"/stories/{story.id}/extract")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["paused"] is False
    assert body["paragraphs_done"] == 3
    assert body["candidates_staged"] == 5
    # The route handed the story's three persisted paragraphs to the coordinator.
    assert coordinator.seen_paragraphs == 3


async def test_extract_pause_returns_202_with_partial_progress(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story_with_paragraphs(db_conn, 4)
    coordinator = _StubCoordinator(
        IngestResult(
            paragraphs_total=4,
            paragraphs_done=2,
            candidates_staged=3,
            paused=True,
            pause_reason="daily budget reached",
        )
    )
    client: AsyncClient = make_client(coordinator)  # type: ignore[operator]

    resp = await client.post(f"/stories/{story.id}/extract")

    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["paused"] is True
    assert body["paragraphs_done"] == 2
    assert body["pause_reason"] == "daily budget reached"


async def test_extract_unknown_story_404(make_client: object) -> None:
    from uuid import uuid4

    coordinator = _StubCoordinator(
        IngestResult(
            paragraphs_total=0,
            paragraphs_done=0,
            candidates_staged=0,
            paused=False,
            pause_reason=None,
        )
    )
    client: AsyncClient = make_client(coordinator)  # type: ignore[operator]
    resp = await client.post(f"/stories/{uuid4()}/extract")
    assert resp.status_code == 404, resp.text


async def test_extract_agent_failure_maps_to_502(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story_with_paragraphs(db_conn, 1)
    coordinator = _StubCoordinator(ExtractionError("gave up after retries"))
    client: AsyncClient = make_client(coordinator)  # type: ignore[operator]

    resp = await client.post(f"/stories/{story.id}/extract")

    assert resp.status_code == 502, resp.text
    assert "gave up" in resp.json()["detail"]


async def test_extract_router_transport_failure_maps_to_502(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # When the wired router exhausts failover, it re-raises its terminal httpx error
    # (provider outage, 5xx, or a 401 from bad Ollama Cloud creds). That must surface
    # as the documented 502, not FastAPI's default 500.
    story = await _make_story_with_paragraphs(db_conn, 1)
    coordinator = _StubCoordinator(httpx.ConnectError("connection refused"))
    client: AsyncClient = make_client(coordinator)  # type: ignore[operator]

    resp = await client.post(f"/stories/{story.id}/extract")

    assert resp.status_code == 502, resp.text
