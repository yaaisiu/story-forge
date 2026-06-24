"""Integration tests for the project listing routes (multi-story, DM-MS-4).

Exercise `GET /projects` and `GET /projects/{id}/stories` against the throwaway test DB. These are
the read-only surfaces a project/story picker needs: every project with its derived story count
(newest first), and a project's stories (newest first, no body). The `get_connection` dependency is
overridden to share the test transaction, so inserted rows are visible and rolled back on teardown.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from story_forge.adapters.db import get_connection
from story_forge.adapters.postgres_repo import insert_project, insert_story
from story_forge.domain.models import Project, Story
from story_forge.main import app

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def client(db_conn: psycopg.AsyncConnection) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator[psycopg.AsyncConnection]:
        yield db_conn

    app.dependency_overrides[get_connection] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _at(day: int) -> datetime:
    """A distinct timestamp so created_at / ingested_at ordering is deterministic in tests."""
    return datetime(2026, 6, day, tzinfo=UTC)


async def test_list_projects_empty(client: AsyncClient) -> None:
    resp = await client.get("/projects")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


async def test_list_projects_with_story_counts_newest_first(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    older = Project(name="older", language="pl", created_at=_at(1))
    newer = Project(name="newer", language="en", created_at=_at(2))
    await insert_project(db_conn, older)
    await insert_project(db_conn, newer)
    # older has two stories; newer has none (count 0 via the LEFT JOIN).
    await insert_story(db_conn, Story(project_id=older.id, title="s1", raw_text="x"))
    await insert_story(db_conn, Story(project_id=older.id, title="s2", raw_text="x"))

    body = (await client.get("/projects")).json()

    assert [p["id"] for p in body] == [str(newer.id), str(older.id)]  # newest first
    by_id = {p["id"]: p for p in body}
    assert by_id[str(older.id)]["story_count"] == 2
    assert by_id[str(newer.id)]["story_count"] == 0
    assert by_id[str(newer.id)]["language"] == "en"
    assert "style_anchor" not in by_id[str(newer.id)]  # listing shape omits it


async def test_list_project_stories_newest_first(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    project = Project(name="p", language="pl")
    await insert_project(db_conn, project)
    first = Story(project_id=project.id, title="first", raw_text="body-a", ingested_at=_at(1))
    second = Story(project_id=project.id, title="second", raw_text="body-b", ingested_at=_at(2))
    await insert_story(db_conn, first)
    await insert_story(db_conn, second)

    body = (await client.get(f"/projects/{project.id}/stories")).json()

    assert [s["id"] for s in body] == [str(second.id), str(first.id)]  # newest first
    assert body[0]["title"] == "second"
    assert "raw_text" not in body[0]  # listing shape omits the document body


async def test_list_project_stories_empty_for_project_with_no_stories(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    project = Project(name="p", language="pl")
    await insert_project(db_conn, project)

    resp = await client.get(f"/projects/{project.id}/stories")

    assert resp.status_code == 200, resp.text
    assert resp.json() == []


async def test_list_project_stories_unknown_project_404(client: AsyncClient) -> None:
    resp = await client.get(f"/projects/{uuid4()}/stories")
    assert resp.status_code == 404, resp.text
