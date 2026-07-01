"""Unit tests for `enrich_candidate_view` — the pure merge-verification projection (S3, DM-EE-3).

No DB/Neo4j: the caller resolves the entity + quote lookups; this proves the pure mapping — the
target name resolved from the merge target, each alternative's type/aliases/sample quote, and the
graceful fallbacks when an id is absent from a lookup (missing entity, missing quote).
"""

from __future__ import annotations

from uuid import uuid4

from story_forge.api.stories import enrich_candidate_view
from story_forge.domain.candidates import StagedCandidate
from story_forge.domain.graph import GraphEntity


def _candidate(*, target_entity_id=None, alternatives=None) -> StagedCandidate:
    return StagedCandidate(
        project_id=uuid4(),
        story_id=uuid4(),
        paragraph_id=uuid4(),
        candidate_name="Janek",
        type="Character",
        context="Janek walked.",
        proposal="merge" if target_entity_id else "new",
        target_entity_id=target_entity_id,
        stage_reached=1,
        alternatives=alternatives or [],
    )


def _entity(entity_id, *, name, type_="Character", aliases=None) -> GraphEntity:
    return GraphEntity(
        id=entity_id,
        type=type_,
        canonical_name_pl=name,
        aliases=aliases or [],
        project_id=uuid4(),
    )


def test_target_canonical_name_resolved_from_the_merge_target() -> None:
    target_id = uuid4()
    candidate = _candidate(target_entity_id=target_id)
    entities = {str(target_id): _entity(target_id, name="Janusz")}

    view = enrich_candidate_view(candidate, entities, {}, language="pl")

    assert view.target_canonical_name == "Janusz"
    assert view.target_entity_id == target_id


def test_target_name_none_when_target_absent_from_graph() -> None:
    candidate = _candidate(target_entity_id=uuid4())
    view = enrich_candidate_view(candidate, {}, {}, language="pl")
    assert view.target_canonical_name is None


def test_no_target_leaves_name_none() -> None:
    view = enrich_candidate_view(_candidate(), {}, {}, language="pl")
    assert view.target_canonical_name is None


def test_alternative_enriched_with_type_aliases_and_sample_quote() -> None:
    alt_id = uuid4()
    candidate = _candidate(
        alternatives=[{"entity_id": str(alt_id), "canonical_name": "Janek", "score": 100.0}]
    )
    entities = {str(alt_id): _entity(alt_id, name="Janek", type_="Character", aliases=["Jaś"])}
    quotes = {str(alt_id): ["Janek came home late.", "second quote (ignored)"]}

    view = enrich_candidate_view(candidate, entities, quotes, language="pl")

    (alt,) = view.alternatives
    assert alt.entity_id == alt_id
    assert alt.canonical_name == "Janek"
    assert alt.score == 100.0
    assert alt.type == "Character"
    assert alt.aliases == ["Jaś"]
    assert alt.context_quote == "Janek came home late."  # the first sample only


def test_alternative_missing_entity_and_quote_falls_back() -> None:
    alt_id = uuid4()
    candidate = _candidate(
        alternatives=[{"entity_id": str(alt_id), "canonical_name": "Ghost", "score": 42.0}]
    )
    # entity absent from the graph read, no quote surfaced.
    view = enrich_candidate_view(candidate, {}, {}, language="pl")

    (alt,) = view.alternatives
    assert alt.type is None
    assert alt.aliases == []
    assert alt.context_quote is None
    assert alt.canonical_name == "Ghost"  # the stored name still renders
