"""Unit tests for the CandidateReviewService — the human-accept write path (M3.S4a).

No I/O: fakes stand in for the graph writer, the mention writer, and the candidate store, with a
shared event log to assert the cross-store **write order** (Neo4j → mention → evidence → status,
the last write). These pin the accept-path idempotency contract (a retry before the status flip
makes no duplicate node, because the entity id is deterministic) and the TOCTOU merge-target guard.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from story_forge.agents.candidate_review import (
    CandidateNotFound,
    CandidateReviewService,
    StaleMergeTarget,
)
from story_forge.domain.candidates import CandidateDecision, CandidateStatus, StagedCandidate
from story_forge.domain.graph import GraphEntity
from story_forge.domain.models import EntityMention

LANG = "pl"


def _candidate(*, proposal: str = "new", target: UUID | None = None) -> StagedCandidate:
    return StagedCandidate(
        project_id=uuid4(),
        story_id=uuid4(),
        paragraph_id=uuid4(),
        candidate_name="Bronek",
        type="Character",
        context="Bronek walked.",
        context_embedding=[0.1] * 768,
        proposal=proposal,  # type: ignore[arg-type]
        target_entity_id=target,
        stage_reached=1,
    )


class FakeGraph:
    """Records writes; stores entities by id so a deterministic re-create is a no-op."""

    def __init__(
        self, events: list[tuple[str, object]], *, existing: set[UUID] | None = None
    ) -> None:
        self.entities: dict[UUID, GraphEntity] = {}
        self.aliases: list[tuple[UUID, str]] = []
        self._existing = existing or set()
        self._events = events

    async def create_entity(self, entity: GraphEntity) -> None:
        self.entities[entity.id] = entity
        self._existing.add(entity.id)
        self._events.append(("entity", entity.id))

    async def add_alias(self, entity_id: UUID, alias: str) -> None:
        self.aliases.append((entity_id, alias))
        self._events.append(("alias", entity_id))

    async def get_entity(self, entity_id: UUID) -> GraphEntity | None:
        return (
            GraphEntity(type="Character", project_id=uuid4(), id=entity_id)
            if entity_id in self._existing
            else None
        )


class FakeMentions:
    def __init__(self, events: list[tuple[str, object]]) -> None:
        self.mentions: list[EntityMention] = []
        self._events = events

    async def add_mention(self, mention: EntityMention) -> None:
        self.mentions.append(mention)
        self._events.append(("mention", mention.id))


class FakeCandidateRepo:
    def __init__(self, events: list[tuple[str, object]], candidate: StagedCandidate | None) -> None:
        self._by_id: dict[UUID, StagedCandidate] = {candidate.id: candidate} if candidate else {}
        self.decisions: list[CandidateDecision] = []
        self._events = events
        self.set_status_boom = False

    async def get(self, candidate_id: UUID) -> StagedCandidate | None:
        return self._by_id.get(candidate_id)

    async def insert_decision(self, decision: CandidateDecision) -> None:
        self.decisions.append(decision)
        self._events.append(("decision", decision.id))

    async def set_status(self, candidate_id: UUID, status: CandidateStatus) -> None:
        if self.set_status_boom:
            raise RuntimeError("crash before flip")
        self._by_id[candidate_id].status = status
        self._events.append(("status", status))


def _service(
    candidate: StagedCandidate | None, *, existing: set[UUID] | None = None
) -> tuple[CandidateReviewService, FakeGraph, FakeMentions, FakeCandidateRepo, list]:
    events: list[tuple[str, object]] = []
    graph = FakeGraph(events, existing=existing)
    mentions = FakeMentions(events)
    repo = FakeCandidateRepo(events, candidate)
    return CandidateReviewService(graph, repo, mentions), graph, mentions, repo, events


# --- accept-create ---------------------------------------------------------


async def test_accept_create_writes_in_order_status_last() -> None:
    candidate = _candidate(proposal="new")
    service, graph, mentions, repo, events = _service(candidate)

    result = await service.accept(candidate.id, language=LANG)

    assert result.status == "created"
    assert len(graph.entities) == 1
    assert len(mentions.mentions) == 1
    assert mentions.mentions[0].entity_id == result.entity_id
    assert mentions.mentions[0].embedding == candidate.context_embedding
    assert len(repo.decisions) == 1
    # The status flip is the LAST write — Neo4j → mention → evidence → status.
    assert [kind for kind, _ in events] == ["entity", "mention", "decision", "status"]


async def test_accept_create_is_idempotent_on_retry_before_flip() -> None:
    # Simulate a crash before the status flip: status stays review-queued, so a retry re-runs.
    # The entity id is deterministic, so the re-create is a no-op — no duplicate node.
    candidate = _candidate(proposal="new")
    service, graph, _, repo, _ = _service(candidate)
    repo.set_status_boom = True

    with pytest.raises(RuntimeError):
        await service.accept(candidate.id, language=LANG)
    assert candidate.status == "review-queued"  # never flipped

    repo.set_status_boom = False
    result = await service.accept(candidate.id, language=LANG)  # retry succeeds
    assert result.status == "created"
    assert len(graph.entities) == 1  # still one node — deterministic id, idempotent create


async def test_reaccept_after_success_is_a_noop() -> None:
    candidate = _candidate(proposal="new")
    service, graph, _, _, _ = _service(candidate)

    await service.accept(candidate.id, language=LANG)
    second = await service.accept(candidate.id, language=LANG)

    assert second.already_decided is True
    assert second.status == "created"
    assert len(graph.entities) == 1  # no second node


# --- accept-merge ----------------------------------------------------------


async def test_accept_merge_aliases_the_target() -> None:
    target = uuid4()
    candidate = _candidate(proposal="merge", target=target)
    service, graph, mentions, repo, events = _service(candidate, existing={target})

    result = await service.accept(candidate.id, language=LANG)

    assert result.status == "merged"
    assert result.entity_id == target
    assert graph.aliases == [(target, "Bronek")]
    assert graph.entities == {}  # merge writes no new node
    assert mentions.mentions[0].entity_id == target
    assert [kind for kind, _ in events] == ["alias", "mention", "decision", "status"]


async def test_accept_merge_stale_target_409_without_writes() -> None:
    target = uuid4()
    candidate = _candidate(proposal="merge", target=target)
    service, graph, mentions, repo, _ = _service(candidate, existing=set())  # target absent

    with pytest.raises(StaleMergeTarget):
        await service.accept(candidate.id, language=LANG)

    assert graph.aliases == [] and mentions.mentions == [] and repo.decisions == []
    assert candidate.status == "review-queued"  # nothing committed


async def test_accept_can_override_proposal_to_create() -> None:
    # The reviewer rejects the cascade's merge proposal and creates a new entity instead.
    target = uuid4()
    candidate = _candidate(proposal="merge", target=target)
    service, graph, _, _, _ = _service(candidate, existing={target})

    result = await service.accept(candidate.id, language=LANG, action="create", custom_type="Deity")

    assert result.status == "created"
    assert len(graph.entities) == 1
    assert next(iter(graph.entities.values())).type == "Deity"


# --- reject ----------------------------------------------------------------


async def test_reject_records_evidence_and_writes_no_graph() -> None:
    candidate = _candidate(proposal="new")
    service, graph, mentions, repo, events = _service(candidate)

    result = await service.reject(candidate.id)

    assert result.status == "rejected"
    assert graph.entities == {} and graph.aliases == [] and mentions.mentions == []
    assert repo.decisions[0].decision == "rejected"
    assert [kind for kind, _ in events] == ["decision", "status"]


# --- not found -------------------------------------------------------------


async def test_accept_unknown_candidate_raises() -> None:
    service, *_ = _service(None)
    with pytest.raises(CandidateNotFound):
        await service.accept(uuid4(), language=LANG)


async def test_reject_unknown_candidate_raises() -> None:
    service, *_ = _service(None)
    with pytest.raises(CandidateNotFound):
        await service.reject(uuid4())
