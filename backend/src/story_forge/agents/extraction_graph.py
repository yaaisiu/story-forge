"""Pure mapping: one paragraph's `ExtractionProposal` → persistable graph shapes.

The seam between extraction output (agent layer) and the knowledge graph
(`domain.graph`) + the cross-store mentions (`domain.models`). No I/O — a proposal
plus paragraph context in, the `GraphEntity` / `GraphRelation` / `EntityMention`
objects to persist out. Persistence (Neo4j + Postgres) is the caller's job; this
function holds only the M2 modelling rules, which keeps them unit-testable without a
database:

- **Provisional naming.** At M2 we have a surface mention, not a resolved bilingual
  name, so the surface form fills the *project-language* canonical slot and the other
  peer stays null. Real PL/EN canonical naming is assigned at M3 merge (§3.2).
- **No dedupe (INV-8).** Every candidate becomes a *fresh* `GraphEntity` (new id);
  two identical surface forms produce two nodes. The deliberately temporary contract
  that exposes the duplicate problem M3's cascade solves.
- **Within-paragraph relation resolution.** A relation's surface endpoints are
  resolved against *this paragraph's* candidates only; an endpoint named nowhere here
  is dangling and its edge is dropped (cross-paragraph / known-entity resolution and
  the surviving dangling links are M3 + human review).

This lives in the agent layer (not `domain/`) because it depends on the agent-owned
`ExtractionProposal` schema; it imports only that and the lower domain layer, never a
concrete adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from story_forge.agents.extraction_agent import ExtractionProposal
from story_forge.domain.graph import GraphEntity, GraphRelation
from story_forge.domain.models import EntityMention


@dataclass(frozen=True)
class ProposalGraph:
    """The persistable result of mapping one paragraph's proposal.

    Ordered for the OQ-1 write sequence: entities (Neo4j) and their mentions
    (Postgres) first, then relations (Neo4j), which reference the entity ids.
    """

    entities: list[GraphEntity]
    relations: list[GraphRelation]
    mentions: list[EntityMention]


def proposal_to_graph(
    proposal: ExtractionProposal,
    *,
    project_id: UUID,
    paragraph_id: UUID,
    language: str,
) -> ProposalGraph:
    """Map a single paragraph's `ExtractionProposal` to graph + mention shapes."""
    entities: list[GraphEntity] = []
    mentions: list[EntityMention] = []
    # Surface form → the node id created for it, for within-paragraph relation
    # resolution. With no dedupe, a repeated surface form overwrites (last wins);
    # the ambiguity is acceptable at M2 — resolving identity is exactly M3's job.
    by_name: dict[str, UUID] = {}

    for candidate in proposal.entities:
        pl = candidate.candidate_name if language == "pl" else None
        # Anything not "pl" fills the EN slot; M2 projects are PL or EN (bilingual
        # peer naming is M3), so a non-PL language is treated as EN here.
        en = candidate.candidate_name if language != "pl" else None
        entity = GraphEntity(
            type=candidate.type,
            canonical_name_pl=pl,
            canonical_name_en=en,
            properties=candidate.properties,
            first_seen_paragraph_id=paragraph_id,
            project_id=project_id,
        )
        entities.append(entity)
        # No reliable per-mention offsets/confidence from the LLM path (it yields an
        # evidence quote, not character spans) — leave them null per the migration.
        mentions.append(EntityMention(paragraph_id=paragraph_id, entity_id=entity.id))
        by_name[candidate.candidate_name] = entity.id

    relations: list[GraphRelation] = []
    for relation in proposal.relations:
        subject_id = by_name.get(relation.subject)
        object_id = by_name.get(relation.object)
        if subject_id is None or object_id is None:
            continue  # dangling endpoint — not a candidate here; M3 resolves it
        relations.append(
            GraphRelation(
                type=relation.predicate,
                subject_id=subject_id,
                object_id=object_id,
                confidence=relation.confidence,
                source_paragraph_id=paragraph_id,
            )
        )

    return ProposalGraph(entities=entities, relations=relations, mentions=mentions)
