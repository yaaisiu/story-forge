"""Integration tests for `GET /stories/{id}/reader` (spec §3.5 inline highlights, M4.S1).

Exercise the read-only reader projection against the throwaway test DB with a *stub* Neo4j
repo (entities are project-scoped, the §3.4 seam). The route's job: load the story's
paragraphs (Postgres) + their entity mentions, cross-join each mention to its accepted Neo4j
entity in app code, resolve where each entity's surface forms (canonical + aliases) sit in the
paragraph (`resolve_highlights`, unit-tested separately), and return per-paragraph decorated
ranges + a tooltip catalog of the entities that actually appeared. Fail-closed: an entity whose
forms don't occur is omitted, not guessed.
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
    insert_mention_suppression,
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
    MentionSuppression,
    Paragraph,
    Project,
    Scene,
    Story,
)
from story_forge.main import app

pytestmark = pytest.mark.integration


class _StubRepo:
    """Returns canned project entities + relations, recording the project_id it was asked for."""

    def __init__(
        self, entities: list[GraphEntity], relations: list[GraphRelation] | None = None
    ) -> None:
        self._entities = entities
        self._relations = relations or []
        self.asked_project: UUID | None = None
        self.asked_relations_project: UUID | None = None

    async def list_entities(self, project_id: UUID) -> list[GraphEntity]:
        self.asked_project = project_id
        return self._entities

    async def get_relations(self, project_id: UUID) -> list[GraphRelation]:
        """Feeds the §3.5 graph-derived tooltip summary (S7).

        Records the scope it was asked for: passing `story_id` here instead of the project id
        would silently empty every tooltip summary in production (Neo4j matches no project) while
        leaving the suite green, so a test pins it.
        """
        self.asked_relations_project = project_id
        return self._relations


async def _make_paragraphs(
    conn: psycopg.AsyncConnection, *contents: str
) -> tuple[Story, list[Paragraph]]:
    """Insert a single-chapter, single-scene story whose scene holds `contents` in order."""
    project = Project(name="t", language="pl")
    story = Story(project_id=project.id, title="t", raw_text="x")
    chapter = Chapter(story_id=story.id, order_index=0)
    scene = Scene(chapter_id=chapter.id, order_index=0)
    await insert_project(conn, project)
    await insert_story(conn, story)
    await insert_chapter(conn, chapter)
    await insert_scene(conn, scene)
    paragraphs = [
        Paragraph(scene_id=scene.id, order_index=i, content=content)
        for i, content in enumerate(contents)
    ]
    for paragraph in paragraphs:
        await insert_paragraph(conn, paragraph)
    return story, paragraphs


async def _mention(
    conn: psycopg.AsyncConnection, paragraph: Paragraph, entity: GraphEntity
) -> None:
    await insert_entity_mention(conn, EntityMention(paragraph_id=paragraph.id, entity_id=entity.id))


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


async def test_reader_highlights_mentioned_entities(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, (para,) = await _make_paragraphs(db_conn, "Janek met Maria.")
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=story.project_id)
    maria = GraphEntity(
        type="Character",
        canonical_name_pl="Maria",
        aliases=["Marysia"],
        project_id=story.project_id,
    )
    await _mention(db_conn, para, janek)
    await _mention(db_conn, para, maria)
    client: AsyncClient = make_client(_StubRepo([janek, maria]))  # type: ignore[operator]

    resp = await client.get(f"/stories/{story.id}/reader")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [p["id"] for p in body["paragraphs"]] == [str(para.id)]
    paragraph = body["paragraphs"][0]
    assert paragraph["text"] == "Janek met Maria."
    # Each highlight now carries source + occurrence identity (M4.S3c, DM-S3c-6): an auto search
    # hit is source="search" with no mention_id.
    assert paragraph["highlights"] == [
        {
            "start": 0,
            "end": 5,
            "entity_id": str(janek.id),
            "type": "Character",
            "source": "search",
            "mention_id": None,
        },
        {
            "start": 10,
            "end": 15,
            "entity_id": str(maria.id),
            "type": "Character",
            "source": "search",
            "mention_id": None,
        },
    ]
    # The tooltip catalog carries only entities that actually appeared, with display name + aliases.
    catalog = {e["entity_id"]: e for e in body["entities"]}
    assert set(catalog) == {str(janek.id), str(maria.id)}
    assert catalog[str(maria.id)] == {
        "entity_id": str(maria.id),
        "canonical_name": "Maria",
        "type": "Character",
        "aliases": ["Marysia"],
        # No relations in this story's graph → an empty §3.5 summary, never a stray "+0 more".
        "relations": [],
        "relation_overflow": 0,
    }


async def test_reader_inflected_mention_matched_via_alias(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # The cross-store join feeds aliases into the resolver, so the inflected surface form
    # "Jankowi" (stored as an alias by a prior merge-accept) is highlighted.
    story, (para,) = await _make_paragraphs(db_conn, "Dał Jankowi książkę.")
    janek = GraphEntity(
        type="Character",
        canonical_name_pl="Janek",
        aliases=["Jankowi"],
        project_id=story.project_id,
    )
    await _mention(db_conn, para, janek)
    client: AsyncClient = make_client(_StubRepo([janek]))  # type: ignore[operator]

    resp = await client.get(f"/stories/{story.id}/reader")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["paragraphs"][0]["highlights"] == [
        {
            "start": 4,
            "end": 11,
            "entity_id": str(janek.id),
            "type": "Character",
            "source": "search",
            "mention_id": None,
        },
    ]


async def test_reader_omits_unresolvable_and_unmentioned(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # para0: a mention whose entity's name does not occur in the text → omitted (fail-closed).
    # para1: no mentions at all → plain text, no highlights.
    story, (para0, para1) = await _make_paragraphs(db_conn, "A quiet room.", "Nothing here either.")
    ghost = GraphEntity(type="Character", canonical_name_pl="Zbyszek", project_id=story.project_id)
    await _mention(db_conn, para0, ghost)
    repo = _StubRepo([ghost])
    client: AsyncClient = make_client(repo)  # type: ignore[operator]

    resp = await client.get(f"/stories/{story.id}/reader")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [p["text"] for p in body["paragraphs"]] == ["A quiet room.", "Nothing here either."]
    assert all(p["highlights"] == [] for p in body["paragraphs"])
    # Nothing appeared, so the catalog is empty (no tooltips advertised for absent entities).
    assert body["entities"] == []
    # The route resolved the story to its project before the entity read.
    assert repo.asked_project == story.project_id


async def test_reader_unknown_story_404(make_client: object) -> None:
    client: AsyncClient = make_client(_StubRepo([]))  # type: ignore[operator]

    resp = await client.get(f"/stories/{uuid4()}/reader")

    assert resp.status_code == 404, resp.text


# --- M4.S3c: the reader reconciles stored manual spans + suppressions over search ----------


async def test_reader_renders_a_manual_span_with_source_and_mention_id(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # A manual tag over "her" — a pronoun search can never re-find — is surfaced as a stored span
    # carrying source="manual" + its mention_id (DM-S3c-1 B / DM-S3c-6), alongside the auto hit.
    story, (para,) = await _make_paragraphs(db_conn, "Janek met her.")
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=story.project_id)
    maria = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=story.project_id)
    await _mention(db_conn, para, janek)  # auto search hit for "Janek"
    manual = EntityMention(
        paragraph_id=para.id, entity_id=maria.id, span_start=10, span_end=13, source="manual"
    )
    await insert_entity_mention(db_conn, manual)
    client: AsyncClient = make_client(_StubRepo([janek, maria]))  # type: ignore[operator]

    resp = await client.get(f"/stories/{story.id}/reader")

    assert resp.status_code == 200, resp.text
    highlights = resp.json()["paragraphs"][0]["highlights"]
    assert highlights == [
        {
            "start": 0,
            "end": 5,
            "entity_id": str(janek.id),
            "type": "Character",
            "source": "search",
            "mention_id": None,
        },
        {
            "start": 10,
            "end": 13,
            "entity_id": str(maria.id),
            "type": "Character",
            "source": "manual",
            "mention_id": str(manual.id),
        },
    ]


async def test_reader_subtracts_a_suppressed_search_hit(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # A "not an entity" suppression at [0,5] (entity None) clears Janek's hit there; Maria's
    # hit at [10,15] is untouched.
    story, (para,) = await _make_paragraphs(db_conn, "Janek met Maria.")
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=story.project_id)
    maria = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=story.project_id)
    await _mention(db_conn, para, janek)
    await _mention(db_conn, para, maria)
    await insert_mention_suppression(
        db_conn, MentionSuppression(paragraph_id=para.id, span_start=0, span_end=5, entity_id=None)
    )
    client: AsyncClient = make_client(_StubRepo([janek, maria]))  # type: ignore[operator]

    resp = await client.get(f"/stories/{story.id}/reader")

    assert resp.status_code == 200, resp.text
    highlights = resp.json()["paragraphs"][0]["highlights"]
    assert [(h["start"], h["end"], h["entity_id"]) for h in highlights] == [(10, 15, str(maria.id))]


async def test_reader_catalog_carries_the_graph_derived_relation_summary(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # Spec §3.5: the summary is derived from the accepted graph at read time, ordered by the
    # neighbour's connection count so the hub link leads.
    #
    # The ordering must be decided by *degree*, not by the predicate tiebreak, or this test would
    # still pass with the degree term deleted from the sort key (it did, before `/code-review`
    # caught it). So: Maria is a hub with 3 distinct neighbours; Karczma is a dead end whose only
    # neighbour is Janek. The predicate tiebreak alone would put DRINKS_AT/Karczma first —
    # degree is the only thing that can put Maria ahead of it.
    story, (para,) = await _make_paragraphs(db_conn, "Janek met Maria.")
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=story.project_id)
    maria = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=story.project_id)
    karczma = GraphEntity(type="Place", canonical_name_pl="Karczma", project_id=story.project_id)
    kot = GraphEntity(type="Animal", canonical_name_pl="Kot", project_id=story.project_id)
    pies = GraphEntity(type="Animal", canonical_name_pl="Pies", project_id=story.project_id)
    await _mention(db_conn, para, janek)
    await _mention(db_conn, para, maria)
    relations = [
        GraphRelation(type="LOVES", subject_id=janek.id, object_id=maria.id, confidence=0.9),
        GraphRelation(type="DRINKS_AT", subject_id=janek.id, object_id=karczma.id, confidence=0.9),
        # Maria's other two neighbours — these are what make her the hub (3 vs Karczma's 1).
        GraphRelation(type="FEEDS", subject_id=maria.id, object_id=kot.id, confidence=0.9),
        GraphRelation(type="WALKS", subject_id=maria.id, object_id=pies.id, confidence=0.9),
    ]
    stub = _StubRepo([janek, maria, karczma, kot, pies], relations)
    client: AsyncClient = make_client(stub)  # type: ignore[operator]

    resp = await client.get(f"/stories/{story.id}/reader")

    assert resp.status_code == 200, resp.text
    catalog = {e["entity_id"]: e for e in resp.json()["entities"]}
    # Only entities that appear in the prose are catalogued — but the others still count as
    # neighbours in the summaries of the ones that do.
    assert set(catalog) == {str(janek.id), str(maria.id)}
    assert catalog[str(janek.id)]["relations"] == [
        {"direction": "out", "predicate": "LOVES", "neighbour_name": "Maria"},
        {"direction": "out", "predicate": "DRINKS_AT", "neighbour_name": "Karczma"},
    ]
    # The new relation read is scoped by the §6.4 tenancy key, like the entity read beside it.
    assert stub.asked_relations_project == story.project_id
    assert catalog[str(janek.id)]["relation_overflow"] == 0


async def test_reader_summary_caps_at_three_relations_and_counts_the_rest(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story, (para,) = await _make_paragraphs(db_conn, "Janek met Maria.")
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=story.project_id)
    await _mention(db_conn, para, janek)
    others = [
        GraphEntity(type="Place", canonical_name_pl=f"Miejsce{i}", project_id=story.project_id)
        for i in range(5)
    ]
    relations = [
        GraphRelation(type=f"VISITS_{i}", subject_id=janek.id, object_id=other.id, confidence=0.9)
        for i, other in enumerate(others)
    ]
    client: AsyncClient = make_client(_StubRepo([janek, *others], relations))  # type: ignore[operator]

    resp = await client.get(f"/stories/{story.id}/reader")

    assert resp.status_code == 200, resp.text
    entry = next(e for e in resp.json()["entities"] if e["entity_id"] == str(janek.id))
    assert len(entry["relations"]) == 3
    assert entry["relation_overflow"] == 2
