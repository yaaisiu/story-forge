"""HTTP-contract tests for the duplicate-suggestion routes (graph-quality S4a).

Assert the route mapping for GET (list) / POST (dismiss) / DELETE (un-dismiss): the happy paths,
the enrichment, and every declared non-2xx — 404 (story) and 503 (store outage). The self-join
itself is unit-tested in `test_duplicate_clusters.py`; here the reader is stubbed. One test drives
the **real** dismissal store through the HTTP layer (POST → GET suppresses) so the suppression
id-contract is exercised producer→consumer, not against a hand-built id.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from neo4j.exceptions import ServiceUnavailable
from psycopg import OperationalError

from story_forge.adapters.db import get_connection, libpq_kwargs
from story_forge.adapters.postgres_duplicate_dismissal_store import (
    PostgresDuplicateDismissalStore,
)
from story_forge.adapters.postgres_repo import insert_project, insert_story
from story_forge.api.stories import get_accepted_reader, get_duplicate_dismissal_store
from story_forge.config import settings
from story_forge.domain.candidates import AcceptedSnapshot
from story_forge.domain.graph import GraphEntity
from story_forge.domain.models import Project, Story
from story_forge.main import app

pytestmark = pytest.mark.integration


class _StubReader:
    def __init__(self, snapshot: AcceptedSnapshot | Exception) -> None:
        self._snapshot = snapshot

    async def load_accepted(self, project_id: UUID) -> AcceptedSnapshot:
        if isinstance(self._snapshot, Exception):
            raise self._snapshot
        return self._snapshot


class _StubDismissStore:
    """Empty by default; `insert`/`delete` optionally raise to exercise the 503 path."""

    def __init__(self, *, insert_error: Exception | None = None) -> None:
        self._insert_error = insert_error

    async def list_pair_ids(self, project_id: UUID) -> set[UUID]:
        return set()

    async def insert(self, project_id: UUID, a: UUID, b: UUID) -> None:
        if self._insert_error is not None:
            raise self._insert_error

    async def delete(self, project_id: UUID, a: UUID, b: UUID) -> None:
        if self._insert_error is not None:
            raise self._insert_error


async def _make_story(conn: psycopg.AsyncConnection) -> Story:
    project = Project(name="t", language="pl")
    story = Story(project_id=project.id, title="t", raw_text="x")
    await insert_project(conn, project)
    await insert_story(conn, story)
    return story


def _pair_snapshot(project_id: UUID) -> tuple[AcceptedSnapshot, UUID, UUID]:
    """A snapshot of two same-named entities (a suggested pair), enriched with a quote."""
    a = GraphEntity(id=uuid4(), type="Character", canonical_name_pl="Bronek", project_id=project_id)
    b = GraphEntity(
        id=uuid4(),
        type="Character",
        canonical_name_pl="Bronek",
        aliases=["Bronio"],
        project_id=project_id,
    )
    snapshot = AcceptedSnapshot(
        entities=[a, b],
        recent_mentions={a.id: ["Bronek left."], b.id: ["Bronek returned."]},
    )
    return snapshot, a.id, b.id


def _real_store() -> PostgresDuplicateDismissalStore:
    return PostgresDuplicateDismissalStore(libpq_kwargs(settings.test_database_url))


@pytest_asyncio.fixture
async def client(db_conn: psycopg.AsyncConnection) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator[psycopg.AsyncConnection]:
        yield db_conn

    app.dependency_overrides[get_connection] = _override
    app.dependency_overrides[get_duplicate_dismissal_store] = lambda: _StubDismissStore()
    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        yield ac
    finally:
        await ac.aclose()
        app.dependency_overrides.clear()


def _with_reader(reader: object) -> None:
    app.dependency_overrides[get_accepted_reader] = lambda: reader


def _with_store(store: object) -> None:
    app.dependency_overrides[get_duplicate_dismissal_store] = lambda: store


# --- GET /duplicate-suggestions --------------------------------------------


async def test_list_returns_ranked_enriched_suggestions(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    snapshot, id_a, id_b = _pair_snapshot(story.project_id)
    _with_reader(_StubReader(snapshot))

    resp = await client.get(f"/stories/{story.id}/duplicate-suggestions")

    assert resp.status_code == 200, resp.text
    suggestions = resp.json()["suggestions"]
    assert len(suggestions) == 1
    s = suggestions[0]
    assert {s["entity_a"]["entity_id"], s["entity_b"]["entity_id"]} == {str(id_a), str(id_b)}
    assert s["name_score"] == 100.0
    assert s["cosine_score"] is None  # no mention vectors → name-only
    # S3/DM-EE-3 enrichment: type + aliases + a sample quote surface for verification.
    views = {v["entity_id"]: v for v in (s["entity_a"], s["entity_b"])}
    assert views[str(id_b)]["type"] == "Character"
    assert views[str(id_b)]["aliases"] == ["Bronio"]
    assert views[str(id_b)]["context_quote"] == "Bronek returned."


async def test_list_unknown_story_404(client: AsyncClient) -> None:
    _with_reader(_StubReader(AcceptedSnapshot()))
    resp = await client.get(f"/stories/{uuid4()}/duplicate-suggestions")
    assert resp.status_code == 404, resp.text


async def test_list_store_outage_503(client: AsyncClient, db_conn: psycopg.AsyncConnection) -> None:
    story = await _make_story(db_conn)
    _with_reader(_StubReader(ServiceUnavailable("neo4j down")))
    resp = await client.get(f"/stories/{story.id}/duplicate-suggestions")
    assert resp.status_code == 503, resp.text


async def test_dismissed_pair_is_suppressed_via_real_store(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    # Producer→consumer: dismiss through the POST route (real store), then the GET must drop
    # that pair — the suppression id computed by the read must match the one the write stored.
    story = await _make_story(db_conn)
    snapshot, id_a, id_b = _pair_snapshot(story.project_id)
    _with_reader(_StubReader(snapshot))
    _with_store(_real_store())

    before = await client.get(f"/stories/{story.id}/duplicate-suggestions")
    assert len(before.json()["suggestions"]) == 1

    dismiss = await client.post(
        f"/stories/{story.id}/duplicate-suggestions/dismiss",
        json={"entity_id_a": str(id_a), "entity_id_b": str(id_b)},
    )
    assert dismiss.status_code == 204, dismiss.text

    after = await client.get(f"/stories/{story.id}/duplicate-suggestions")
    assert after.json()["suggestions"] == []


async def test_undismiss_restores_via_real_store(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    snapshot, id_a, id_b = _pair_snapshot(story.project_id)
    _with_reader(_StubReader(snapshot))
    _with_store(_real_store())
    body = {"entity_id_a": str(id_a), "entity_id_b": str(id_b)}

    await client.post(f"/stories/{story.id}/duplicate-suggestions/dismiss", json=body)
    undismiss = await client.request(
        "DELETE", f"/stories/{story.id}/duplicate-suggestions/dismiss", json=body
    )
    assert undismiss.status_code == 204, undismiss.text

    restored = await client.get(f"/stories/{story.id}/duplicate-suggestions")
    assert len(restored.json()["suggestions"]) == 1


# --- POST / DELETE dismiss error mapping -----------------------------------


async def test_dismiss_unknown_story_404(client: AsyncClient) -> None:
    resp = await client.post(
        f"/stories/{uuid4()}/duplicate-suggestions/dismiss",
        json={"entity_id_a": str(uuid4()), "entity_id_b": str(uuid4())},
    )
    assert resp.status_code == 404, resp.text


async def test_dismiss_store_down_503(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    _with_store(_StubDismissStore(insert_error=OperationalError("connection refused")))
    resp = await client.post(
        f"/stories/{story.id}/duplicate-suggestions/dismiss",
        json={"entity_id_a": str(uuid4()), "entity_id_b": str(uuid4())},
    )
    assert resp.status_code == 503, resp.text


async def test_undismiss_unknown_story_404(client: AsyncClient) -> None:
    resp = await client.request(
        "DELETE",
        f"/stories/{uuid4()}/duplicate-suggestions/dismiss",
        json={"entity_id_a": str(uuid4()), "entity_id_b": str(uuid4())},
    )
    assert resp.status_code == 404, resp.text
