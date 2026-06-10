"""Unit tests for the ExtractionCoordinator batch driver (M2.S4, OQ-1 / OQ-2).

No I/O — fakes stand in for the agent, the graph writer, and the mention store, so
the resume-skip and the pause-and-ask behaviours are driven deterministically. A
shared event log across the fakes lets the OQ-1 write order (entities → mentions →
relations) be asserted directly.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from story_forge.adapters.llm.base import BudgetExceededError, QuotaExhaustedError
from story_forge.agents.extraction_agent import (
    EntityCandidate,
    ExtractionProposal,
    RelationCandidate,
)
from story_forge.agents.extraction_coordinator import ExtractionCoordinator
from story_forge.domain.graph import GraphEntity, GraphRelation
from story_forge.domain.models import EntityMention, Paragraph

LANG = "pl"


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


class FakeGraphWriter:
    def __init__(self, events: list[tuple[str, object]]) -> None:
        self.entities: list[GraphEntity] = []
        self.relations: list[GraphRelation] = []
        self._events = events

    async def create_entity(self, entity: GraphEntity) -> None:
        self.entities.append(entity)
        self._events.append(("entity", entity.id))

    async def create_relation(self, relation: GraphRelation) -> None:
        self.relations.append(relation)
        self._events.append(("relation", relation.id))


class FakeMentionStore:
    def __init__(self, events: list[tuple[str, object]], done: set[UUID] | None = None) -> None:
        self.mentions: list[EntityMention] = []
        self._done = done or set()
        self._events = events

    async def add_mention(self, mention: EntityMention) -> None:
        self.mentions.append(mention)
        self._done.add(mention.paragraph_id)
        self._events.append(("mention", mention.paragraph_id))

    async def paragraphs_with_mentions(self, paragraph_ids: list[UUID]) -> set[UUID]:
        return {pid for pid in paragraph_ids if pid in self._done}


def _coordinator(
    by_text: dict[str, object], *, done: set[UUID] | None = None
) -> tuple[ExtractionCoordinator, FakeGraphWriter, FakeMentionStore, list[tuple[str, object]]]:
    events: list[tuple[str, object]] = []
    graph = FakeGraphWriter(events)
    mentions = FakeMentionStore(events, done)
    coord = ExtractionCoordinator(FakeExtractor(by_text), graph, mentions)
    return coord, graph, mentions, events


async def test_ingests_all_paragraphs() -> None:
    p1, p2 = _para("Janek walked."), _para("Mokosz watched.")
    coord, graph, mentions, _ = _coordinator(
        {
            p1.content: ExtractionProposal(entities=[_entity("Janek")]),
            p2.content: ExtractionProposal(entities=[_entity("Mokosz")]),
        }
    )
    result = await coord.ingest_story(paragraphs=[p1, p2], project_id=uuid4(), language=LANG)

    assert result.paused is False
    assert result.paragraphs_total == 2
    assert result.paragraphs_done == 2
    assert result.entities_written == 2
    assert len(graph.entities) == 2
    assert len(mentions.mentions) == 2


async def test_skips_paragraphs_that_already_have_mentions() -> None:
    p1, p2 = _para("done already"), _para("still to do")
    coord, graph, _, _ = _coordinator(
        {p2.content: ExtractionProposal(entities=[_entity("Mokosz")])},
        done={p1.id},  # p1 is already done; its text is never even requested
    )
    result = await coord.ingest_story(paragraphs=[p1, p2], project_id=uuid4(), language=LANG)

    assert result.paused is False
    assert [e.canonical_name_pl for e in graph.entities] == ["Mokosz"]


async def test_pauses_on_budget_exceeded_and_reports_partial_progress() -> None:
    p1, p2, p3 = _para("first"), _para("second pauses"), _para("third never runs")
    coord, graph, mentions, _ = _coordinator(
        {
            p1.content: ExtractionProposal(entities=[_entity("Janek")]),
            p2.content: BudgetExceededError("daily budget reached"),
            p3.content: ExtractionProposal(entities=[_entity("never")]),
        }
    )
    result = await coord.ingest_story(paragraphs=[p1, p2, p3], project_id=uuid4(), language=LANG)

    assert result.paused is True
    assert result.pause_reason == "daily budget reached"
    # p1 persisted; p2 paused before any write; p3 never reached.
    assert result.paragraphs_done == 1
    assert result.entities_written == 1
    assert len(graph.entities) == 1
    assert mentions._done == {p1.id}


async def test_pauses_on_quota_exhausted() -> None:
    p1 = _para("only paragraph")
    coord, *_ = _coordinator({p1.content: QuotaExhaustedError("free quota spent")})
    result = await coord.ingest_story(paragraphs=[p1], project_id=uuid4(), language=LANG)
    assert result.paused is True
    assert result.pause_reason == "free quota spent"
    assert result.paragraphs_done == 0


async def test_zero_entity_paragraph_is_not_marked_done() -> None:
    # A transition paragraph extracts nothing → no mention → not a resume checkpoint
    # (it would be re-run on a re-POST, harmlessly). `paused` stays the completion
    # signal, not done==total.
    p1 = _para("transition")
    coord, graph, mentions, _ = _coordinator({p1.content: ExtractionProposal()})
    result = await coord.ingest_story(paragraphs=[p1], project_id=uuid4(), language=LANG)

    assert result.paused is False
    assert result.paragraphs_total == 1
    assert result.paragraphs_done == 0  # no mention written
    assert graph.entities == [] and mentions.mentions == []


async def test_write_order_is_entities_then_relations_then_mentions() -> None:
    # The mention is the resume checkpoint, so all Neo4j writes (entities, then
    # relations — which MATCH on the entity ids) must land before it. A relation
    # failure must not leave a checkpointed paragraph with missing edges.
    p1 = _para("Janek worships Mokosz")
    proposal = ExtractionProposal(
        entities=[_entity("Janek"), _entity("Mokosz")],
        relations=[
            RelationCandidate(
                subject="Janek", predicate="WORSHIPS", object="Mokosz", confidence=0.9
            )
        ],
    )
    coord, _, _, events = _coordinator({p1.content: proposal})
    await coord.ingest_story(paragraphs=[p1], project_id=uuid4(), language=LANG)

    kinds = [kind for kind, _ in events]
    assert kinds == ["entity", "entity", "relation", "mention", "mention"]


async def test_relation_write_failure_leaves_paragraph_uncheckpointed() -> None:
    # If a relation write fails (transient Neo4j error), the mention (checkpoint)
    # must NOT be written — otherwise a re-run would skip the paragraph and its
    # relations would be lost forever. The failure propagates; no checkpoint lands.
    p1 = _para("Janek worships Mokosz")
    proposal = ExtractionProposal(
        entities=[_entity("Janek"), _entity("Mokosz")],
        relations=[
            RelationCandidate(
                subject="Janek", predicate="WORSHIPS", object="Mokosz", confidence=0.9
            )
        ],
    )
    events: list[tuple[str, object]] = []
    mentions = FakeMentionStore(events)
    graph = FakeGraphWriter(events)

    async def _boom(_relation: GraphRelation) -> None:
        raise RuntimeError("neo4j unavailable")

    graph.create_relation = _boom  # type: ignore[method-assign]
    coord = ExtractionCoordinator(FakeExtractor({p1.content: proposal}), graph, mentions)

    with pytest.raises(RuntimeError):
        await coord.ingest_story(paragraphs=[p1], project_id=uuid4(), language=LANG)

    assert mentions.mentions == []  # not checkpointed → a re-run will retry it
    assert p1.id not in mentions._done


async def test_no_dedupe_two_identical_candidates_persist_two_nodes() -> None:
    p1 = _para("Mokosz, Mokosz")
    coord, graph, _, _ = _coordinator(
        {p1.content: ExtractionProposal(entities=[_entity("Mokosz"), _entity("Mokosz")])}
    )
    await coord.ingest_story(paragraphs=[p1], project_id=uuid4(), language=LANG)
    assert len(graph.entities) == 2
    assert graph.entities[0].id != graph.entities[1].id
