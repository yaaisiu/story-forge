"""Neo4j repository for the knowledge graph (spec §3.2 / §6.4 / §9 Milestone 2).

Writes extracted entities and relations as graph nodes/edges. Through Milestone 2
this is **no-dedupe**: every entity is written with `CREATE` (never `MERGE`), so two
identical candidates become two distinct nodes — the deliberately temporary INV-8
contract that exposes the duplicate problem M3's cascade then solves. A `MERGE`-on-name
here would silently violate that invariant, so the keyword choice is load-bearing.

Mapping notes (domain `GraphEntity`/`GraphRelation` ↔ Neo4j):
- **UUIDs** have no native Neo4j type — stored as strings, parsed back on read.
- **`properties`** is free-form JSON (§3.2); Neo4j node/relationship properties cannot
  hold a nested map, so it is serialised to a `properties_json` string and parsed back.
- **`aliases`** is a native Neo4j string list (queryable, and it is flat).
- **Nullable fields** (`canonical_name_*`, `first_seen_paragraph_id`, `world_id`) are
  passed as `None`; Neo4j drops a property set to null, and `.get()` restores it on read.
- **Relationship type** is open-world (INV-4) and cannot be parameterised in Cypher, so
  it is interpolated — backtick-quoted with embedded backticks doubled, so an untrusted
  (LLM-produced) type cannot break out of the quoting. This is the Cypher analogue of the
  prompt-injection-by-structure discipline; everything else is a bound parameter.

Connection config comes from the existing M0 `.env` keys (`settings.neo4j_*`).
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from neo4j import AsyncDriver, AsyncGraphDatabase, Record

from story_forge.domain.graph import GraphEntity, GraphRelation


def _opt_str(value: UUID | None) -> str | None:
    return str(value) if value is not None else None


def _opt_uuid(value: object) -> UUID | None:
    return UUID(value) if isinstance(value, str) else None


def _escape_rel_type(rel_type: str) -> str:
    """Backtick-quote a relationship type so an arbitrary string is injection-safe.

    Cypher can't bind a relationship type as a parameter, so the type is interpolated.
    Wrapping it in backticks and doubling any embedded backtick means an untrusted type
    cannot terminate the quoting and inject Cypher (cf. prompt-injection-by-structure).
    """
    return "`" + rel_type.replace("`", "``") + "`"


class Neo4jRepo:
    """Async Neo4j graph writer/reader. One per process; share across requests."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    @classmethod
    async def connect(cls, *, uri: str, user: str, password: str) -> Neo4jRepo:
        driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        # Fail fast with a clear error if the server is unreachable, rather than on
        # the first query deep inside a write.
        await driver.verify_connectivity()
        return cls(driver)

    async def close(self) -> None:
        await self._driver.close()

    # --- Entities ----------------------------------------------------------

    async def create_entity(self, entity: GraphEntity) -> None:
        """Write a fresh entity node. `CREATE`, never `MERGE` — no dedupe (INV-8)."""
        await self._driver.execute_query(
            "CREATE (e:Entity $props)",
            props={
                "id": str(entity.id),
                "type": entity.type,
                "canonical_name_pl": entity.canonical_name_pl,
                "canonical_name_en": entity.canonical_name_en,
                "aliases": entity.aliases,
                "properties_json": json.dumps(entity.properties, ensure_ascii=False),
                "first_seen_paragraph_id": _opt_str(entity.first_seen_paragraph_id),
                "project_id": str(entity.project_id),
                "world_id": _opt_str(entity.world_id),
            },
        )

    async def get_entity(self, entity_id: UUID) -> GraphEntity | None:
        records, _, _ = await self._driver.execute_query(
            "MATCH (e:Entity {id: $id}) RETURN properties(e) AS props",
            id=str(entity_id),
        )
        if not records:
            return None
        return self._to_entity(dict(records[0]["props"]))

    async def list_entities(self, project_id: UUID) -> list[GraphEntity]:
        """Every entity node for a project (the graph viewer read path, §3.4)."""
        records, _, _ = await self._driver.execute_query(
            "MATCH (e:Entity {project_id: $pid}) RETURN properties(e) AS props",
            pid=str(project_id),
        )
        return [self._to_entity(dict(record["props"])) for record in records]

    async def count_entities(self, project_id: UUID) -> int:
        records, _, _ = await self._driver.execute_query(
            "MATCH (e:Entity {project_id: $pid}) RETURN count(e) AS n",
            pid=str(project_id),
        )
        return int(records[0]["n"])

    # --- Relations ---------------------------------------------------------

    async def create_relation(self, relation: GraphRelation) -> None:
        """Link two existing entities with a fresh, open-world-typed edge.

        Only endpoints that exist are matched, so a dangling relation (an endpoint
        no node satisfies) simply writes no edge — accepted at M2 (open-world; M3 +
        human review resolve dangling endpoints).
        """
        await self._driver.execute_query(
            f"MATCH (s:Entity {{id: $sid}}), (o:Entity {{id: $oid}}) "
            f"CREATE (s)-[r:{_escape_rel_type(relation.type)}]->(o) SET r = $props",
            sid=str(relation.subject_id),
            oid=str(relation.object_id),
            props={
                "id": str(relation.id),
                "confidence": relation.confidence,
                "source_paragraph_id": _opt_str(relation.source_paragraph_id),
                "properties_json": json.dumps(relation.properties, ensure_ascii=False),
            },
        )

    async def get_relations(self, project_id: UUID) -> list[GraphRelation]:
        records, _, _ = await self._driver.execute_query(
            "MATCH (s:Entity {project_id: $pid})-[r]->(o:Entity {project_id: $pid}) "
            "RETURN type(r) AS type, properties(r) AS props, s.id AS sid, o.id AS oid",
            pid=str(project_id),
        )
        return [self._to_relation(record) for record in records]

    # --- Maintenance -------------------------------------------------------

    async def delete_project_graph(self, project_id: UUID) -> None:
        """Remove a project's entities and their relationships (reversibility, INV-3)."""
        await self._driver.execute_query(
            "MATCH (e:Entity {project_id: $pid}) DETACH DELETE e",
            pid=str(project_id),
        )

    # --- Row → model -------------------------------------------------------

    def _to_entity(self, props: dict[str, Any]) -> GraphEntity:
        return GraphEntity(
            id=UUID(props["id"]),
            type=props["type"],
            canonical_name_pl=props.get("canonical_name_pl"),
            canonical_name_en=props.get("canonical_name_en"),
            aliases=list(props.get("aliases", [])),
            properties=json.loads(props["properties_json"]),
            first_seen_paragraph_id=_opt_uuid(props.get("first_seen_paragraph_id")),
            embedding=props.get("embedding"),
            project_id=UUID(props["project_id"]),
            world_id=_opt_uuid(props.get("world_id")),
        )

    def _to_relation(self, record: Record) -> GraphRelation:
        props = dict(record["props"])
        return GraphRelation(
            id=UUID(props["id"]),
            type=record["type"],
            subject_id=UUID(record["sid"]),
            object_id=UUID(record["oid"]),
            confidence=props["confidence"],
            source_paragraph_id=_opt_uuid(props.get("source_paragraph_id")),
            properties=json.loads(props["properties_json"]),
        )
