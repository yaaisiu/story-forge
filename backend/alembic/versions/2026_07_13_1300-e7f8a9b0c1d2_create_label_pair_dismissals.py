"""create label_pair_dismissals

Revision ID: e7f8a9b0c1d2
Revises: b1c2d3e4f5a6
Create Date: 2026-07-13 13:00:00.000000

Graph-quality S6a (register DM-NN-3): the label-synonym self-join *suggests* synonymous
predicate / entity-type names computed on open; this table records the human's "these are
genuinely different" dismissals so a rejected pair is not re-surfaced every time the
normalise list opens. The direct sibling of `duplicate_suggestion_dismissals` (ADR 0010) —
the *same* "a negative record the read subtracts" design at **label** granularity, a
separate table (a label pair is a *string* pair, not the uuid pair that store keys on; the
project already runs sibling-table-per-surface, cf. `mention_suppressions`). No fresh ADR —
ADR 0010's pattern governs.

Staging-side (Postgres), so INV-9 holds — this is never a graph write. `project_id`
references a Neo4j-backed project, so it carries **no** Postgres FK (the OQ-1 cross-store
seam), matching `duplicate_suggestion_dismissals`. The row's `id` is an app-supplied
deterministic `uuid5` over the project + `surface` + the *sorted* label pair
(`domain.label_synonyms.label_dismissal_id`), so an unordered pair has one identity,
re-dismissal is idempotent (`ON CONFLICT (id) DO NOTHING`), and a type dismissal never
suppresses an identically-spelled predicate pair. `label_lo`/`label_hi` are stored in
canonical (sorted) order for the same reason. Retention: none at PoC (OQ-4); a dismissal is
reversible (the row is deleted on un-dismiss).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"  # pragma: allowlist secret  (alembic revision id, not a secret)
down_revision: str | Sequence[str] | None = "b1c2d3e4f5a6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE label_pair_dismissals (
            id          uuid PRIMARY KEY,
            project_id  uuid NOT NULL,
            surface     text NOT NULL,
            label_lo    text NOT NULL,
            label_hi    text NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_label_pair_dismissals_project_id ON label_pair_dismissals (project_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS label_pair_dismissals")
