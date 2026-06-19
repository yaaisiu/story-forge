"""create graph_edits

Revision ID: 3d760a15b9f9
Revises: 893f57edb237
Create Date: 2026-06-19 12:36:07.215149

M4.S3a entity-&-relation editing (DM-S3a-2). The first slice that *writes* committed graph
state needs a durable before→after record of every human edit — the substrate for INV-3 undo
and for the correction-as-training-data flywheel — the graph-edit twin of `candidate_decisions`
(which logs accept/reject, not post-commit edits of an already-written node/edge).

One table covers **both** node-field edits and edge add/remove (the DM-S3a-2 verify-at-build):
`target_kind` discriminates `'entity' | 'relation'`, `op` names the operation (`'edit_fields'`,
`'add_relation'`, `'remove_relation'`), and `before`/`after` carry the JSONB images (`before` is
null for an add, `after` null for a remove). `target_id` references a **Neo4j** id (entity id or
edge id) and so carries no Postgres FK — the OQ-1 cross-store seam, as for
`candidates.target_entity_id` / `staged_relations.edge_id`.

Append-only; a row is never updated. Raw SQL (`op.execute`) to match the existing migrations.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3d760a15b9f9"  # pragma: allowlist secret  (alembic revision id, not a secret)
down_revision: str | Sequence[str] | None = "893f57edb237"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE graph_edits (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            target_id   uuid NOT NULL,
            target_kind text NOT NULL,
            op          text NOT NULL,
            before      jsonb,
            after       jsonb,
            actor       text NOT NULL DEFAULT 'human',
            created_at  timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # Undo / history reads a target's edits newest-last.
    op.execute("CREATE INDEX ix_graph_edits_target_time ON graph_edits (target_id, created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS graph_edits")
