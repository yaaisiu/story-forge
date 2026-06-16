"""Integration: the relation-write path end to end (M3.S4e, spec §3.3's 5th human action).

Exercises the real stores against the throwaway test DB + the real compose Neo4j. A paragraph
extracts two entity candidates *and* a relation between them; the coordinator stages all three
(writing **zero** graph edges). After the human accepts both endpoint candidates, the
`RelationReviewService` is the only thing that writes an edge, and only on an explicit decide:

- accept both endpoints → `decide(commit)` writes exactly ONE edge between the committed
  entities; a retried commit doubles nothing (MERGE-by-id idempotency);
- accept only one endpoint → the relation is held (not committable) and a forced commit 409s;
- reject → no edge.

Teardown mirrors `test_candidates`: the PG tree is removed by deleting the project (staged
relations cascade off the `paragraph_id` FK); the Neo4j side is scoped to a fresh `project_id`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import psycopg
import pytest
import pytest_asyncio

from story_forge.adapters import postgres_repo as repo
from story_forge.adapters.accepted_entity_reader import AcceptedEntityReader
from story_forge.adapters.db import libpq_kwargs
from story_forge.adapters.neo4j_repo import Neo4jRepo
from story_forge.adapters.postgres_candidate_store import PostgresCandidateStore
from story_forge.adapters.postgres_mention_store import PostgresMentionStore
from story_forge.adapters.postgres_relation_store import PostgresRelationStore
from story_forge.agents.candidate_review import CandidateReviewService
from story_forge.agents.candidate_staging import CandidateStager
from story_forge.agents.extraction_agent import (
    EntityCandidate,
    ExtractionProposal,
    RelationCandidate,
)
from story_forge.agents.extraction_coordinator import ExtractionCoordinator
from story_forge.agents.matching_agent import MatchingAgent
from story_forge.agents.relation_review import (
    RelationEndpointsUnresolved,
    RelationReviewService,
)
from story_forge.config import settings
from story_forge.domain.models import Chapter, Paragraph, Project, Scene, Story

pytestmark = pytest.mark.integration

VEC = [0.1] * 768


def _entity(name: str) -> EntityCandidate:
    return EntityCandidate(candidate_name=name, type="Character", match_confidence=0.5)


def _relation(subject: str, predicate: str, object_: str) -> RelationCandidate:
    return RelationCandidate(subject=subject, predicate=predicate, object=object_, confidence=0.9)


class _FakeEmbedder:
    def encode(self, text: str) -> list[float]:
        return VEC


class _FakeJudge:
    async def judge(self, **kwargs: object) -> object:  # pragma: no cover - must not be called
        raise AssertionError("judge must not be reached with an empty accepted graph")


@dataclass
class _Live:
    graph: Neo4jRepo
    project: Project
    story: Story
    paragraphs: list[Paragraph]
    store: PostgresCandidateStore
    relations: PostgresRelationStore
    reader: AcceptedEntityReader
    review: CandidateReviewService
    relation_review: RelationReviewService
    conninfo: dict[str, object]

    def coordinator(self, by_text: dict[str, ExtractionProposal]) -> ExtractionCoordinator:
        class _Extractor:
            async def propose_extraction(
                self, *, paragraph_text: str, language: str
            ) -> ExtractionProposal:
                return by_text.get(paragraph_text, ExtractionProposal())

        stager = CandidateStager(_FakeEmbedder(), MatchingAgent(), _FakeJudge())
        return ExtractionCoordinator(_Extractor(), stager, self.store, self.reader)


@pytest_asyncio.fixture
async def live(_migrated_test_db: None) -> AsyncIterator[_Live]:
    conninfo = libpq_kwargs(settings.test_database_url)
    graph = await Neo4jRepo.connect(
        uri=settings.neo4j_uri, user=settings.neo4j_user, password=settings.neo4j_password
    )
    project = Project(name="Rel Test", language="pl")
    story = Story(project_id=project.id, title="Book", raw_text="x")
    chapter = Chapter(story_id=story.id, order_index=0)
    scene = Scene(chapter_id=chapter.id, order_index=0)
    paragraphs = [
        Paragraph(scene_id=scene.id, order_index=0, content="Janek and Mokosz met."),
        Paragraph(scene_id=scene.id, order_index=1, content="A quiet transition."),
    ]
    async with await psycopg.AsyncConnection.connect(autocommit=True, **conninfo) as conn:  # type: ignore[arg-type]
        await repo.insert_project(conn, project)
        await repo.insert_story(conn, story)
        await repo.insert_chapter(conn, chapter)
        await repo.insert_scene(conn, scene)
        for paragraph in paragraphs:
            await repo.insert_paragraph(conn, paragraph)

    store = PostgresCandidateStore(conninfo)
    relations = PostgresRelationStore(conninfo)
    mentions = PostgresMentionStore(conninfo)
    reader = AcceptedEntityReader(graph, conninfo)
    review = CandidateReviewService(graph, store, mentions)
    relation_review = RelationReviewService(graph, relations, store)
    try:
        yield _Live(
            graph,
            project,
            story,
            paragraphs,
            store,
            relations,
            reader,
            review,
            relation_review,
            conninfo,
        )
    finally:
        async with await psycopg.AsyncConnection.connect(autocommit=True, **conninfo) as conn:  # type: ignore[arg-type]
            await repo.delete_project(conn, project.id)  # cascades candidates / relations / marker
        await graph.delete_project_graph(project.id)
        await graph.close()


async def _ingest(live: _Live, by_text: dict[str, ExtractionProposal]) -> None:
    await live.coordinator(by_text).ingest_story(
        paragraphs=live.paragraphs,
        project_id=live.project.id,
        story_id=live.story.id,
        language="pl",
    )


async def _accept(live: _Live, name: str) -> None:
    """Accept the pending candidate with the given name (creates its entity node)."""
    candidate = next(
        c for c in await live.store.list_pending(live.story.id) if c.candidate_name == name
    )
    await live.review.accept(candidate.id, language="pl")


_PROPOSAL = ExtractionProposal(
    entities=[_entity("Janek"), _entity("Mokosz")],
    relations=[_relation("Janek", "KNOWS", "Mokosz")],
)


async def test_extract_stages_relation_and_writes_no_edge(live: _Live) -> None:
    await _ingest(live, {live.paragraphs[0].content: _PROPOSAL})

    # The relation is staged but no edge is written (INV-9 — extraction writes zero graph).
    staged = await live.relations.list_staged(live.story.id)
    assert [(r.subject, r.predicate, r.object) for r in staged] == [("Janek", "KNOWS", "Mokosz")]
    assert await live.graph.get_relations(live.project.id) == []
    # Not committable until both endpoints are accepted.
    assert await live.relation_review.list_committable(live.story.id) == []


async def test_commit_writes_one_edge_between_accepted_endpoints(live: _Live) -> None:
    await _ingest(live, {live.paragraphs[0].content: _PROPOSAL})
    await _accept(live, "Janek")
    await _accept(live, "Mokosz")

    committable = await live.relation_review.list_committable(live.story.id)
    assert len(committable) == 1
    result = await live.relation_review.decide(committable[0].relation.id, action="commit")

    assert result.status == "written"
    edges = await live.graph.get_relations(live.project.id)
    assert len(edges) == 1  # exactly ONE edge
    assert edges[0].type == "KNOWS"
    assert edges[0].subject_id == committable[0].subject_entity_id
    assert edges[0].object_id == committable[0].object_entity_id
    # No longer committable once written.
    assert await live.relation_review.list_committable(live.story.id) == []


async def test_recommit_is_idempotent_no_double_edge(live: _Live) -> None:
    await _ingest(live, {live.paragraphs[0].content: _PROPOSAL})
    await _accept(live, "Janek")
    await _accept(live, "Mokosz")
    rel_id = (await live.relation_review.list_committable(live.story.id))[0].relation.id

    await live.relation_review.decide(rel_id, action="commit")
    second = await live.relation_review.decide(rel_id, action="commit")  # double-submit

    assert second.already_decided is True
    assert len(await live.graph.get_relations(live.project.id)) == 1  # still one edge


async def test_held_when_one_endpoint_unaccepted(live: _Live) -> None:
    await _ingest(live, {live.paragraphs[0].content: _PROPOSAL})
    await _accept(live, "Janek")  # Mokosz left pending

    assert await live.relation_review.list_committable(live.story.id) == []
    rel = (await live.relations.list_staged(live.story.id))[0]
    with pytest.raises(RelationEndpointsUnresolved):
        await live.relation_review.decide(rel.id, action="commit")
    assert await live.graph.get_relations(live.project.id) == []


async def test_reject_writes_no_edge(live: _Live) -> None:
    await _ingest(live, {live.paragraphs[0].content: _PROPOSAL})
    await _accept(live, "Janek")
    await _accept(live, "Mokosz")
    rel_id = (await live.relation_review.list_committable(live.story.id))[0].relation.id

    result = await live.relation_review.decide(rel_id, action="reject")

    assert result.status == "rejected"
    assert await live.graph.get_relations(live.project.id) == []
    assert await live.relation_review.list_committable(live.story.id) == []


async def test_resume_does_not_double_stage_relations(live: _Live) -> None:
    by_text = {live.paragraphs[0].content: _PROPOSAL}
    await _ingest(live, by_text)
    await _ingest(live, by_text)  # re-run — the marker skips the paragraph

    staged = await live.relations.list_staged(live.story.id)
    assert len(staged) == 1  # deterministic id + ON CONFLICT — no duplicate row
