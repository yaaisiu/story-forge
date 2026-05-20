// Applied automatically at first compose-up by the one-shot `neo4j-init` service
// (after the `neo4j` service passes its healthcheck). Idempotent thanks to
// IF NOT EXISTS — re-running is safe.

// --- Uniqueness constraints (also auto-create backing indexes) ---
CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
  FOR (e:Entity)  REQUIRE e.id IS UNIQUE;

CREATE CONSTRAINT project_id_unique IF NOT EXISTS
  FOR (p:Project) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT world_id_unique IF NOT EXISTS
  FOR (w:World)   REQUIRE w.id IS UNIQUE;

// --- Indexes for the access patterns named in spec §6.4 ---
// Filter entities by type (the primary scoping query)
CREATE INDEX entity_type_idx IF NOT EXISTS
  FOR (e:Entity) ON (e.type);

// Filter entities by project_id / world_id (multi-tenancy via property)
CREATE INDEX entity_project_idx IF NOT EXISTS
  FOR (e:Entity) ON (e.project_id);

CREATE INDEX entity_world_idx IF NOT EXISTS
  FOR (e:Entity) ON (e.world_id);

// Lookup by canonical name in either language (cascade Stage 1 hot path)
CREATE INDEX entity_canonical_name_pl_idx IF NOT EXISTS
  FOR (e:Entity) ON (e.canonical_name_pl);

CREATE INDEX entity_canonical_name_en_idx IF NOT EXISTS
  FOR (e:Entity) ON (e.canonical_name_en);
