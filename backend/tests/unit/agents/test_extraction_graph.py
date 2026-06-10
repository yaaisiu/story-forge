"""Unit tests for the pure ExtractionProposal → graph mapping (M2.S4).

No I/O: a proposal + paragraph context in, the persistable `GraphEntity` /
`GraphRelation` / `EntityMention` shapes out. The mapping is where the M2 modelling
rules live — provisional `canonical_name` (surface form in the project language, the
other-language peer null — bilingual naming is M3), the no-dedupe property (INV-8:
every candidate becomes a fresh node), and within-paragraph relation resolution with
dangling endpoints dropped (M3 + human review resolve those).
"""

from __future__ import annotations

from uuid import uuid4

from story_forge.agents.extraction_agent import (
    EntityCandidate,
    ExtractionProposal,
    RelationCandidate,
)
from story_forge.agents.extraction_graph import proposal_to_graph


def _entity(name: str, type_: str = "Character", **kw: object) -> EntityCandidate:
    return EntityCandidate(candidate_name=name, type=type_, match_confidence=0.5, **kw)


def test_entity_maps_to_graph_entity_and_mention() -> None:
    project_id, paragraph_id = uuid4(), uuid4()
    proposal = ExtractionProposal(
        entities=[_entity("Janek", "Character", properties={"role": "hero"})]
    )
    graph = proposal_to_graph(
        proposal, project_id=project_id, paragraph_id=paragraph_id, language="pl"
    )

    assert len(graph.entities) == 1
    entity = graph.entities[0]
    assert entity.type == "Character"
    assert entity.project_id == project_id
    assert entity.first_seen_paragraph_id == paragraph_id
    assert entity.properties == {"role": "hero"}
    # Provisional canonical name: surface form in the project language, peer null.
    assert entity.canonical_name_pl == "Janek"
    assert entity.canonical_name_en is None

    # Every entity gets exactly one mention back-referencing the same node id.
    assert len(graph.mentions) == 1
    mention = graph.mentions[0]
    assert mention.entity_id == entity.id
    assert mention.paragraph_id == paragraph_id
    # The LLM path yields a quote, not offsets, so spans/confidence stay null.
    assert mention.span_start is None and mention.span_end is None
    assert mention.confidence is None


def test_english_project_fills_the_english_canonical_slot() -> None:
    proposal = ExtractionProposal(entities=[_entity("Janek")])
    graph = proposal_to_graph(proposal, project_id=uuid4(), paragraph_id=uuid4(), language="en")
    assert graph.entities[0].canonical_name_en == "Janek"
    assert graph.entities[0].canonical_name_pl is None


def test_no_dedupe_two_identical_candidates_become_two_entities() -> None:
    # INV-8: M2 writes every candidate as a fresh node. Two identical surface forms
    # in one paragraph produce two distinct entities (distinct ids), exposing the
    # duplicate problem M3 then solves.
    proposal = ExtractionProposal(entities=[_entity("Mokosz", "Deity"), _entity("Mokosz", "Deity")])
    graph = proposal_to_graph(proposal, project_id=uuid4(), paragraph_id=uuid4(), language="pl")
    assert len(graph.entities) == 2
    assert graph.entities[0].id != graph.entities[1].id
    assert len(graph.mentions) == 2


def test_relation_resolves_endpoints_to_this_paragraphs_entities() -> None:
    proposal = ExtractionProposal(
        entities=[_entity("Janek"), _entity("Mokosz", "Deity")],
        relations=[
            RelationCandidate(
                subject="Janek", predicate="WORSHIPS", object="Mokosz", confidence=0.9
            )
        ],
    )
    graph = proposal_to_graph(proposal, project_id=uuid4(), paragraph_id=uuid4(), language="pl")
    assert len(graph.relations) == 1
    relation = graph.relations[0]
    assert relation.type == "WORSHIPS"
    assert relation.confidence == 0.9
    by_name = {e.canonical_name_pl: e.id for e in graph.entities}
    assert relation.subject_id == by_name["Janek"]
    assert relation.object_id == by_name["Mokosz"]
    assert relation.source_paragraph_id is not None


def test_dangling_relation_endpoint_is_dropped() -> None:
    # An endpoint not named as a candidate in this paragraph can't be resolved to a
    # node id at M2 (cross-paragraph/known-entity resolution is M3). Drop the edge
    # rather than write a relation to a non-existent node.
    proposal = ExtractionProposal(
        entities=[_entity("Janek")],
        relations=[
            RelationCandidate(
                subject="Janek", predicate="SON_OF", object="Stary Bronek", confidence=0.5
            )
        ],
    )
    graph = proposal_to_graph(proposal, project_id=uuid4(), paragraph_id=uuid4(), language="pl")
    assert graph.entities  # the resolvable entity is still written
    assert graph.relations == []  # the dangling edge is dropped
