"""Integration tests for `POST /stories/{id}/structure` (spec §7, step 2).

Exercise the whole route against the throwaway test DB: build an outline from the
story's stored raw text in each mode and persist chapters/scenes/paragraphs. The
`get_connection` dependency shares the test transaction (writes visible, rolled
back), and `get_chunking_coordinator` is overridden with a coordinator wrapping a
*stub* agent — manual mode never calls it, hybrid mode does, no network either way.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import psycopg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from story_forge.adapters.db import get_connection
from story_forge.adapters.postgres_repo import (
    get_story,
    insert_project,
    insert_story,
    list_chapters,
    list_paragraphs,
    list_scenes,
)
from story_forge.agents.chunking_agent import (
    ChapterProposal,
    ChunkingProposal,
    SceneProposal,
)
from story_forge.agents.chunking_coordinator import ChunkingCoordinator
from story_forge.api.stories import get_chunking_coordinator
from story_forge.domain.models import Project, Story
from story_forge.main import app

pytestmark = pytest.mark.integration


class _StubAgent:
    """Returns one canned proposal; records that it was called."""

    def __init__(self, proposal: ChunkingProposal | None = None) -> None:
        self._proposal = proposal
        self.calls = 0

    async def propose_outline(
        self, *, raw_text: str, language: str, word_count: int | None = None
    ) -> ChunkingProposal:
        self.calls += 1
        assert self._proposal is not None
        return self._proposal


async def _make_story(conn: psycopg.AsyncConnection, raw_text: str) -> Story:
    project = Project(name="t", language="en")
    story = Story(project_id=project.id, title="t", raw_text=raw_text)
    await insert_project(conn, project)
    await insert_story(conn, story)
    return story


@pytest_asyncio.fixture
async def make_client(
    db_conn: psycopg.AsyncConnection,
) -> AsyncIterator[object]:
    """Yields a factory: given a coordinator, returns a client sharing the test txn."""

    async def _override() -> AsyncIterator[psycopg.AsyncConnection]:
        yield db_conn

    app.dependency_overrides[get_connection] = _override
    clients: list[AsyncClient] = []

    def _factory(coordinator: ChunkingCoordinator) -> AsyncClient:
        app.dependency_overrides[get_chunking_coordinator] = lambda: coordinator
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clients.append(client)
        return client

    yield _factory
    for client in clients:
        await client.aclose()
    app.dependency_overrides.clear()


async def test_manual_mode_persists_the_tree(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    raw = (
        "## The Crossing\n"
        "### Dawn\nThey reached the river.\n\nThe water was high.\n"
        "### Dusk\nNightfall.\n"
    )
    story = await _make_story(db_conn, raw)
    coordinator = ChunkingCoordinator(_StubAgent())
    client: AsyncClient = make_client(coordinator)  # type: ignore[operator]

    resp = await client.post(f"/stories/{story.id}/structure", params={"mode": "manual"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert (body["chapter_count"], body["scene_count"], body["paragraph_count"]) == (1, 2, 3)

    chapters = await list_chapters(db_conn, story.id)
    assert [c.title for c in chapters] == ["The Crossing"]
    scenes = await list_scenes(db_conn, chapters[0].id)
    assert [s.title for s in scenes] == ["Dawn", "Dusk"]
    dawn_paragraphs = await list_paragraphs(db_conn, scenes[0].id)
    assert [p.content for p in dawn_paragraphs] == [
        "They reached the river.",
        "The water was high.",
    ]
    assert [p.order_index for p in dawn_paragraphs] == [0, 1]


async def test_hybrid_mode_fills_untitled_scene_and_persists(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # Chapter marked, scenes not → the stub agent sub-divides the untitled scene.
    raw = "## The Crossing\nFirst.\n\nSecond.\n\nThird.\n"
    story = await _make_story(db_conn, raw)
    proposal = ChunkingProposal(
        chapters=[
            ChapterProposal(
                title="c",
                summary="c",
                scenes=[
                    SceneProposal(title="Arrival", summary="s", paragraph_range=(0, 0)),
                    SceneProposal(title="After", summary="s", paragraph_range=(1, 2)),
                ],
            )
        ]
    )
    agent = _StubAgent(proposal)
    coordinator = ChunkingCoordinator(agent)
    client: AsyncClient = make_client(coordinator)  # type: ignore[operator]

    resp = await client.post(f"/stories/{story.id}/structure", params={"mode": "hybrid"})
    assert resp.status_code == 201, resp.text
    assert agent.calls == 1
    chapters = await list_chapters(db_conn, story.id)
    scenes = await list_scenes(db_conn, chapters[0].id)
    assert [s.title for s in scenes] == ["Arrival", "After"]


async def test_unknown_story_is_404(make_client: object) -> None:
    coordinator = ChunkingCoordinator(_StubAgent())
    client: AsyncClient = make_client(coordinator)  # type: ignore[operator]
    missing = UUID("00000000-0000-0000-0000-000000000000")
    resp = await client.post(f"/stories/{missing}/structure", params={"mode": "manual"})
    assert resp.status_code == 404


async def test_restructuring_an_already_structured_story_is_409(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn, "## One\n### A\nBody.\n")
    coordinator = ChunkingCoordinator(_StubAgent())
    client: AsyncClient = make_client(coordinator)  # type: ignore[operator]

    first = await client.post(f"/stories/{story.id}/structure", params={"mode": "manual"})
    assert first.status_code == 201, first.text
    second = await client.post(f"/stories/{story.id}/structure", params={"mode": "manual"})
    assert second.status_code == 409


async def test_invalid_mode_is_422(make_client: object, db_conn: psycopg.AsyncConnection) -> None:
    story = await _make_story(db_conn, "## One\n### A\nBody.\n")
    coordinator = ChunkingCoordinator(_StubAgent())
    client: AsyncClient = make_client(coordinator)  # type: ignore[operator]
    resp = await client.post(f"/stories/{story.id}/structure", params={"mode": "sideways"})
    assert resp.status_code == 422


async def test_manual_mode_with_raw_text_override_uses_and_persists_edit(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # Spec §7 step 2: "UI shows proposed outline, user accepts/edits". The
    # frontend manual editor edits the source markers and POSTs the result in
    # the request body; the route must use that text (not the originally-stored
    # one) AND update story.raw_text so a later re-read sees the edits — without
    # a separate PATCH endpoint. This pins both halves.
    original = "## Orig\n### A\nFoo.\n"
    story = await _make_story(db_conn, original)
    coordinator = ChunkingCoordinator(_StubAgent())
    client: AsyncClient = make_client(coordinator)  # type: ignore[operator]

    edited = "## New\n### B\nBar.\n\nBaz.\n"
    resp = await client.post(
        f"/stories/{story.id}/structure",
        params={"mode": "manual"},
        json={"raw_text": edited},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # Counts reflect the edited text, not the original (which had 1 paragraph,
    # the edited has 2).
    assert (body["chapter_count"], body["scene_count"], body["paragraph_count"]) == (1, 1, 2)

    chapters = await list_chapters(db_conn, story.id)
    assert [c.title for c in chapters] == ["New"]

    # And the stored raw_text is now the edited copy — re-reads see the user's
    # changes.
    updated = await get_story(db_conn, story.id)
    assert updated is not None
    assert updated.raw_text == edited
