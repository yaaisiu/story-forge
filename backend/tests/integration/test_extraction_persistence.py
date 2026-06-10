"""End-to-end graph persistence for M2.S4: ExtractionCoordinator over live stores.

Exercises the real write path — `ExtractionCoordinator` driving a fake extractor
into a live `Neo4jRepo` + live `PostgresMentionStore` — so the OQ-1 cross-store
write (entities → Neo4j, mentions → Postgres, relations → Neo4j) and the OQ-2 resume
checkpoint are proven against real databases, not fakes.

The mention store commits on its own connection (the resumability requirement), so
it can't ride the `db_conn` rollback fixture. Instead the tree + paragraphs are
committed via an autocommit connection and torn down by deleting the project (the
`paragraph_id` FK cascades the mentions); the Neo4j side is scoped to a fresh
`project_id` and DETACH-DELETEd on teardown, like `test_neo4j_repo`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import psycopg
import pytest
import pytest_asyncio

from story_forge.adapters import postgres_repo as repo
from story_forge.adapters.db import libpq_kwargs
from story_forge.adapters.neo4j_repo import Neo4jRepo
from story_forge.adapters.postgres_mention_store import PostgresMentionStore
from story_forge.agents.extraction_agent import (
    EntityCandidate,
    ExtractionProposal,
    RelationCandidate,
)
from story_forge.agents.extraction_coordinator import ExtractionCoordinator
from story_forge.config import settings
from story_forge.domain.models import Chapter, EntityMention, Paragraph, Project, Scene, Story

pytestmark = pytest.mark.integration


def _entity(name: str) -> EntityCandidate:
    return EntityCandidate(candidate_name=name, type="Character", match_confidence=0.5)


class FakeExtractor:
    """Returns the proposal queued for a paragraph's text (no real LLM)."""

    def __init__(self, by_text: dict[str, ExtractionProposal]) -> None:
        self._by_text = by_text

    async def propose_extraction(self, *, paragraph_text: str, language: str) -> ExtractionProposal:
        return self._by_text[paragraph_text]


@pytest_asyncio.fixture
async def live(
    _migrated_test_db: None,
) -> AsyncIterator[tuple[Neo4jRepo, Project, list[Paragraph], PostgresMentionStore]]:
    """A live Neo4j repo + a committed PG tree with two paragraphs + a mention store."""
    conninfo = libpq_kwargs(settings.test_database_url)
    graph = await Neo4jRepo.connect(
        uri=settings.neo4j_uri, user=settings.neo4j_user, password=settings.neo4j_password
    )
    project = Project(name="Ingest Test", language="pl")
    story = Story(project_id=project.id, title="Book", raw_text="x")
    chapter = Chapter(story_id=story.id, order_index=0)
    scene = Scene(chapter_id=chapter.id, order_index=0)
    paragraphs = [
        Paragraph(scene_id=scene.id, order_index=0, content="Janek worships Mokosz."),
        Paragraph(scene_id=scene.id, order_index=1, content="A quiet transition."),
    ]
    async with await psycopg.AsyncConnection.connect(autocommit=True, **conninfo) as conn:  # type: ignore[arg-type]
        await repo.insert_project(conn, project)
        await repo.insert_story(conn, story)
        await repo.insert_chapter(conn, chapter)
        await repo.insert_scene(conn, scene)
        for paragraph in paragraphs:
            await repo.insert_paragraph(conn, paragraph)

    mentions = PostgresMentionStore(conninfo)
    try:
        yield graph, project, paragraphs, mentions
    finally:
        async with await psycopg.AsyncConnection.connect(autocommit=True, **conninfo) as conn:  # type: ignore[arg-type]
            await repo.delete_project(conn, project.id)  # cascades paragraphs + mentions
        await graph.delete_project_graph(project.id)
        await graph.close()


async def test_ingest_persists_entities_relations_and_mentions(
    live: tuple[Neo4jRepo, Project, list[Paragraph], PostgresMentionStore],
) -> None:
    graph, project, paragraphs, mentions = live
    p1 = paragraphs[0]
    extractor = FakeExtractor(
        {
            p1.content: ExtractionProposal(
                entities=[_entity("Janek"), _entity("Mokosz")],
                relations=[
                    RelationCandidate(
                        subject="Janek", predicate="WORSHIPS", object="Mokosz", confidence=0.9
                    )
                ],
            )
        }
    )
    coord = ExtractionCoordinator(extractor, graph, mentions)

    result = await coord.ingest_story(paragraphs=[p1], project_id=project.id, language="pl")

    assert result.paused is False
    assert await graph.count_entities(project.id) == 2
    relations = await graph.get_relations(project.id)
    assert [r.type for r in relations] == ["WORSHIPS"]
    # The cross-store mention back-reference holds for the processed paragraph.
    assert await mentions.paragraphs_with_mentions([p1.id]) == {p1.id}


async def test_no_dedupe_two_identical_candidates_make_two_nodes(
    live: tuple[Neo4jRepo, Project, list[Paragraph], PostgresMentionStore],
) -> None:
    graph, project, paragraphs, mentions = live
    p1 = paragraphs[0]
    extractor = FakeExtractor(
        {p1.content: ExtractionProposal(entities=[_entity("Mokosz"), _entity("Mokosz")])}
    )
    coord = ExtractionCoordinator(extractor, graph, mentions)

    await coord.ingest_story(paragraphs=[p1], project_id=project.id, language="pl")

    # INV-8: identical candidates are not merged — two physical nodes.
    assert await graph.count_entities(project.id) == 2


async def test_resume_skips_a_paragraph_that_already_has_a_mention(
    live: tuple[Neo4jRepo, Project, list[Paragraph], PostgresMentionStore],
) -> None:
    graph, project, paragraphs, mentions = live
    p1, p2 = paragraphs
    # Pre-commit a mention for p1 (a prior, interrupted run), then ingest both.
    await mentions.add_mention(EntityMention(paragraph_id=p1.id, entity_id=uuid4()))
    extractor = FakeExtractor({p2.content: ExtractionProposal(entities=[_entity("Mokosz")])})
    coord = ExtractionCoordinator(extractor, graph, mentions)

    result = await coord.ingest_story(paragraphs=[p1, p2], project_id=project.id, language="pl")

    # Only p2 produced a node; p1 was skipped (no double-write), so exactly one entity.
    assert result.paused is False
    assert await graph.count_entities(project.id) == 1
