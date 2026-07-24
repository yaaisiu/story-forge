"""Integration tests for the single-story detail route (Grzymalin S3 — story hub).

Exercise `GET /stories/{story_id}` against the throwaway test DB. This is the light read the
story hub's header needs on a cold deep-link: the story's title + ingest time, *without* the
`raw_text` body. 404s an unknown story (fail-closed). The `get_connection` dependency is
overridden to share the test transaction, so inserted rows are visible and rolled back on teardown.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
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


async def test_get_story_detail_returns_title_without_body(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    project = Project(name="p", language="pl")
    await insert_project(db_conn, project)
    story = Story(project_id=project.id, title="Grzymalin research", raw_text="a long body")
    await insert_story(db_conn, story)

    resp = await client.get(f"/stories/{story.id}")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(story.id)
    assert body["title"] == "Grzymalin research"
    assert "ingested_at" in body
    assert "raw_text" not in body  # detail shape omits the document body


async def test_get_story_detail_unknown_story_404(client: AsyncClient) -> None:
    resp = await client.get(f"/stories/{uuid4()}")
    assert resp.status_code == 404, resp.text
