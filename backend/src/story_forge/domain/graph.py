"""Knowledge-graph domain models (spec §3.2 / §6.4 — the Neo4j side).

These are the *persisted* graph shapes, deliberately distinct from the agent's
extraction-time `EntityCandidate` / `RelationCandidate` (which carry a surface
`candidate_name`, no id, no resolved bilingual name). A candidate becomes a
`GraphEntity` at write time (M2.S4); resolving the bilingual `canonical_name`
and merging duplicates is M3's job — through Milestone 2 every candidate is
written as a fresh node with no dedupe (INV-8).

Pure Pydantic, no persistence concerns: the Neo4j adapter (`adapters/neo4j_repo`)
maps these onto nodes/relationships. IDs are app-generated UUIDs, stable across
the Postgres/Neo4j split (a paragraph id from Postgres is referenced here as
`first_seen_paragraph_id` / `source_paragraph_id`).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class GraphEntity(BaseModel):
    """An entity node in the knowledge graph (spec §3.2, §6.4 `(:Entity {...})`).

    `canonical_name_pl` / `canonical_name_en` are nullable: at M2 write time we may
    only have a surface form in the project's language, and the resolved bilingual
    pair is assigned at M3 merge. `embedding` stays None until M3's matching pass
    fills it. `properties` is free-form JSON (§3.2) — the adapter serialises it,
    since Neo4j node properties cannot hold a nested map.
    """

    id: UUID = Field(default_factory=uuid4)
    type: str  # open-world, free string — never an enum (INV-4)
    canonical_name_pl: str | None = None
    canonical_name_en: str | None = None
    aliases: list[str] = Field(default_factory=list)
    properties: dict[str, object] = Field(default_factory=dict)
    first_seen_paragraph_id: UUID | None = None
    embedding: list[float] | None = None  # M3 fills it
    project_id: UUID

    @field_validator("type")
    @classmethod
    def _type_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("entity type must be a non-empty string")
        return value


class GraphRelation(BaseModel):
    """A typed, directed edge between two entities (spec §6.4 `[:RELATION_TYPE {...}]`).

    `type` is open-world (INV-4) and becomes the Neo4j relationship type. `subject_id`
    / `object_id` reference `GraphEntity.id`s. The edge may be *dangling* at the domain
    level (an endpoint that no node satisfies); the adapter's `CREATE` only links
    endpoints that exist, so a dangling write simply persists no edge.
    """

    id: UUID = Field(default_factory=uuid4)
    type: str
    subject_id: UUID
    object_id: UUID
    confidence: float = Field(ge=0.0, le=1.0)
    source_paragraph_id: UUID | None = None
    properties: dict[str, object] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def _type_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("relation type must be a non-empty string")
        return value
