"""create staged_relations

Revision ID: 893f57edb237
Revises: 30cb9c529752
Create Date: 2026-06-16 17:38:04.367887

M3.S4e relation-write (DM-Rel-4). Extraction stages each paragraph's relations as
surface-form triples; this table gives them the lifecycle the JSONB blob in
`paragraph_processed.relations` could not — a per-relation id, a `staged → written | rejected`
status, the endpoint ids resolved at commit, and the committed `edge_id` — so the §3.3 5th
human action ("decide on relations") can write Neo4j edges under an explicit gate and an
audit trail (INV-3), idempotently.

- `id` is a deterministic per-paragraph-occurrence id (`uuid5` of the surface triple within a
  paragraph), so re-staging a paragraph is idempotent (`ON CONFLICT (id) DO NOTHING`).
- `subject`/`predicate`/`object` are *surface strings* (no entity id until both endpoints
  resolve to accepted candidates). `subject_entity_id`/`object_entity_id`/`edge_id` are
  nullable, filled at commit. They reference **Neo4j** ids and so carry no Postgres FK (the
  OQ-1 cross-store seam, as for `candidates.target_entity_id`).
- `status` mirrors the staged-relation lifecycle (`staged|written|rejected`).

Additive only. The `paragraph_processed` *marker row* stays the resume checkpoint; from S4e
the relation payload is staged here instead of into `paragraph_processed.relations`, which is
left in place (vestigial, `DEFAULT '[]'`) — dropping it is a separate cleanup. Raw SQL
(`op.execute`) to match the existing migrations.

Re-point note (DM-Rel-5): M3 *writes* edges; re-pointing an edge when two already-accepted
entities are merged is an M4 concern, out of scope here.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "893f57edb237"  # pragma: allowlist secret  (alembic revision id, not a secret)
down_revision: str | Sequence[str] | None = "30cb9c529752"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE staged_relations (
            id                uuid PRIMARY KEY,
            story_id          uuid NOT NULL,
            paragraph_id      uuid NOT NULL REFERENCES paragraphs (id) ON DELETE CASCADE,
            subject           text NOT NULL,
            predicate         text NOT NULL,
            object            text NOT NULL,
            confidence        double precision,
            evidence_quote    text,
            subject_entity_id uuid,
            object_entity_id  uuid,
            edge_id           uuid,
            status            text NOT NULL DEFAULT 'staged',
            created_at        timestamptz NOT NULL DEFAULT now(),
            updated_at        timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # The decide-relations queue reads a story's still-staged relations (status filter).
    op.execute(
        "CREATE INDEX ix_staged_relations_story_status ON staged_relations (story_id, status)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS staged_relations")
