"""1-hop neighbourhood (ego-graph) assembly for the reader side panel (M4.S2a, spec §3.5).

A read-only projection of the accepted graph: given a focal entity and the relation edges
**incident to it** (each paired with the accepted entity on the far end), produce the
*ego-graph* — the focal node's direct neighbours plus the edges touching it, each classified
by direction (`out` = focal→neighbour, `in` = neighbour→focal). This is the "local graph
around that entity" the side panel renders (§3.5); strict 1-hop, entity-incident edges only
(DM-SP-2 — see `architecture/glossary/ego-graph.md`).

Pure and deterministic — no store, no model, no I/O (the layer the project unit-tests
hardest). The `Neo4jRepo.get_neighbourhood` 1-hop query feeds the incident (edge, neighbour)
pairs in; the side-panel endpoint (DM-SP-1a) wraps the result with the focal entity's details
+ properties.

Failure posture is **omit, don't guess** ([[fail-closed]]): a **self-loop** (an edge whose
two endpoints are the focal entity — a merge artifact, never a real "relates-to-itself") is
dropped rather than drawn `(e)-[r]->(e)`, and an edge not actually incident to the focal node
is skipped. A neighbour that was merged-away/rejected cannot appear here because the query
co-returns the node — but if one ever did, it is omitted, never drawn into the void
([[referential-integrity]]). Neighbours are de-duplicated by id (two edges to the same node —
"loves" *and* "betrays" — yield one neighbour, two edges).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from story_forge.domain.graph import GraphEntity, GraphRelation


class EgoNeighbour(BaseModel):
    """One directly-connected entity in the focal node's 1-hop neighbourhood (display subset).

    The same colour-by-type/name fields the §3.4 graph node carries, so the panel's mini-graph
    can render a neighbour without a second lookup. `type` is open-world (INV-4).
    """

    entity_id: UUID
    type: str
    canonical_name_pl: str | None = None
    canonical_name_en: str | None = None
    aliases: list[str] = Field(default_factory=list)


class EgoEdge(BaseModel):
    """One relation edge incident to the focal entity, oriented relative to it.

    `direction` is `out` when the focal entity is the relation's subject (focal→neighbour) and
    `in` when it is the object (neighbour→focal); `neighbour_id` is the entity on the far end.
    """

    id: UUID
    type: str
    direction: Literal["out", "in"]
    neighbour_id: UUID
    confidence: float


class EgoGraph(BaseModel):
    """The focal entity's 1-hop neighbourhood: its direct neighbours + the edges touching it."""

    neighbours: list[EgoNeighbour] = Field(default_factory=list)
    edges: list[EgoEdge] = Field(default_factory=list)


def build_ego_graph(focal_id: UUID, incident: list[tuple[GraphRelation, GraphEntity]]) -> EgoGraph:
    """Assemble the focal entity's 1-hop ego-graph from its incident (edge, neighbour) pairs.

    `incident` is every relation touching `focal_id` paired with the entity on the far end (as
    `Neo4jRepo.get_neighbourhood` returns). Drops self-loops and non-incident edges; de-dupes
    neighbours by id and edges by id; returns deterministically-ordered neighbours + edges.
    """
    neighbours: dict[UUID, EgoNeighbour] = {}
    edges: dict[UUID, EgoEdge] = {}
    for relation, neighbour in incident:
        # Direction relative to the focal node; an edge not incident to it is skipped (defensive).
        if relation.subject_id == focal_id:
            direction: Literal["out", "in"] = "out"
            far_id = relation.object_id
        elif relation.object_id == focal_id:
            direction = "in"
            far_id = relation.subject_id
        else:
            continue
        # Self-loop (both endpoints are the focal entity — a merge artifact): never a neighbour.
        if far_id == focal_id:
            continue
        # The co-returned node must be the far endpoint; a mismatch is omitted, not guessed.
        if neighbour.id != far_id:
            continue
        edges.setdefault(
            relation.id,
            EgoEdge(
                id=relation.id,
                type=relation.type,
                direction=direction,
                neighbour_id=far_id,
                confidence=relation.confidence,
            ),
        )
        neighbours.setdefault(
            neighbour.id,
            EgoNeighbour(
                entity_id=neighbour.id,
                type=neighbour.type,
                canonical_name_pl=neighbour.canonical_name_pl,
                canonical_name_en=neighbour.canonical_name_en,
                aliases=neighbour.aliases,
            ),
        )

    def _name(n: EgoNeighbour) -> str:
        return n.canonical_name_pl or n.canonical_name_en or ""

    ordered_neighbours = sorted(neighbours.values(), key=lambda n: (_name(n), str(n.entity_id)))
    ordered_edges = sorted(edges.values(), key=lambda e: (str(e.neighbour_id), e.type, str(e.id)))
    return EgoGraph(neighbours=ordered_neighbours, edges=ordered_edges)
