"""HTTP-contract tests for the name-normalisation routes (graph-quality S6a).

Assert the route mapping for GET (list synonyms) / POST (dismiss) / DELETE (un-dismiss): the
happy paths across both vocabularies, the counts/score projection, per-surface dismissal, and
every declared non-2xx — 404 (story) and 503 (store outage). The self-join is unit-tested in
`test_label_synonyms.py`; here the reader is stubbed (so no ~2 GB embedding model loads). Two
tests drive the **real** dismissal store through the HTTP layer (POST → GET suppresses) so the
suppression id-contract is exercised producer→consumer, including surface-scoping.
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
from story_forge.adapters.postgres_label_dismissal_store import PostgresLabelDismissalStore
from story_forge.adapters.postgres_repo import insert_project, insert_story
from story_forge.api.stories import get_label_dismissal_store, get_label_vocabulary_reader
from story_forge.config import settings
from story_forge.domain.label_synonyms import LabelVocabularyEntry
from story_forge.domain.models import Project, Story
from story_forge.main import app

pytestmark = pytest.mark.integration

_Vocab = tuple[list[LabelVocabularyEntry], list[LabelVocabularyEntry]]


class _StubReader:
    def __init__(self, vocab: _Vocab | Exception) -> None:
        self._vocab = vocab

    async def load_vocabulary(self, project_id: UUID) -> _Vocab:
        if isinstance(self._vocab, Exception):
            raise self._vocab
        return self._vocab


class _StubDismissStore:
    """Empty by default; `insert`/`delete` optionally raise to exercise the 503 path."""

    def __init__(self, *, insert_error: Exception | None = None) -> None:
        self._insert_error = insert_error

    async def list_pair_ids(self, project_id: UUID) -> set[UUID]:
        return set()

    async def insert(self, project_id: UUID, surface: str, a: str, b: str) -> None:
        if self._insert_error is not None:
            raise self._insert_error

    async def delete(self, project_id: UUID, surface: str, a: str, b: str) -> None:
        if self._insert_error is not None:
            raise self._insert_error


async def _make_story(conn: psycopg.AsyncConnection) -> Story:
    project = Project(name="t", language="pl")
    story = Story(project_id=project.id, title="t", raw_text="x")
    await insert_project(conn, project)
    await insert_story(conn, story)
    return story


def _vocab() -> _Vocab:
    """A predicate pair (PASSENGER_ON/passenger_on) and a type pair (PERSON/Person), name-only."""
    predicates = [
        LabelVocabularyEntry(label="PASSENGER_ON", count=5, embedding=None),
        LabelVocabularyEntry(label="passenger_on", count=2, embedding=None),
    ]
    types = [
        LabelVocabularyEntry(label="PERSON", count=9, embedding=None),
        LabelVocabularyEntry(label="Person", count=1, embedding=None),
    ]
    return predicates, types


def _real_store() -> PostgresLabelDismissalStore:
    return PostgresLabelDismissalStore(libpq_kwargs(settings.test_database_url))


@pytest_asyncio.fixture
async def client(db_conn: psycopg.AsyncConnection) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator[psycopg.AsyncConnection]:
        yield db_conn

    app.dependency_overrides[get_connection] = _override
    app.dependency_overrides[get_label_dismissal_store] = lambda: _StubDismissStore()
    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        yield ac
    finally:
        await ac.aclose()
        app.dependency_overrides.clear()


def _with_reader(reader: object) -> None:
    app.dependency_overrides[get_label_vocabulary_reader] = lambda: reader


def _with_store(store: object) -> None:
    app.dependency_overrides[get_label_dismissal_store] = lambda: store


# --- GET /label-vocabulary --------------------------------------------------


async def test_list_returns_both_surfaces_with_counts_and_scores(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    _with_reader(_StubReader(_vocab()))

    resp = await client.get(f"/stories/{story.id}/label-vocabulary")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["predicate_suggestions"]) == 1
    assert len(body["type_suggestions"]) == 1
    pred = body["predicate_suggestions"][0]
    assert {pred["label_lo"], pred["label_hi"]} == {"PASSENGER_ON", "passenger_on"}
    assert pred["name_score"] == 100.0  # normalised fuzzy folds case/underscore
    assert pred["cosine_score"] is None
    # Counts follow canonical label order (label_lo == "PASSENGER_ON", the upper-cased form).
    assert pred["label_lo"] == "PASSENGER_ON" and pred["count_lo"] == 5
    assert pred["label_hi"] == "passenger_on" and pred["count_hi"] == 2


async def test_list_unknown_story_404(client: AsyncClient) -> None:
    _with_reader(_StubReader(([], [])))
    resp = await client.get(f"/stories/{uuid4()}/label-vocabulary")
    assert resp.status_code == 404, resp.text


async def test_list_store_outage_503(client: AsyncClient, db_conn: psycopg.AsyncConnection) -> None:
    story = await _make_story(db_conn)
    _with_reader(_StubReader(ServiceUnavailable("neo4j down")))
    resp = await client.get(f"/stories/{story.id}/label-vocabulary")
    assert resp.status_code == 503, resp.text


async def test_dismissed_pair_is_suppressed_via_real_store(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    # Producer→consumer: dismiss through the POST route (real store), then the GET must drop that
    # pair — the suppression id computed by the read must match the one the write stored.
    story = await _make_story(db_conn)
    _with_reader(_StubReader(_vocab()))
    _with_store(_real_store())

    before = await client.get(f"/stories/{story.id}/label-vocabulary")
    assert len(before.json()["type_suggestions"]) == 1

    dismiss = await client.post(
        f"/stories/{story.id}/label-vocabulary/dismiss",
        json={"surface": "type", "label_a": "PERSON", "label_b": "Person"},
    )
    assert dismiss.status_code == 204, dismiss.text

    after = await client.get(f"/stories/{story.id}/label-vocabulary")
    assert after.json()["type_suggestions"] == []
    # The predicate pair is untouched — dismissal is per-surface.
    assert len(after.json()["predicate_suggestions"]) == 1


async def test_dismissal_is_surface_scoped_via_real_store(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    # An identically-spelled pair on the *other* surface must not be suppressed by this dismissal.
    story = await _make_story(db_conn)
    same_spelling = (
        [
            LabelVocabularyEntry(label="OWNS", count=3, embedding=None),
            LabelVocabularyEntry(label="owns", count=1, embedding=None),
        ],
        [
            LabelVocabularyEntry(label="OWNS", count=2, embedding=None),
            LabelVocabularyEntry(label="owns", count=1, embedding=None),
        ],
    )
    _with_reader(_StubReader(same_spelling))
    _with_store(_real_store())

    await client.post(
        f"/stories/{story.id}/label-vocabulary/dismiss",
        json={"surface": "type", "label_a": "OWNS", "label_b": "owns"},
    )
    after = await client.get(f"/stories/{story.id}/label-vocabulary")
    assert after.json()["type_suggestions"] == []  # the dismissed surface
    assert len(after.json()["predicate_suggestions"]) == 1  # the other surface survives


async def test_undismiss_restores_via_real_store(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    _with_reader(_StubReader(_vocab()))
    _with_store(_real_store())
    body = {"surface": "type", "label_a": "PERSON", "label_b": "Person"}

    await client.post(f"/stories/{story.id}/label-vocabulary/dismiss", json=body)
    undismiss = await client.request(
        "DELETE", f"/stories/{story.id}/label-vocabulary/dismiss", json=body
    )
    assert undismiss.status_code == 204, undismiss.text

    restored = await client.get(f"/stories/{story.id}/label-vocabulary")
    assert len(restored.json()["type_suggestions"]) == 1


# --- POST / DELETE dismiss error mapping -----------------------------------


async def test_dismiss_unknown_story_404(client: AsyncClient) -> None:
    resp = await client.post(
        f"/stories/{uuid4()}/label-vocabulary/dismiss",
        json={"surface": "type", "label_a": "A", "label_b": "B"},
    )
    assert resp.status_code == 404, resp.text


async def test_dismiss_invalid_surface_422(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    resp = await client.post(
        f"/stories/{story.id}/label-vocabulary/dismiss",
        json={"surface": "banana", "label_a": "A", "label_b": "B"},
    )
    assert resp.status_code == 422, resp.text


async def test_dismiss_store_down_503(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    _with_store(_StubDismissStore(insert_error=OperationalError("connection refused")))
    resp = await client.post(
        f"/stories/{story.id}/label-vocabulary/dismiss",
        json={"surface": "type", "label_a": "A", "label_b": "B"},
    )
    assert resp.status_code == 503, resp.text


async def test_undismiss_unknown_story_404(client: AsyncClient) -> None:
    resp = await client.request(
        "DELETE",
        f"/stories/{uuid4()}/label-vocabulary/dismiss",
        json={"surface": "type", "label_a": "A", "label_b": "B"},
    )
    assert resp.status_code == 404, resp.text
