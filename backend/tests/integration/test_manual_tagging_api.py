"""Integration tests for the M4.S3c manual-correction routes — `POST .../paragraphs/{pid}/tags`,
`.../suppressions`, `.../boundaries` (spec §3.5).

Like `test_entity_edit_api`, these exercise the HTTP contract against the throwaway test DB (a real
story + paragraph, so the route resolves the §6.4 tenancy key *and* can validate a span against the
paragraph's text) with a **stub** `EntityEditService` injected via override — the service's real
behaviour is covered by `test_entity_edit`. Here we prove the route validates the span (→400),
guards request shape (Pydantic →422), maps domain exceptions to their declared status, and projects
the response shape.
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
    insert_paragraph,
    insert_project,
    insert_scene,
    insert_story,
)
from story_forge.agents.entity_edit import EntityNotFound, MentionNotFound
from story_forge.api.stories import get_entity_edit
from story_forge.domain.models import Chapter, Paragraph, Project, Scene, Story
from story_forge.main import app

pytestmark = pytest.mark.integration

PARAGRAPH_TEXT = "Janek met Maria."  # 16 chars — spans index into this


class _StubEdit:
    """A configurable `EntityEditService` double for the manual-correction routes."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self._raises = raises
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def tag_existing(
        self, project_id: UUID, paragraph_id: UUID, entity_id: UUID, span_start: int, span_end: int
    ) -> UUID:
        self.calls.append(("tag_existing", (project_id, paragraph_id, entity_id)))
        if self._raises is not None:
            raise self._raises
        return uuid4()

    async def tag_new_entity(
        self,
        project_id: UUID,
        paragraph_id: UUID,
        name: str,
        type_: str,
        language: str,
        span_start: int,
        span_end: int,
    ) -> tuple[UUID, UUID]:
        self.calls.append(("tag_new_entity", (project_id, paragraph_id, name, type_, language)))
        if self._raises is not None:
            raise self._raises
        return uuid4(), uuid4()

    async def suppress_occurrence(
        self,
        project_id: UUID,
        paragraph_id: UUID,
        span_start: int,
        span_end: int,
        entity_id: UUID | None,
    ) -> UUID:
        self.calls.append(("suppress_occurrence", (project_id, paragraph_id, entity_id)))
        if self._raises is not None:
            raise self._raises
        return uuid4()

    async def retag_occurrence(
        self,
        project_id: UUID,
        paragraph_id: UUID,
        span_start: int,
        span_end: int,
        from_entity_id: UUID,
        to_entity_id: UUID,
    ) -> tuple[UUID, UUID]:
        self.calls.append(("retag_occurrence", (project_id, from_entity_id, to_entity_id)))
        if self._raises is not None:
            raise self._raises
        return uuid4(), uuid4()

    async def change_boundaries(
        self,
        project_id: UUID,
        paragraph_id: UUID,
        entity_id: UUID,
        mention_id: UUID | None,
        old_start: int,
        old_end: int,
        new_start: int,
        new_end: int,
    ) -> UUID:
        self.calls.append(("change_boundaries", (project_id, entity_id, mention_id)))
        if self._raises is not None:
            raise self._raises
        return mention_id or uuid4()


async def _make_story_paragraph(conn: psycopg.AsyncConnection) -> tuple[Story, Paragraph]:
    project = Project(name="t", language="pl")
    story = Story(project_id=project.id, title="t", raw_text="x")
    chapter = Chapter(story_id=story.id, order_index=0)
    scene = Scene(chapter_id=chapter.id, order_index=0)
    paragraph = Paragraph(scene_id=scene.id, order_index=0, content=PARAGRAPH_TEXT)
    await insert_project(conn, project)
    await insert_story(conn, story)
    await insert_chapter(conn, chapter)
    await insert_scene(conn, scene)
    await insert_paragraph(conn, paragraph)
    return story, paragraph


