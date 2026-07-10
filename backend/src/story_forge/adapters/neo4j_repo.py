"""Neo4j repository for the knowledge graph (spec §3.2 / §6.4 / §9 Milestone 3).

Writes entities and relations as graph nodes/edges. Under M3 intercept-before-write (DM6,
ADR 0004) the graph is written **only by the human-accept path** (`CandidateReviewService`),
never by extraction (INV-9). `create_entity` is therefore an idempotent **upsert by id**
(`MERGE` on the unique `id`, a primary-key write) so a retried accept never doubles a node —
this is *not* a name-merge: folding two candidates into one entity is the human's review act,
done with `add_alias`. (This retires M2's temporary INV-8 "CREATE never MERGE" no-dedupe
contract — the graph no longer accumulates duplicates because nothing auto-writes it.)

Mapping notes (domain `GraphEntity`/`GraphRelation` ↔ Neo4j):
- **UUIDs** have no native Neo4j type — stored as strings, parsed back on read.
- **`properties`** is free-form JSON (§3.2); Neo4j node/relationship properties cannot
  hold a nested map, so it is serialised to a `properties_json` string and parsed back.
- **`aliases`** is a native Neo4j string list (queryable, and it is flat).
- **Nullable fields** (`canonical_name_*`, `first_seen_paragraph_id`) are
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
        """Write an entity node, idempotent by id (the human-accept create path, M3).

        `MERGE` on the unique `id` (a primary-key upsert) + `ON CREATE SET`, so a retried
        accept with the same (deterministic) id is a no-op rather than a second node. This is
        the idempotency half of the accept-path contract; the alias fold (`add_alias`) is the
        merge half. It is *not* a name-merge — INV-9 keeps all dedup decisions human.
        """
        await self._driver.execute_query(
            "MERGE (e:Entity {id: $props.id}) ON CREATE SET e = $props",
            props={
                "id": str(entity.id),
                "type": entity.type,
                "canonical_name_pl": entity.canonical_name_pl,
                "canonical_name_en": entity.canonical_name_en,
                "aliases": entity.aliases,
                "properties_json": json.dumps(entity.properties, ensure_ascii=False),
                "first_seen_paragraph_id": _opt_str(entity.first_seen_paragraph_id),
                "project_id": str(entity.project_id),
            },
        )

    async def add_alias(self, entity_id: UUID, alias: str) -> None:
        """Fold a candidate surface form into an existing entity as an alias (accept-merge).

        The merge half of the human-accept path: when the reviewer accepts a MERGE, the
        candidate's surface form is recorded as an alias of the chosen target. Idempotent —
        the list is de-duplicated, so a retried accept adds nothing twice. No-op if the target
        no longer exists (the review service re-validates the target first — the TOCTOU guard).
        """
        await self._driver.execute_query(
            "MATCH (e:Entity {id: $id}) "
            "SET e.aliases = CASE WHEN $alias IN coalesce(e.aliases, []) "
            "THEN coalesce(e.aliases, []) ELSE coalesce(e.aliases, []) + [$alias] END",
            id=str(entity_id),
            alias=alias,
        )

    async def update_entity(self, entity: GraphEntity) -> None:
        """Re-SET an existing entity's editable fields (the human-edit path, M4.S3a, DM-S3a-1).

        `MATCH` (not `MERGE`) on the id, then `SET` the mutable display/properties fields, so a
        missing node is a no-op rather than a resurrection — the edit service re-reads via
        `get_entity` first (the TOCTOU guard) and 404s before calling this. `type` is a node
        *property* (not a label — see `create_entity`), so it is a plain SET. `properties` is
        re-serialised wholesale; clearing a `canonical_name_*` to `None` removes that property
        (Neo4j drops a null-valued property), which `get_entity`'s `.get()` restores as `None`.
        Idempotent: re-applying the same next-state writes the same values.
        """
        await self._driver.execute_query(
            "MATCH (e:Entity {id: $id}) "
            "SET e.type = $type, e.canonical_name_pl = $canonical_name_pl, "
            "e.canonical_name_en = $canonical_name_en, e.aliases = $aliases, "
            "e.properties_json = $properties_json",
            id=str(entity.id),
            type=entity.type,
            canonical_name_pl=entity.canonical_name_pl,
            canonical_name_en=entity.canonical_name_en,
            aliases=entity.aliases,
            properties_json=json.dumps(entity.properties, ensure_ascii=False),
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
        """Link two existing entities with an open-world-typed edge, idempotent by id (M3.S4e).

        `MERGE` on the deterministic edge `id` (a primary-key upsert) + `ON CREATE SET`, so a
        retried decide-relations commit is a no-op rather than a second parallel edge — the
        relation analogue of `create_entity`'s contract. Because the id is `uuid5` of the
        resolved (subject, predicate, object) triple (DM-Rel-6), the *same fact* stated in two
        paragraphs MERGEs to one edge. Only endpoints that exist are matched (`MATCH` first), so
        a dangling relation writes no edge — though the human gate never commits an unresolved
        endpoint, so dangling is the open-world safety net, not the expected path.
        """
        await self._driver.execute_query(
            f"MATCH (s:Entity {{id: $sid}}), (o:Entity {{id: $oid}}) "
            f"MERGE (s)-[r:{_escape_rel_type(relation.type)} {{id: $props.id}}]->(o) "
            f"ON CREATE SET r = $props",
            sid=str(relation.subject_id),
            oid=str(relation.object_id),
            props={
                "id": str(relation.id),
                "confidence": relation.confidence,
                "source_paragraph_id": _opt_str(relation.source_paragraph_id),
                "properties_json": json.dumps(relation.properties, ensure_ascii=False),
                # The §4 surrogate handle (ADR 0011). `ON CREATE SET` (no `ON MATCH`) *is* the
                # coalesce rule: a MERGE that matches an existing edge sets nothing, so an edge's
                # handle is never overwritten by a duplicate/retried write, and a re-key preserves
                # it by passing the old edge's `edge_uid` on the create (DM-S5-3).
                "edge_uid": _opt_str(relation.edge_uid),
            },
        )

    async def get_relations(self, project_id: UUID) -> list[GraphRelation]:
        records, _, _ = await self._driver.execute_query(
            "MATCH (s:Entity {project_id: $pid})-[r]->(o:Entity {project_id: $pid}) "
            "RETURN type(r) AS type, properties(r) AS props, s.id AS sid, o.id AS oid",
            pid=str(project_id),
        )
        return [self._to_relation(record) for record in records]

    async def get_relation(self, project_id: UUID, edge_id: UUID) -> GraphRelation | None:
        """A single edge by id, scoped to a project (both endpoints in `project_id`) — the
        tenancy-safe read behind the manual relation edit path (M4.S3a). Used to detect a
        re-predicate MERGE-collision before an add and to confirm an edge belongs to the project
        before a remove. Returns `None` if no such in-project edge exists."""
        records, _, _ = await self._driver.execute_query(
            "MATCH (s:Entity {project_id: $pid})-[r {id: $eid}]->(o:Entity {project_id: $pid}) "
            "RETURN type(r) AS type, properties(r) AS props, s.id AS sid, o.id AS oid",
            pid=str(project_id),
            eid=str(edge_id),
        )
        if not records:
            return None
        return self._to_relation(records[0])

    async def get_neighbourhood(self, entity_id: UUID) -> list[tuple[GraphRelation, GraphEntity]]:
        """The 1-hop neighbourhood of an entity: each incident edge + the node on its far end.

        The targeted read behind the reader side panel's "local graph around that entity" (M4.S2a,
        spec §3.5, DM-SP-1a) — `(e)-[r]-(n)` matches edges in **both** directions (the panel shows
        incoming and outgoing), and `startNode`/`endNode` carry the true orientation so the pure
        `build_ego_graph` can label each edge `out`/`in`. Fetches only the focal node's edges, not
        the whole project graph. Returns `(relation, neighbour)` pairs; a self-loop yields the focal
        node as the neighbour and is dropped by `build_ego_graph`, not here.

        The neighbour is constrained to the focal node's **own project** (`n.project_id =
        e.project_id`) — the same §6.4 tenancy scoping `get_relations` applies to both endpoints.
        A cross-project edge shouldn't exist (endpoints resolve within one story/project), so this
        is defense-in-depth: it keeps the panel from ever surfacing another project's node even if
        a stray edge did, matching the tenancy guard the endpoint enforces on the focal entity.
        """
        records, _, _ = await self._driver.execute_query(
            "MATCH (e:Entity {id: $id})-[r]-(n:Entity) "
            "WHERE n.project_id = e.project_id "
            "RETURN type(r) AS type, properties(r) AS props, "
            "startNode(r).id AS sid, endNode(r).id AS oid, properties(n) AS nprops",
            id=str(entity_id),
        )
        return [
            (self._to_relation(record), self._to_entity(dict(record["nprops"])))
            for record in records
        ]

    async def delete_relation(self, edge_id: UUID) -> None:
        """Remove a single graph edge by its deterministic id (the human relation-remove path,
        M4.S3a, DM-S3a-3). Matched by edge id in either direction; a missing edge is a no-op (so a
        retried remove is idempotent). Re-predicate is delete-old + `create_relation`-new, since
        the edge id is `uuid5` of the (subject, predicate, object) triple — a new predicate is a
        new edge, not an in-place update."""
        await self._driver.execute_query(
            "MATCH ()-[r {id: $id}]-() DELETE r",
            id=str(edge_id),
        )

    async def delete_entity(self, entity_id: UUID) -> None:
        """Remove a single entity node and its incident edges (the merge-of-B / whole-entity
        delete path, M4.S3b, DM-S3b-5). `DETACH DELETE` drops the node together with every
        relationship touching it; a missing node is a no-op, so a retried merge/delete is
        idempotent (the OQ-1 cross-store retry contract). The caller captures the before-image
        for undo *before* calling this — once the node is gone it is unreadable."""
        await self._driver.execute_query(
            "MATCH (e:Entity {id: $id}) DETACH DELETE e",
            id=str(entity_id),
        )

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
            # `None` for a legacy edge written before §4 (mint-forward, no backfill — DM-S5-3).
            edge_uid=_opt_uuid(props.get("edge_uid")),
        )
