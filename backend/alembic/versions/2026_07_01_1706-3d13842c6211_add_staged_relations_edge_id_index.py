"""add staged_relations edge_id index

Revision ID: 3d13842c6211
Revises: c0c7904a555c
Create Date: 2026-07-01 17:06:45.249087

Indexes `staged_relations.edge_id` for the edge-evidence read (graph-quality S3, DM-EE-2):
`get_written_by_edge_id` fetches all `written` rows for one content-addressed edge, and the only
existing index is `(story_id, status)`. Single-column on `edge_id` (the selective predicate); the
story-scope filter rides the same query.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3d13842c6211"  # pragma: allowlist secret  (alembic revision id, not a secret)
down_revision: str | Sequence[str] | None = "c0c7904a555c"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE INDEX ix_staged_relations_edge_id ON staged_relations (edge_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_staged_relations_edge_id")
