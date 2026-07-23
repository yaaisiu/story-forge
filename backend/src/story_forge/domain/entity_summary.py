"""Graph-derived relation summaries for the reader's hover tooltip (S7, spec §3.5).

Spec §3.5 has the reader's tooltip show, alongside an entity's name/type/aliases, a **summary
derived from the accepted graph**: up to three of its connections, ordered by the *neighbour's*
connection count so the structurally significant links surface rather than an accident of the
alphabet. Entities carry no stored `description` field and none is authored or LLM-generated —
this is computed at read time from edges the reader already loads.

**One line per distinct neighbour.** A pair of entities is often joined by several edges, and
ordering by degree alone let the single biggest hub take every slot — on the real Oakhaven graph
each entity's tooltip read "→ HUNTS Locke / ← CAUGHT Locke / ← POINTS_AT Locke", saying one thing
three times while hiding who else it touched. Where a pair has several edges one represents them,
and `overflow` counts unshown *neighbours*, so "+N more" means "N more connections".

Why a module of its own rather than an extension of `domain/neighbourhood.py`: `build_ego_graph`
summarises **one** focal entity from the per-entity `Neo4jRepo.get_neighbourhood` query. The
reader needs a summary for **every** entity in its tooltip catalog, so recomputing per entity
would rescan the edge list N times. This function takes the project's whole relation list once
(the same read `/graph` already does) and returns every entity's summary in a single pass.

Pure and deterministic — no store, no model, no I/O. The neighbour *names* are resolved by the
caller (naming is language-dependent and `canonical_for_language` lives in `agents/`, which
`domain/` must not import), so this module takes a plain id → name mapping.

Failure posture is **omit, don't guess** (the same rule `build_ego_graph` follows): a **self-loop**
is a merge artifact, never a real "relates to itself", so it is dropped; an edge whose far endpoint
cannot be *named* — absent from `names` because it was deleted or merged away, or present but
nameless (`GraphEntity` permits both canonical names to be None, which the caller resolves to "")
— is skipped rather than rendered into the void. And, so the ordering reflects only what the
reader can actually see, such an edge does not count toward any neighbour's connection count.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from story_forge.domain.graph import GraphRelation

DEFAULT_SUMMARY_LIMIT = 3


class RelationSummaryLine(BaseModel):
    """One relation as the tooltip renders it, oriented relative to the entity hovered.

    `direction` is `out` when the hovered entity is the relation's subject and `in` when it is
    the object — the frontend draws these as `→` / `←`. Structured rather than pre-rendered:
    presentation belongs to the frontend.
    """

    direction: Literal["out", "in"]
    predicate: str
    neighbour_name: str


class EntityRelationSummary(BaseModel):
    """An entity's tooltip summary: the kept lines plus how many *neighbours* were left out.

    `overflow` counts unshown **neighbours**, not unshown edges — one line represents one
    neighbour however many edges join the pair, so an entity with 3 neighbours and 30 edges
    reports `overflow=0`, not 27.
    """

    lines: list[RelationSummaryLine] = Field(default_factory=list)
    overflow: int = 0


def summarise_relations(
    relations: Sequence[GraphRelation],
    names: Mapping[UUID, str],
    limit: int = DEFAULT_SUMMARY_LIMIT,
    *,
    only: Collection[UUID] | None = None,
) -> dict[UUID, EntityRelationSummary]:
    """Summarise entities' relations for the reader tooltip, in one pass.

    `relations` is the project's whole edge list; `names` maps entity id → the display name the
    caller resolved. Returns a mapping of entity id → summary, containing an entry only for
    entities with at least one *visible* relation (an entity with none needs no summary).

    `only` narrows which entities get a summary built — the reader catalogues just the entities
    that actually appear in the prose, so building the rest is discarded work. It does **not**
    narrow the graph the ranking is computed over: degree is always counted across every visible
    edge, because a neighbour's significance comes from the whole graph, not from the subset
    being displayed.
    """
    # Keep only what the reader can actually see, de-duplicated by edge id (`GraphRelation.id`
    # is uuid5 of the triple, so the same triple read twice is one edge).
    visible: dict[UUID, GraphRelation] = {}
    for relation in relations:
        if relation.subject_id == relation.object_id:
            continue  # self-loop — a merge artifact, never a real neighbour
        # An endpoint we cannot *name* — omit rather than render into the void. Truthiness, not
        # key presence: `GraphEntity` permits both canonical names to be None, and the caller's
        # resolver returns "" for that entity, which would otherwise render "→ LIVES_IN " with a
        # blank after the predicate *and* count toward every other neighbour's rank.
        if not names.get(relation.subject_id) or not names.get(relation.object_id):
            continue
        visible.setdefault(relation.id, relation)

    # Connection count per entity = its number of **distinct neighbours**, over the *visible*
    # edges only. Counting incident *edges* here would contradict the one-line-per-neighbour
    # display below: a dead-end neighbour joined by four parallel edges would score 4 and outrank
    # a genuine hub joined to three different entities, which is precisely backwards from the
    # "most structurally significant links surface" the spec promises. An edge the reader can't
    # see must not make a neighbour look better-connected than it is either.
    neighbours_of: dict[UUID, set[UUID]] = {}
    for relation in visible.values():
        neighbours_of.setdefault(relation.subject_id, set()).add(relation.object_id)
        neighbours_of.setdefault(relation.object_id, set()).add(relation.subject_id)
    degree = {entity_id: len(peers) for entity_id, peers in neighbours_of.items()}

    # Each edge contributes a line to *both* its endpoints, oriented from each one's point of view.
    # **One line per distinct neighbour**: a pair can be joined by several edges, and spending all
    # three slots on one neighbour ("→ HUNTS Locke / ← CAUGHT Locke / ← POINTS_AT Locke") says one
    # thing three times while hiding who else the entity touches. Where a pair has several edges,
    # the alphabetically-first predicate represents it — arbitrary but deterministic.
    # The rank is a *tuple*, not a joined string: predicates are open-world free strings (INV-4),
    # and a separator-joined key over an unconstrained type has to defend its delimiter. Tuples
    # compare element-wise, so there is no separator to collide on.
    best: dict[UUID, dict[UUID, tuple[tuple[str, str], RelationSummaryLine]]] = {}
    for relation in visible.values():
        endpoints: tuple[tuple[UUID, UUID, Literal["out", "in"]], ...] = (
            (relation.subject_id, relation.object_id, "out"),
            (relation.object_id, relation.subject_id, "in"),
        )
        for focal_id, far_id, direction in endpoints:
            candidate = (
                (relation.type, str(relation.id)),
                RelationSummaryLine(
                    direction=direction,
                    predicate=relation.type,
                    neighbour_name=names[far_id],
                ),
            )
            by_neighbour = best.setdefault(focal_id, {})
            if far_id not in by_neighbour or candidate[0] < by_neighbour[far_id][0]:
                by_neighbour[far_id] = candidate

    # Order the neighbours: most-connected first (spec §3.5), then a deterministic tiebreak chain
    # (predicate → neighbour name → neighbour id) so the tooltip never reshuffles between reads.
    summaries: dict[UUID, EntityRelationSummary] = {}
    for entity_id, by_neighbour in best.items():
        if only is not None and entity_id not in only:
            continue
        ordered = sorted(
            by_neighbour.items(),
            key=lambda item: (
                -degree[item[0]],
                item[1][1].predicate,
                item[1][1].neighbour_name,
                str(item[0]),
            ),
        )
        summaries[entity_id] = EntityRelationSummary(
            lines=[line for _, (_, line) in ordered[:limit]],
            # Neighbours, not edges: with one line per neighbour, "+N more" means "N more
            # connections" rather than a misleading pile of hidden parallel edges.
            overflow=max(0, len(ordered) - limit),
        )
    return summaries
