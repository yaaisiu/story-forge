"""create duplicate_suggestion_dismissals

Revision ID: b1c2d3e4f5a6
Revises: 3d13842c6211
Create Date: 2026-07-07 12:00:00.000000

Graph-quality S4a (register DM-CD-3, ADR 0010): the duplicate self-join *suggests*
likely-duplicate entity pairs computed on open; this table records the human's "not a
duplicate" dismissals so a rejected pair is not re-surfaced every time the list opens (the
`candidate_decisions`/DM-rej precedent — remembering a human's rejection is a feature).

Staging-side (Postgres), so INV-9 holds — this is never a graph write. `project_id` and the
two entity ids reference Neo4j nodes, so they carry **no** Postgres FK (the OQ-1 cross-store
seam), matching `candidates`. The row's `id` is an app-supplied deterministic `uuid5` over the
project + the *sorted* entity pair (`domain.duplicate_clusters.dismissal_pair_id`), so an
unordered pair has one identity and re-dismissal is idempotent (`ON CONFLICT (id) DO NOTHING`)
— the project's uuid5-PK idiom (cf. `staged_relations.id`), no `UNIQUE`/`LEAST/GREATEST` needed.
`entity_id_lo`/`entity_id_hi` are stored in canonical (sorted) order for the same reason.
Retention: none at PoC (OQ-4), same posture as the other staging tables; a dismissal is
reversible (the row is deleted on un-dismiss).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"  # pragma: allowlist secret  (alembic revision id, not a secret)
down_revision: str | Sequence[str] | None = "3d13842c6211"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE duplicate_suggestion_dismissals (
            id            uuid PRIMARY KEY,
            project_id    uuid NOT NULL,
            entity_id_lo  uuid NOT NULL,
            entity_id_hi  uuid NOT NULL,
            created_at    timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_duplicate_suggestion_dismissals_project_id "
        "ON duplicate_suggestion_dismissals (project_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS duplicate_suggestion_dismissals")
