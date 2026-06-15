"""Integration: the intercept-before-write path end to end (M3.S4a, spec §9 M3).

Exercises the real stores against the throwaway test DB + the real compose Neo4j: the
coordinator *stages* candidates (writing **zero** graph nodes — the invariant flip), and the
`CandidateReviewService` is the only thing that writes Neo4j, on a human accept. The §3.3
cascade itself is driven with a fake embedder/judge (the embedding model wheels are not in CI;
the cascade routing is unit-tested in `test_candidate_staging.py`) — here the focus is the
cross-store persistence: staging, the resume marker, the accept-time writes, and rejection memory.

Teardown mirrors `test_neo4j_repo`: the PG tree is committed on an autocommit connection and
removed by deleting the project (candidates / decisions / mentions / marker cascade off the
`paragraph_id` / `candidate_id` FKs); the Neo4j side is scoped to a fresh `project_id`.
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
from story_forge.agents.candidate_rematch import ReMatchService
from story_forge.agents.candidate_review import CandidateReviewService
from story_forge.agents.candidate_staging import CandidateStager
from story_forge.agents.extraction_agent import EntityCandidate, ExtractionProposal
from story_forge.agents.extraction_coordinator import ExtractionCoordinator
from story_forge.agents.matching_agent import MatchingAgent
from story_forge.config import settings
from story_forge.domain.models import Chapter, Paragraph, Project, Scene, Story

pytestmark = pytest.mark.integration

VEC = [0.1] * 768


def _entity(name: str) -> EntityCandidate:
    return EntityCandidate(candidate_name=name, type="Character", match_confidence=0.5)


class _FakeEmbedder:
    def encode(self, text: str) -> list[float]:
        return VEC


class _FakeJudge:
    """The empty-graph runs never reach Stage 3 (all candidates score NEW); guard that."""

    async def judge(self, **kwargs: object) -> object:  # pragma: no cover - must not be called
        raise AssertionError("judge must not be reached with an empty accepted graph")


@dataclass
class _Live:
    graph: Neo4jRepo
    project: Project
    story: Story
    paragraphs: list[Paragraph]
    store: PostgresCandidateStore
    reader: AcceptedEntityReader
    review: CandidateReviewService
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
    project = Project(name="Cand Test", language="pl")
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
    mentions = PostgresMentionStore(conninfo)
    reader = AcceptedEntityReader(graph, conninfo)
    review = CandidateReviewService(
        graph, store, mentions, rematch=ReMatchService(MatchingAgent(), store)
    )
    try:
        yield _Live(graph, project, story, paragraphs, store, reader, review, conninfo)
    finally:
        async with await psycopg.AsyncConnection.connect(autocommit=True, **conninfo) as conn:  # type: ignore[arg-type]
            await repo.delete_project(conn, project.id)  # cascades candidates / marker / mentions
        await graph.delete_project_graph(project.id)
        await graph.close()


async def _ingest(live: _Live, by_text: dict[str, ExtractionProposal]) -> None:
    await live.coordinator(by_text).ingest_story(
        paragraphs=live.paragraphs,
        project_id=live.project.id,
        story_id=live.story.id,
        language="pl",
    )


async def _decision_count(live: _Live, candidate_id: object) -> int:
    async with await psycopg.AsyncConnection.connect(autocommit=True, **live.conninfo) as conn:  # type: ignore[arg-type]
        cur = await conn.execute(
            "SELECT count(*) FROM candidate_decisions WHERE candidate_id = %s", (candidate_id,)
        )
        row = await cur.fetchone()
    return int(row[0]) if row else 0


async def test_extract_stages_candidates_and_writes_no_graph(live: _Live) -> None:
    p1 = live.paragraphs[0]
    await _ingest(
        live, {p1.content: ExtractionProposal(entities=[_entity("Janek"), _entity("Mokosz")])}
    )

    # The invariant flip: zero Neo4j nodes after extraction — only staged rows.
    assert await live.graph.count_entities(live.project.id) == 0
    pending = await live.store.list_pending(live.story.id)
    assert sorted(c.candidate_name for c in pending) == ["Janek", "Mokosz"]
    assert all(c.proposal == "new" and c.status == "review-queued" for c in pending)
    # Both paragraphs are checkpointed — incl. the zero-candidate transition paragraph.
    processed = await live.store.paragraphs_processed([p.id for p in live.paragraphs])
    assert processed == {p.id for p in live.paragraphs}


async def test_accept_writes_entity_mention_evidence_and_flips_status(live: _Live) -> None:
    p1 = live.paragraphs[0]
    await _ingest(live, {p1.content: ExtractionProposal(entities=[_entity("Janek")])})
    candidate = (await live.store.list_pending(live.story.id))[0]

    result = await live.review.accept(candidate.id, language="pl")

    assert result.status == "created"
    assert await live.graph.count_entities(live.project.id) == 1
    # The mention landed with the candidate's context vector (copied at accept-time).
    async with await psycopg.AsyncConnection.connect(autocommit=True, **live.conninfo) as conn:  # type: ignore[arg-type]
        from pgvector.psycopg import register_vector_async

        await register_vector_async(conn)
        mentions = await repo.list_entity_mentions_for_paragraph(conn, candidate.paragraph_id)
    assert len(mentions) == 1
    assert mentions[0].entity_id == result.entity_id
    assert mentions[0].embedding is not None
    assert await _decision_count(live, candidate.id) == 1
    assert (await live.store.get(candidate.id)).status == "created"  # type: ignore[union-attr]
    # No longer in the pending queue.
    assert await live.store.list_pending(live.story.id) == []


async def test_accept_rematches_pending_duplicates_without_writing_graph(live: _Live) -> None:
    """M3.S4c flip test — the intra-batch dedup the browser walk surfaced.

    A first pass stages 'Janek' ×3 against the empty graph as three independent NEW proposals
    the queue cannot merge. Accepting the first re-runs the deterministic matcher over the two
    still-pending Janeks: they fuzz-match the just-accepted entity (Stage 1 > 85%) and flip
    `new → merge` targeting it — and re-match writes **zero** new Neo4j nodes (only the accept's
    own create), so INV-9 holds (graph count stays 1).
    """
    p1 = live.paragraphs[0]
    await _ingest(
        live,
        {p1.content: ExtractionProposal(entities=[_entity("Janek") for _ in range(3)])},
    )
    pending = await live.store.list_pending(live.story.id)
    assert len(pending) == 3 and all(c.proposal == "new" for c in pending)

    result = await live.review.accept(pending[0].id, language="pl")

    # The flip: the accept created exactly one node; re-match added none (INV-9 holds).
    assert result.status == "created"
    assert await live.graph.count_entities(live.project.id) == 1

    # The two still-pending Janeks now propose a merge into the accepted entity.
    remaining = await live.store.list_pending(live.story.id)
    assert len(remaining) == 2
    assert all(c.proposal == "merge" for c in remaining)
    assert all(c.target_entity_id == result.entity_id for c in remaining)
    assert all(c.stage_reached == 1 for c in remaining)


async def test_reject_remembers_and_writes_no_graph(live: _Live) -> None:
    p1 = live.paragraphs[0]
    await _ingest(live, {p1.content: ExtractionProposal(entities=[_entity("Janek")])})
    candidate = (await live.store.list_pending(live.story.id))[0]

    result = await live.review.reject(candidate.id)

    assert result.status == "rejected"
    assert await live.graph.count_entities(live.project.id) == 0
    assert await _decision_count(live, candidate.id) == 1  # the rejection is remembered (DM-rej)
    assert (await live.store.get(candidate.id)).status == "rejected"  # type: ignore[union-attr]


async def test_resume_skips_already_staged_paragraphs(live: _Live) -> None:
    p1 = live.paragraphs[0]
    by_text = {p1.content: ExtractionProposal(entities=[_entity("Janek")])}
    await _ingest(live, by_text)
    await _ingest(live, by_text)  # re-run

    # Re-staging is skipped (the marker), so exactly one candidate exists, not two.
    pending = await live.store.list_pending(live.story.id)
    assert [c.candidate_name for c in pending] == ["Janek"]


async def test_reaccept_is_idempotent_no_double_node(live: _Live) -> None:
    p1 = live.paragraphs[0]
    await _ingest(live, {p1.content: ExtractionProposal(entities=[_entity("Janek")])})
    candidate = (await live.store.list_pending(live.story.id))[0]

    await live.review.accept(candidate.id, language="pl")
    second = await live.review.accept(candidate.id, language="pl")  # re-accept

    assert second.already_decided is True
    assert await live.graph.count_entities(live.project.id) == 1  # no duplicate node
