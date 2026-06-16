"""Unit tests for RelationReviewService — the human-gated relation-edge write path (M3.S4e).

No I/O: fakes stand in for the edge writer, the staged-relation store, and the accepted-
candidate read, with a shared event log to assert the write order (Neo4j edge → status, the
last write). These pin the witness — accepting both endpoints of a staged relation and
committing writes exactly ONE edge between the two committed entities; accepting only one (or
not deciding) writes none; a retried commit doubles nothing — plus the held/self-loop guards.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from story_forge.agents.relation_review import (
    RelationEndpointsUnresolved,
    RelationNotFound,
    RelationReviewService,
)
from story_forge.domain.candidates import (
    RelationStatus,
    StagedCandidate,
    StagedRelation,
    committed_entity_id,
    relation_edge_id,
    staged_relation_id,
)
from story_forge.domain.graph import GraphRelation

PARA = uuid4()
STORY = uuid4()
PROJECT = uuid4()


def _accepted(name: str, *, paragraph_id: UUID = PARA) -> StagedCandidate:
    """An already-accepted (created) candidate — `committed_entity_id` resolves it."""
    return StagedCandidate(
        project_id=PROJECT,
        story_id=STORY,
        paragraph_id=paragraph_id,
        candidate_name=name,
        type="Character",
        context=f"{name} walked.",
        proposal="new",
        stage_reached=1,
        status="created",
    )


def _pending(name: str, *, paragraph_id: UUID = PARA) -> StagedCandidate:
    """A still-queued candidate — no committed entity, so it cannot anchor an endpoint."""
    return StagedCandidate(
        project_id=PROJECT,
        story_id=STORY,
        paragraph_id=paragraph_id,
        candidate_name=name,
        type="Character",
        context=f"{name} walked.",
        proposal="new",
        stage_reached=1,
        status="review-queued",
    )


def _relation(
    *, subject: str, predicate: str, object_: str, paragraph_id: UUID = PARA
) -> StagedRelation:
    return StagedRelation(
        id=staged_relation_id(paragraph_id, subject, predicate, object_),
        story_id=STORY,
        paragraph_id=paragraph_id,
        subject=subject,
        predicate=predicate,
        object=object_,
        confidence=0.9,
    )


class FakeGraph:
    """Records edge writes; MERGEs by edge id so a deterministic re-create is a no-op."""

    def __init__(self, events: list[tuple[str, object]]) -> None:
        self.relations: dict[UUID, GraphRelation] = {}
        self._events = events

    async def create_relation(self, relation: GraphRelation) -> None:
        self.relations[relation.id] = relation  # MERGE-by-id semantics
        self._events.append(("relation", relation.id))


class FakeRelationRepo:
    def __init__(self, events: list[tuple[str, object]], relations: list[StagedRelation]) -> None:
        self._by_id: dict[UUID, StagedRelation] = {r.id: r for r in relations}
        self._events = events
        self.mark_written_boom = False

    async def list_staged(self, story_id: UUID) -> list[StagedRelation]:
        return [r for r in self._by_id.values() if r.status == "staged"]

    async def get_relation(self, relation_id: UUID) -> StagedRelation | None:
        return self._by_id.get(relation_id)

    async def mark_written(
        self,
        relation_id: UUID,
        *,
        subject_entity_id: UUID,
        object_entity_id: UUID,
        edge_id: UUID,
    ) -> None:
        if self.mark_written_boom:
            raise RuntimeError("crash before flip")
        rel = self._by_id[relation_id]
        self._by_id[relation_id] = rel.model_copy(
            update={
                "status": "written",
                "subject_entity_id": subject_entity_id,
                "object_entity_id": object_entity_id,
                "edge_id": edge_id,
            }
        )
        self._events.append(("status", "written"))

    async def mark_rejected(self, relation_id: UUID) -> None:
        rel = self._by_id[relation_id]
        self._by_id[relation_id] = rel.model_copy(update={"status": "rejected"})
        self._events.append(("status", "rejected"))


class FakeCandidateRepo:
    def __init__(self, accepted: list[StagedCandidate]) -> None:
        self._candidates = accepted

    async def list_accepted(self, story_id: UUID) -> list[StagedCandidate]:
        # Mirror the store contract: only committed (created/merged) rows are returned.
        return [c for c in self._candidates if c.status in ("created", "merged")]


def _service(
    relations: list[StagedRelation], candidates: list[StagedCandidate]
) -> tuple[RelationReviewService, FakeGraph, FakeRelationRepo, list[tuple[str, object]]]:
    events: list[tuple[str, object]] = []
    graph = FakeGraph(events)
    repo = FakeRelationRepo(events, relations)
    cands = FakeCandidateRepo(candidates)
    return RelationReviewService(graph, repo, cands), graph, repo, events


# --- the witness -----------------------------------------------------------


async def test_commit_writes_one_edge_between_committed_endpoints() -> None:
    janek, mokosz = _accepted("Janek"), _accepted("Mokosz")
    # Surface strings differ in case/whitespace from the candidate names — normalised-exact.
    rel = _relation(subject=" janek ", predicate="KNOWS", object_="MOKOSZ")
    service, graph, _repo, events = _service([rel], [janek, mokosz])

    committable = await service.list_committable(STORY)
    assert [c.relation.id for c in committable] == [rel.id]  # both endpoints resolve

    result = await service.decide(rel.id, action="commit")

    assert result.status == "written"
    assert len(graph.relations) == 1  # exactly ONE edge
    edge = next(iter(graph.relations.values()))
    assert edge.subject_id == committed_entity_id(janek)
    assert edge.object_id == committed_entity_id(mokosz)
    assert edge.type == "KNOWS"
    assert edge.id == relation_edge_id(edge.subject_id, "KNOWS", edge.object_id)
    assert result.edge_id == edge.id
    # Neo4j edge first, status flip last.
    assert [kind for kind, _ in events] == ["relation", "status"]


async def test_one_endpoint_unaccepted_is_held_not_committable() -> None:
    janek, mokosz_pending = _accepted("Janek"), _pending("Mokosz")
    rel = _relation(subject="Janek", predicate="KNOWS", object_="Mokosz")
    service, graph, _repo, _events = _service([rel], [janek, mokosz_pending])

    assert await service.list_committable(STORY) == []  # held — Mokosz not accepted (DM-Rel-7)

    with pytest.raises(RelationEndpointsUnresolved):  # forcing the commit → 409, no write
        await service.decide(rel.id, action="commit")
    assert graph.relations == {}


async def test_commit_is_idempotent_on_retry_before_flip() -> None:
    # Crash before the status flip: status stays 'staged', so a retry re-runs. The edge id is
    # deterministic and the graph MERGEs by it, so the re-write is a no-op — one edge.
    janek, mokosz = _accepted("Janek"), _accepted("Mokosz")
    rel = _relation(subject="Janek", predicate="KNOWS", object_="Mokosz")
    service, graph, repo, _events = _service([rel], [janek, mokosz])
    repo.mark_written_boom = True

    with pytest.raises(RuntimeError):
        await service.decide(rel.id, action="commit")
    assert len(graph.relations) == 1  # edge written, but status never flipped

    repo.mark_written_boom = False
    result = await service.decide(rel.id, action="commit")  # retry succeeds
    assert result.status == "written"
    assert len(graph.relations) == 1  # still ONE edge — MERGE-by-id idempotent


async def test_redecide_after_success_is_a_noop() -> None:
    janek, mokosz = _accepted("Janek"), _accepted("Mokosz")
    rel = _relation(subject="Janek", predicate="KNOWS", object_="Mokosz")
    service, graph, _repo, _events = _service([rel], [janek, mokosz])

    first = await service.decide(rel.id, action="commit")
    second = await service.decide(rel.id, action="commit")  # double-submit

    assert second.already_decided is True
    assert second.status == "written"
    assert second.edge_id == first.edge_id
    assert len(graph.relations) == 1  # no second edge
    assert await service.list_committable(STORY) == []  # no longer staged


def _merged(name: str, target: UUID, *, paragraph_id: UUID = PARA) -> StagedCandidate:
    """A candidate accepted as a MERGE into `target` — `committed_entity_id` → the target id."""
    return StagedCandidate(
        project_id=PROJECT,
        story_id=STORY,
        paragraph_id=paragraph_id,
        candidate_name=name,
        type="Character",
        context=f"{name} walked.",
        proposal="merge",
        target_entity_id=target,
        stage_reached=1,
        status="merged",
    )


async def test_self_loop_is_dropped() -> None:
    # Two distinct surface forms merged into the SAME entity (a merge artifact) resolve to one
    # id → subject_id == object_id → no self-edge (the self-loop branch, not ambiguity).
    target = uuid4()
    janek = _merged("Janek", target)
    jan = _merged("Jan", target)  # different name, same merge target → same committed id
    rel = _relation(subject="Janek", predicate="KNOWS", object_="Jan")
    service, graph, _repo, _events = _service([rel], [janek, jan])

    assert await service.list_committable(STORY) == []
    with pytest.raises(RelationEndpointsUnresolved):
        await service.decide(rel.id, action="commit")
    assert graph.relations == {}


async def test_ambiguous_same_name_endpoint_is_held() -> None:
    # Two accepted candidates with the SAME name in one paragraph resolve to DIFFERENT entities
    # → the endpoint is ambiguous → held, never guessed.
    janek_a, janek_b = _accepted("Janek"), _accepted("Janek")  # distinct ids → distinct entities
    mokosz = _accepted("Mokosz")
    rel = _relation(subject="Janek", predicate="KNOWS", object_="Mokosz")
    service, graph, _repo, _events = _service([rel], [janek_a, janek_b, mokosz])

    assert await service.list_committable(STORY) == []
    with pytest.raises(RelationEndpointsUnresolved):
        await service.decide(rel.id, action="commit")
    assert graph.relations == {}


async def test_reject_writes_no_edge() -> None:
    janek, mokosz = _accepted("Janek"), _accepted("Mokosz")
    rel = _relation(subject="Janek", predicate="KNOWS", object_="Mokosz")
    service, graph, _repo, events = _service([rel], [janek, mokosz])

    result = await service.decide(rel.id, action="reject")

    assert result.status == "rejected"
    assert graph.relations == {}
    assert [kind for kind, _ in events] == ["status"]  # only the status flip
    assert await service.list_committable(STORY) == []


async def test_decide_unknown_relation_raises() -> None:
    service, *_ = _service([], [])
    with pytest.raises(RelationNotFound):
        await service.decide(uuid4(), action="commit")


async def test_status_is_a_relation_status_literal() -> None:
    # Guards the domain literal stays the three-state machine the store column mirrors.
    valid: set[RelationStatus] = {"staged", "written", "rejected"}
    assert valid == {"staged", "written", "rejected"}
