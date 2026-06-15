"""Unit tests for the ExtractionCoordinator batch driver (M3.S4a, OQ-1 / OQ-2).

No I/O — fakes stand in for the extraction agent, the §3.3 cascade stager, the accepted-graph
reader, and the candidate store, so the resume-skip, the pause-and-ask, and the **invariant
flip** (extraction stages candidates and writes *zero* graph nodes) are driven deterministically.

This replaces M2.S4's `test_no_dedupe_two_identical_candidates_persist_two_nodes`: under
intercept-before-write the coordinator has no graph writer at all — two identical candidates
*both stage* and the human dedupes them at the review queue (INV-1), never the machine (INV-9).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from story_forge.adapters.llm.base import BudgetExceededError, QuotaExhaustedError
from story_forge.agents.candidate_staging import StagedParagraph
from story_forge.agents.extraction_agent import (
    EntityCandidate,
    ExtractionProposal,
    RelationCandidate,
)
from story_forge.agents.extraction_coordinator import ExtractionCoordinator
from story_forge.domain.candidates import AcceptedSnapshot, StagedCandidate
from story_forge.domain.models import Paragraph

LANG = "pl"
PROJECT = uuid4()
STORY = uuid4()


def _para(content: str) -> Paragraph:
    return Paragraph(scene_id=uuid4(), order_index=0, content=content)


def _entity(name: str) -> EntityCandidate:
    return EntityCandidate(candidate_name=name, type="Character", match_confidence=0.5)


class FakeExtractor:
    """Returns a queued proposal (or raises a queued exception) per paragraph text."""

    def __init__(self, by_text: dict[str, object]) -> None:
        self._by_text = by_text

    async def propose_extraction(self, *, paragraph_text: str, language: str) -> ExtractionProposal:
        item = self._by_text[paragraph_text]
        if isinstance(item, Exception):
            raise item
        assert isinstance(item, ExtractionProposal)
        return item


class FakeStager:
    """Stages one NEW-proposed candidate per proposal entity — or raises a queued exception.

    The cascade itself is exercised in `test_candidate_staging.py`; here the stager is a
    stand-in so the driver's resume/pause/staging behaviour is isolated.
    """

    def __init__(self, raise_on: dict[UUID, Exception] | None = None) -> None:
        self._raise_on = raise_on or {}

    async def stage(
        self,
        *,
        proposal: ExtractionProposal,
        paragraph: Paragraph,
        project_id: UUID,
        story_id: UUID,
        language: str,
        snapshot: AcceptedSnapshot,
    ) -> StagedParagraph:
        if paragraph.id in self._raise_on:
            raise self._raise_on[paragraph.id]
        candidates = [
            StagedCandidate(
                project_id=project_id,
                story_id=story_id,
                paragraph_id=paragraph.id,
                candidate_name=e.candidate_name,
                type=e.type,
                properties=e.properties,
                context=paragraph.content,
                proposal="new",
                stage_reached=1,
            )
            for e in proposal.entities
        ]
        relations = [r.model_dump() for r in proposal.relations]
        return StagedParagraph(candidates=candidates, relations=relations)


class FakeReader:
    def __init__(self) -> None:
        self.calls = 0

    async def load_accepted(self, project_id: UUID) -> AcceptedSnapshot:
        self.calls += 1
        return AcceptedSnapshot()


class FakeCandidateStore:
    def __init__(self, processed: set[UUID] | None = None) -> None:
        self.candidates: list[StagedCandidate] = []
        self.relations: list[dict[str, object]] = []
        self._processed = processed or set()

    async def persist(
        self,
        *,
        paragraph_id: UUID,
        story_id: UUID,
        candidates: list[StagedCandidate],
        relations: list[dict[str, object]],
    ) -> None:
        self.candidates.extend(candidates)
        self.relations.extend(relations)
        self._processed.add(paragraph_id)

    async def paragraphs_processed(self, paragraph_ids: list[UUID]) -> set[UUID]:
        return {pid for pid in paragraph_ids if pid in self._processed}


def _coordinator(
    by_text: dict[str, object],
    *,
    processed: set[UUID] | None = None,
    stager: FakeStager | None = None,
) -> tuple[ExtractionCoordinator, FakeCandidateStore, FakeReader]:
    store = FakeCandidateStore(processed)
    reader = FakeReader()
    coord = ExtractionCoordinator(FakeExtractor(by_text), stager or FakeStager(), store, reader)
    return coord, store, reader


async def _ingest(coord: ExtractionCoordinator, paragraphs: list[Paragraph]):
    return await coord.ingest_story(
        paragraphs=paragraphs, project_id=PROJECT, story_id=STORY, language=LANG
    )


async def test_stages_all_paragraphs() -> None:
    p1, p2 = _para("Janek walked."), _para("Mokosz watched.")
    coord, store, _ = _coordinator(
        {
            p1.content: ExtractionProposal(entities=[_entity("Janek")]),
            p2.content: ExtractionProposal(entities=[_entity("Mokosz")]),
        }
    )
    result = await _ingest(coord, [p1, p2])

    assert result.paused is False
    assert result.paragraphs_total == 2
    assert result.paragraphs_done == 2
    assert result.candidates_staged == 2
    assert [c.candidate_name for c in store.candidates] == ["Janek", "Mokosz"]
    assert all(c.status == "review-queued" for c in store.candidates)


async def test_skips_already_processed_paragraphs() -> None:
    p1, p2 = _para("done already"), _para("still to do")
    coord, store, _ = _coordinator(
        {p2.content: ExtractionProposal(entities=[_entity("Mokosz")])},
        processed={p1.id},  # p1 is already staged; its text is never even requested
    )
    result = await _ingest(coord, [p1, p2])

    assert result.paused is False
    assert [c.candidate_name for c in store.candidates] == ["Mokosz"]


async def test_zero_candidate_paragraph_is_still_processed() -> None:
    # A transition paragraph stages no candidate, but a marker is written so a re-POST
    # does NOT reprocess it (the M2 "wasted re-run" wart, fixed by the resume marker).
    p1 = _para("transition")
    coord, store, _ = _coordinator({p1.content: ExtractionProposal()})
    result = await _ingest(coord, [p1])

    assert result.paused is False
    assert result.paragraphs_done == 1  # processed via the marker, despite zero candidates
    assert result.candidates_staged == 0
    assert store.candidates == []
    assert await store.paragraphs_processed([p1.id]) == {p1.id}


async def test_reads_accepted_snapshot_once_per_run() -> None:
    p1, p2 = _para("a"), _para("b")
    coord, _, reader = _coordinator(
        {
            p1.content: ExtractionProposal(entities=[_entity("Janek")]),
            p2.content: ExtractionProposal(entities=[_entity("Mokosz")]),
        }
    )
    await _ingest(coord, [p1, p2])
    assert reader.calls == 1  # one snapshot read for the whole batch, not per paragraph


async def test_does_not_read_snapshot_when_all_processed() -> None:
    p1 = _para("done")
    coord, _, reader = _coordinator({}, processed={p1.id})
    await _ingest(coord, [p1])
    assert reader.calls == 0  # nothing to do → no graph read


async def test_pauses_on_budget_during_extraction() -> None:
    p1, p2, p3 = _para("first"), _para("second pauses"), _para("third never runs")
    coord, store, _ = _coordinator(
        {
            p1.content: ExtractionProposal(entities=[_entity("Janek")]),
            p2.content: BudgetExceededError("daily budget reached"),
            p3.content: ExtractionProposal(entities=[_entity("never")]),
        }
    )
    result = await _ingest(coord, [p1, p2, p3])

    assert result.paused is True
    assert result.pause_reason == "daily budget reached"
    # p1 staged; p2 paused before any write; p3 never reached.
    assert result.paragraphs_done == 1
    assert result.candidates_staged == 1
    assert [c.candidate_name for c in store.candidates] == ["Janek"]


async def test_pauses_on_budget_during_cascade_without_persisting_paragraph() -> None:
    # The Stage-3 judge can hit the budget mid-cascade. The paragraph must NOT be
    # persisted half-staged: it stays un-checkpointed so a re-run re-stages it whole.
    p1, p2 = _para("first"), _para("second pauses in cascade")
    stager = FakeStager(raise_on={p2.id: BudgetExceededError("budget reached in judge")})
    coord, store, _ = _coordinator(
        {
            p1.content: ExtractionProposal(entities=[_entity("Janek")]),
            p2.content: ExtractionProposal(entities=[_entity("Mokosz")]),
        },
        stager=stager,
    )
    result = await _ingest(coord, [p1, p2])

    assert result.paused is True
    assert result.pause_reason == "budget reached in judge"
    assert result.paragraphs_done == 1
    assert [c.candidate_name for c in store.candidates] == ["Janek"]
    assert await store.paragraphs_processed([p2.id]) == set()  # not checkpointed → retryable


async def test_pauses_on_quota_exhausted() -> None:
    p1 = _para("only paragraph")
    coord, _, _ = _coordinator({p1.content: QuotaExhaustedError("free quota spent")})
    result = await _ingest(coord, [p1])
    assert result.paused is True
    assert result.pause_reason == "free quota spent"
    assert result.paragraphs_done == 0


async def test_two_identical_candidates_both_stage_and_write_no_graph() -> None:
    # The invariant flip (replaces M2.S4's two-identical-candidates → two-nodes test):
    # the coordinator has NO graph writer, so two identical candidates both *stage*
    # (status review-queued) and nothing reaches Neo4j. The human dedupes at Stage 4.
    p1 = _para("Mokosz, Mokosz")
    coord, store, _ = _coordinator(
        {p1.content: ExtractionProposal(entities=[_entity("Mokosz"), _entity("Mokosz")])}
    )
    result = await _ingest(coord, [p1])

    assert result.candidates_staged == 2
    assert [c.candidate_name for c in store.candidates] == ["Mokosz", "Mokosz"]
    assert all(c.status == "review-queued" and c.proposal == "new" for c in store.candidates)
    # Distinct staged rows — the human, not the machine, decides they are the same entity.
    assert store.candidates[0].id != store.candidates[1].id


async def test_stages_relations_as_data() -> None:
    # Relations are staged (preserved) but no edge is written in S4a — the write +
    # re-point is S4b, once both endpoints are accepted.
    p1 = _para("Janek worships Mokosz")
    proposal = ExtractionProposal(
        entities=[_entity("Janek"), _entity("Mokosz")],
        relations=[
            RelationCandidate(
                subject="Janek", predicate="WORSHIPS", object="Mokosz", confidence=0.9
            )
        ],
    )
    coord, store, _ = _coordinator({p1.content: proposal})
    await _ingest(coord, [p1])

    assert len(store.relations) == 1
    assert store.relations[0]["predicate"] == "WORSHIPS"