@pytest_asyncio.fixture
async def make_client(db_conn: psycopg.AsyncConnection) -> AsyncIterator[object]:
    async def _override() -> AsyncIterator[psycopg.AsyncConnection]:
        yield db_conn

    app.dependency_overrides[get_connection] = _override
    clients: list[AsyncClient] = []

    def _factory(service: object) -> AsyncClient:
        app.dependency_overrides[get_entity_edit] = lambda: service
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clients.append(client)
        return client

    yield _factory
    for client in clients:
        await client.aclose()
    app.dependency_overrides.clear()


# --- tag ---------------------------------------------------------------------


async def test_tag_existing_entity_returns_ids(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, para = await _make_story_paragraph(db_conn)
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    entity_id = uuid4()

    resp = await client.post(
        f"/stories/{story.id}/paragraphs/{para.id}/tags",
        json={"span_start": 0, "span_end": 5, "entity_id": str(entity_id)},
    )

    assert resp.status_code == 200, resp.text
    assert service.calls[0] == ("tag_existing", (story.project_id, para.id, entity_id))
    body = resp.json()
    assert body["entity_id"] == str(entity_id) and UUID(body["mention_id"])


async def test_tag_new_entity_returns_ids(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, para = await _make_story_paragraph(db_conn)
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(
        f"/stories/{story.id}/paragraphs/{para.id}/tags",
        json={"span_start": 0, "span_end": 5, "new_entity": {"name": "Janek", "type": "Character"}},
    )

    assert resp.status_code == 200, resp.text
    assert service.calls[0][0] == "tag_new_entity"
    body = resp.json()
    assert UUID(body["entity_id"]) and UUID(body["mention_id"])


async def test_tag_both_targets_is_422(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, para = await _make_story_paragraph(db_conn)
    client: AsyncClient = make_client(_StubEdit())  # type: ignore[operator]
    resp = await client.post(
        f"/stories/{story.id}/paragraphs/{para.id}/tags",
        json={
            "span_start": 0,
            "span_end": 5,
            "entity_id": str(uuid4()),
            "new_entity": {"name": "x", "type": "y"},
        },
    )
    assert resp.status_code == 422, resp.text


async def test_tag_neither_target_is_422(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, para = await _make_story_paragraph(db_conn)
    client: AsyncClient = make_client(_StubEdit())  # type: ignore[operator]
    resp = await client.post(
        f"/stories/{story.id}/paragraphs/{para.id}/tags",
        json={"span_start": 0, "span_end": 5},
    )
    assert resp.status_code == 422, resp.text


async def test_tag_out_of_bounds_span_is_400(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # The route validates the span against the paragraph text before calling the service.
    story, para = await _make_story_paragraph(db_conn)
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    resp = await client.post(
        f"/stories/{story.id}/paragraphs/{para.id}/tags",
        json={"span_start": 0, "span_end": 999, "entity_id": str(uuid4())},
    )
    assert resp.status_code == 400, resp.text
    assert service.calls == []  # rejected before the service


async def test_tag_zero_length_span_is_400(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, para = await _make_story_paragraph(db_conn)
    client: AsyncClient = make_client(_StubEdit())  # type: ignore[operator]
    resp = await client.post(
        f"/stories/{story.id}/paragraphs/{para.id}/tags",
        json={"span_start": 5, "span_end": 5, "entity_id": str(uuid4())},
    )
    assert resp.status_code == 400, resp.text


async def test_tag_unknown_entity_is_404(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, para = await _make_story_paragraph(db_conn)
    service = _StubEdit(raises=EntityNotFound("nope"))
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    resp = await client.post(
        f"/stories/{story.id}/paragraphs/{para.id}/tags",
        json={"span_start": 0, "span_end": 5, "entity_id": str(uuid4())},
    )
    assert resp.status_code == 404, resp.text


async def test_tag_paragraph_not_in_story_is_404(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, _para = await _make_story_paragraph(db_conn)
    client: AsyncClient = make_client(_StubEdit())  # type: ignore[operator]
    resp = await client.post(
        f"/stories/{story.id}/paragraphs/{uuid4()}/tags",
        json={"span_start": 0, "span_end": 5, "entity_id": str(uuid4())},
    )
    assert resp.status_code == 404, resp.text


async def test_tag_unknown_story_is_404(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    client: AsyncClient = make_client(_StubEdit())  # type: ignore[operator]
    resp = await client.post(
        f"/stories/{uuid4()}/paragraphs/{uuid4()}/tags",
        json={"span_start": 0, "span_end": 5, "entity_id": str(uuid4())},
    )
    assert resp.status_code == 404, resp.text


# --- suppress / re-assign ----------------------------------------------------


async def test_suppress_not_an_entity_returns_suppression_only(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, para = await _make_story_paragraph(db_conn)
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    resp = await client.post(
        f"/stories/{story.id}/paragraphs/{para.id}/suppressions",
        json={"span_start": 0, "span_end": 5},  # entity_id None = "not an entity"
    )
    assert resp.status_code == 200, resp.text
    assert service.calls[0] == ("suppress_occurrence", (story.project_id, para.id, None))
    body = resp.json()
    assert UUID(body["suppression_id"]) and body["mention_id"] is None


async def test_suppress_atomic_retag_returns_both_ids(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, para = await _make_story_paragraph(db_conn)
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    from_id, to_id = uuid4(), uuid4()
    resp = await client.post(
        f"/stories/{story.id}/paragraphs/{para.id}/suppressions",
        json={"span_start": 0, "span_end": 5, "entity_id": str(from_id), "retag_to": str(to_id)},
    )
    assert resp.status_code == 200, resp.text
    assert service.calls[0] == ("retag_occurrence", (story.project_id, from_id, to_id))
    body = resp.json()
    assert UUID(body["suppression_id"]) and UUID(body["mention_id"])


async def test_suppress_retag_without_from_entity_is_422(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, para = await _make_story_paragraph(db_conn)
    client: AsyncClient = make_client(_StubEdit())  # type: ignore[operator]
    resp = await client.post(
        f"/stories/{story.id}/paragraphs/{para.id}/suppressions",
        json={"span_start": 0, "span_end": 5, "retag_to": str(uuid4())},  # no entity_id
    )
    assert resp.status_code == 422, resp.text


# --- change boundaries -------------------------------------------------------


async def test_boundaries_materialize_returns_mention_id(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, para = await _make_story_paragraph(db_conn)
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    entity_id = uuid4()
    resp = await client.post(
        f"/stories/{story.id}/paragraphs/{para.id}/boundaries",
        json={
            "entity_id": str(entity_id),
            "mention_id": None,
            "old_start": 0,
            "old_end": 5,
            "new_start": 0,
            "new_end": 9,
        },
    )
    assert resp.status_code == 200, resp.text
    assert service.calls[0] == ("change_boundaries", (story.project_id, entity_id, None))
    assert UUID(resp.json()["mention_id"])


async def test_boundaries_invalid_new_span_is_400(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, para = await _make_story_paragraph(db_conn)
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    resp = await client.post(
        f"/stories/{story.id}/paragraphs/{para.id}/boundaries",
        json={
            "entity_id": str(uuid4()),
            "old_start": 0,
            "old_end": 5,
            "new_start": 0,
            "new_end": 999,
        },
    )
    assert resp.status_code == 400, resp.text
    assert service.calls == []


async def test_boundaries_missing_mention_is_404(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, para = await _make_story_paragraph(db_conn)
    service = _StubEdit(raises=MentionNotFound("gone"))
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    resp = await client.post(
        f"/stories/{story.id}/paragraphs/{para.id}/boundaries",
        json={
            "entity_id": str(uuid4()),
            "mention_id": str(uuid4()),
            "old_start": 0,
            "old_end": 5,
            "new_start": 0,
            "new_end": 9,
        },
    )
    assert resp.status_code == 404, resp.text
