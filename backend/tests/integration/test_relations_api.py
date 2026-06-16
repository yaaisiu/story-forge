"""HTTP-contract tests for the decide-relations routes (M3.S4e, spec §3.3's 5th action).

Stub the relation-review service via a dependency override (its logic is covered by the unit
and end-to-end integration tests) and assert the route mapping: the committable-list read, the
commit/reject happy paths, and every declared non-2xx — 404 (story/relation), 409 (a stale/held
endpoint), 503 (store outage). Mirrors `test_candidates_api.py`.
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
from story_forge.agents.relation_review import (
    CommittableRelation,
    RelationDecisionResult,
    RelationEndpointsUnresolved,
    RelationNotFound,
)
from story_forge.api.stories import get_relation_review
from story_forge.domain.candidates import StagedRelation, staged_relation_id
from story_forge.domain.models import Project, Story
from story_forge.main import app

pytestmark = pytest.mark.integration


def _committable(story_id: UUID) -> CommittableRelation:
    paragraph_id = uuid4()
    relation = StagedRelation(
        id=staged_relation_id(paragraph_id, "Janek", "KNOWS", "Mokosz"),
        story_id=story_id,
        paragraph_id=paragraph_id,
        subject="Janek",
        predicate="KNOWS",
        object="Mokosz",
        confidence=0.9,
    )
    return CommittableRelation(relation, subject_entity_id=uuid4(), object_entity_id=uuid4())


class _StubReview:
    def __init__(
        self,
        *,
        committable: list[CommittableRelation] | Exception | None = None,
        decision: RelationDecisionResult | Exception | None = None,
    ) -> None:
        self._committable = committable
        self._decision = decision

    async def list_committable(self, story_id: UUID) -> list[CommittableRelation]:
        if isinstance(self._committable, Exception):
            raise self._committable
        return self._committable or []

    async def decide(self, relation_id: UUID, *, action: str) -> RelationDecisionResult:
        if isinstance(self._decision, Exception):
            raise self._decision
        assert self._decision is not None
        return self._decision


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


def _with_review(review: object) -> None:
    app.dependency_overrides[get_relation_review] = lambda: review


# --- GET /relations --------------------------------------------------------


async def test_list_relations_returns_committable(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    _with_review(_StubReview(committable=[_committable(story.id)]))
    resp = await client.get(f"/stories/{story.id}/relations")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["relations"]) == 1
    rel = body["relations"][0]
    assert rel["subject"] == "Janek" and rel["predicate"] == "KNOWS" and rel["object"] == "Mokosz"
    assert rel["subject_entity_id"] and rel["object_entity_id"]


async def test_list_relations_unknown_story_404(client: AsyncClient) -> None:
    _with_review(_StubReview(committable=[]))
    resp = await client.get(f"/stories/{uuid4()}/relations")
    assert resp.status_code == 404, resp.text


async def test_list_relations_store_down_503(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    _with_review(_StubReview(committable=OperationalError("connection refused")))
    resp = await client.get(f"/stories/{story.id}/relations")
    assert resp.status_code == 503, resp.text


# --- POST decide -----------------------------------------------------------


async def test_decide_commit_happy_path(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    edge_id = uuid4()
    _with_review(
        _StubReview(
            decision=RelationDecisionResult(uuid4(), "written", edge_id, already_decided=False)
        )
    )
    resp = await client.post(
        f"/stories/{story.id}/relations/{uuid4()}/decide", json={"action": "commit"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "written"
    assert body["edge_id"] == str(edge_id)


async def test_decide_unknown_story_404(client: AsyncClient) -> None:
    _with_review(
        _StubReview(
            decision=RelationDecisionResult(uuid4(), "written", uuid4(), already_decided=False)
        )
    )
    resp = await client.post(
        f"/stories/{uuid4()}/relations/{uuid4()}/decide", json={"action": "commit"}
    )
    assert resp.status_code == 404, resp.text


async def test_decide_unknown_relation_404(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    _with_review(_StubReview(decision=RelationNotFound("gone")))
    resp = await client.post(
        f"/stories/{story.id}/relations/{uuid4()}/decide", json={"action": "commit"}
    )
    assert resp.status_code == 404, resp.text


async def test_decide_unresolved_endpoint_409(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    _with_review(_StubReview(decision=RelationEndpointsUnresolved("held")))
    resp = await client.post(
        f"/stories/{story.id}/relations/{uuid4()}/decide", json={"action": "commit"}
    )
    assert resp.status_code == 409, resp.text


async def test_decide_store_down_503(client: AsyncClient, db_conn: psycopg.AsyncConnection) -> None:
    story = await _make_story(db_conn)
    _with_review(_StubReview(decision=OperationalError("connection refused")))
    resp = await client.post(
        f"/stories/{story.id}/relations/{uuid4()}/decide", json={"action": "commit"}
    )
    assert resp.status_code == 503, resp.text
