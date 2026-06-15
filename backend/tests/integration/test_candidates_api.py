"""HTTP-contract tests for the review-queue routes (M3.S4a, spec §3.3 Stage 4).

Stub the store + review service via dependency overrides (their logic is covered by the unit and
end-to-end integration tests) and assert the route mapping: the queue read, the accept/reject
happy paths, and every declared non-2xx — 404 (story/candidate), 409 (stale merge target), 503
(store outage). Mirrors `test_extract.py`'s stub-coordinator approach.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from psycopg import OperationalError

from story_forge.adapters.db import get_connection
from story_forge.adapters.postgres_repo import insert_project, insert_story
from story_forge.agents.candidate_review import (
    CandidateNotFound,
    ReviewResult,
    StaleMergeTarget,
)
from story_forge.api.stories import get_candidate_review, get_candidate_store
from story_forge.domain.candidates import StagedCandidate
from story_forge.domain.models import Project, Story
from story_forge.main import app

pytestmark = pytest.mark.integration


def _candidate(story_id: UUID) -> StagedCandidate:
    return StagedCandidate(
        project_id=uuid4(),
        story_id=story_id,
        paragraph_id=uuid4(),
        candidate_name="Janek",
        type="Character",
        context="Janek walked.",
        proposal="new",
        stage_reached=1,
    )


class _StubStore:
    def __init__(self, pending: list[StagedCandidate] | Exception) -> None:
        self._pending = pending

    async def list_pending(self, story_id: UUID) -> list[StagedCandidate]:
        if isinstance(self._pending, Exception):
            raise self._pending
        return self._pending


class _StubReview:
    def __init__(self, result: ReviewResult | Exception) -> None:
        self._result = result

    async def accept(self, candidate_id: UUID, **kwargs: object) -> ReviewResult:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result

    async def reject(self, candidate_id: UUID) -> ReviewResult:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


async def _make_story(conn: psycopg.AsyncConnection) -> Story:
    project = Project(name="t", language="pl")
    story = Story(project_id=project.id, title="t", raw_text="x")
    await insert_project(conn, project)
    await insert_story(conn, story)
    return story


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


def _with_store(store: object) -> None:
    app.dependency_overrides[get_candidate_store] = lambda: store


def _with_review(review: object) -> None:
    app.dependency_overrides[get_candidate_review] = lambda: review


# --- GET /candidates -------------------------------------------------------


async def test_list_candidates_returns_pending(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    _with_store(_StubStore([_candidate(story.id)]))
    resp = await client.get(f"/stories/{story.id}/candidates")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [c["candidate_name"] for c in body["candidates"]] == ["Janek"]
    assert body["candidates"][0]["proposal"] == "new"


async def test_list_candidates_unknown_story_404(client: AsyncClient) -> None:
    _with_store(_StubStore([]))
    resp = await client.get(f"/stories/{uuid4()}/candidates")
    assert resp.status_code == 404, resp.text


async def test_list_candidates_store_down_503(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    _with_store(_StubStore(OperationalError("connection refused")))
    resp = await client.get(f"/stories/{story.id}/candidates")
    assert resp.status_code == 503, resp.text


# --- POST accept -----------------------------------------------------------


async def test_accept_happy_path(client: AsyncClient, db_conn: psycopg.AsyncConnection) -> None:
    story = await _make_story(db_conn)
    entity_id = uuid4()
    _with_review(_StubReview(ReviewResult(uuid4(), "created", entity_id, already_decided=False)))
    resp = await client.post(f"/stories/{story.id}/candidates/{uuid4()}/accept", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "created"
    assert body["entity_id"] == str(entity_id)


async def test_accept_unknown_story_404(client: AsyncClient) -> None:
    _with_review(_StubReview(ReviewResult(uuid4(), "created", uuid4(), already_decided=False)))
    resp = await client.post(f"/stories/{uuid4()}/candidates/{uuid4()}/accept", json={})
    assert resp.status_code == 404, resp.text


async def test_accept_unknown_candidate_404(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    _with_review(_StubReview(CandidateNotFound("gone")))
    resp = await client.post(f"/stories/{story.id}/candidates/{uuid4()}/accept", json={})
    assert resp.status_code == 404, resp.text


async def test_accept_stale_merge_target_409(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    _with_review(_StubReview(StaleMergeTarget("target gone")))
    resp = await client.post(f"/stories/{story.id}/candidates/{uuid4()}/accept", json={})
    assert resp.status_code == 409, resp.text


async def test_accept_store_down_503(client: AsyncClient, db_conn: psycopg.AsyncConnection) -> None:
    story = await _make_story(db_conn)
    _with_review(_StubReview(OperationalError("connection refused")))
    resp = await client.post(f"/stories/{story.id}/candidates/{uuid4()}/accept", json={})
    assert resp.status_code == 503, resp.text


# --- POST reject -----------------------------------------------------------


async def test_reject_happy_path(client: AsyncClient, db_conn: psycopg.AsyncConnection) -> None:
    story = await _make_story(db_conn)
    _with_review(_StubReview(ReviewResult(uuid4(), "rejected", None, already_decided=False)))
    resp = await client.post(f"/stories/{story.id}/candidates/{uuid4()}/reject")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rejected"


async def test_reject_unknown_candidate_404(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    _with_review(_StubReview(CandidateNotFound("gone")))
    resp = await client.post(f"/stories/{story.id}/candidates/{uuid4()}/reject")
    assert resp.status_code == 404, resp.text
