"""AcceptedEntityReader — reads the already-accepted graph the cascade matches against (M3.S4a).

The §3.3 cascade matches a new candidate against *accepted* entities only (Stage 1 names,
Stage 2 mention vectors, Stage 3 recent-mention context). This reader assembles that
`AcceptedSnapshot` in a single pass per ingest run — one Neo4j read for the entities, two
Postgres reads for their vectors and recent mention texts — so the cascade's per-candidate
work is pure in-memory compute (the C4 store-chatty mitigation: reads are batched, not fanned
out per candidate). It composes two adapters (`Neo4jRepo`, `postgres_repo`) and produces a
domain shape, so it stays free of any agent-layer import.
"""

from __future__ import annotations

from uuid import UUID

from story_forge.adapters import postgres_repo
from story_forge.adapters.db import connect, libpq_kwargs
from story_forge.adapters.neo4j_repo import Neo4jRepo
from story_forge.config import settings
from story_forge.domain.candidates import AcceptedSnapshot


class AcceptedEntityReader:
    """Assembles the `AcceptedSnapshot` for a project from Neo4j + Postgres, read once per run."""

    def __init__(self, neo4j_repo: Neo4jRepo, conninfo: dict[str, object] | None = None) -> None:
        self._neo4j = neo4j_repo
        self._conninfo = conninfo if conninfo is not None else libpq_kwargs(settings.database_url)

    async def load_accepted(self, project_id: UUID) -> AcceptedSnapshot:
        entities = await self._neo4j.list_entities(project_id)
        if not entities:
            return AcceptedSnapshot()
        entity_ids = [entity.id for entity in entities]
        async with await connect(self._conninfo, autocommit=True) as conn:
            mention_vectors = await postgres_repo.list_mention_vectors_for_entities(
                conn, entity_ids
            )
            recent_mentions = await postgres_repo.list_recent_mention_texts_for_entities(
                conn, entity_ids
            )
        return AcceptedSnapshot(
            entities=entities,
            mention_vectors=mention_vectors,
            recent_mentions=recent_mentions,
        )
