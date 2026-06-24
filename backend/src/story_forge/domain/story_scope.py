"""Pure story-scope projection over a project's knowledge graph (M4 multi-story, DM-MS-1/2).

A project graph is shared across all its stories (spec §3.6); per-story *membership* is **derived,
not stored** — an entity belongs to a story iff it has an accepted mention whose paragraph rolls up
to that story (DM-MS-1). This module is the pure filter that turns the whole-project graph into the
"this story" subgraph the §3.4 toggle shows; the caller supplies the two derived sets (the member
entity-ids and the story's paragraph-ids), which an adapter rolls up from `entity_mentions` and the
document tree. No I/O here — the single most-testable altitude.
"""

from __future__ import annotations

from uuid import UUID

from story_forge.domain.graph import GraphEntity, GraphRelation


def filter_graph_to_story(
    entities: list[GraphEntity],
    relations: list[GraphRelation],
    member_entity_ids: set[UUID],
    story_paragraph_ids: set[UUID],
) -> tuple[list[GraphEntity], list[GraphRelation]]:
    """Project a whole-project graph down to one story's subgraph (DM-MS-2 edge rule).

    A node is kept iff it is a member of the story. An edge is kept iff **both** endpoints are
    members **and** it is asserted within the story — where "asserted within the story" means its
    ``source_paragraph_id`` is one of the story's paragraphs, *or* it has no source paragraph at all
    (a hand-added manual edge, which is story-agnostic and shown whenever both endpoints are
    members). The both-endpoints rule guarantees a self-contained subgraph with no dangling edges.
    """
    nodes = [e for e in entities if e.id in member_entity_ids]
    edges = [
        r
        for r in relations
        if r.subject_id in member_entity_ids
        and r.object_id in member_entity_ids
        and (r.source_paragraph_id is None or r.source_paragraph_id in story_paragraph_ids)
    ]
    return nodes, edges
