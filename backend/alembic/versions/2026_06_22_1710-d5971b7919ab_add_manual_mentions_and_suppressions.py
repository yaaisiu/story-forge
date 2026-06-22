"""add manual mentions and suppressions

Revision ID: d5971b7919ab
Revises: 285403049b2b
Create Date: 2026-06-22 17:10:39.702598

M4.S3c manual correction in the reader (spec §3.5 / §6.4). The reader's highlight layer stops
being purely derived: an author can now tag an arbitrary span, hide a wrong highlight, or change a
boundary (DM-S3c-1 "save only what you touch" — overlay stored manual spans + suppressions over the
render-time search). Two schema additions, both purely additive (no backfill, existing extraction
mentions unchanged):

- `entity_mentions.source` — `'extraction'` (default, the cascade-written mention with NULL
  offsets) vs `'manual'` (a human tag carrying real `span_start`/`span_end` that overlays + wins
  over search). An explicit flag, not a "non-null span" heuristic, so manual stays distinguishable
  the day extraction ever stores real offsets (DM-S3c-1, build-call 1).
- `mention_suppressions` — a negative record the reader subtracts: "this `[start, end)` is **not**
  a highlight". `entity_id` NULL = "not an entity" (clears every claimant at the span); set = "not
  this entity" (clears that one). Mirrors `entity_mentions`' cross-store seam: `paragraph_id` is a
  real FK (cascade with the tree), `entity_id` carries **no** FK (references a Neo4j node — OQ-1).

Raw SQL (`op.execute`) to match the existing schema migrations.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5971b7919ab"  # pragma: allowlist secret  (alembic revision id, not a secret)
down_revision: str | Sequence[str] | None = "285403049b2b"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing rows default to 'extraction'; manual writes set 'manual'. No backfill.
    op.execute("ALTER TABLE entity_mentions ADD COLUMN source text NOT NULL DEFAULT 'extraction'")
    op.execute(
        """
        CREATE TABLE mention_suppressions (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            paragraph_id uuid NOT NULL REFERENCES paragraphs (id) ON DELETE CASCADE,
            entity_id    uuid,
            span_start   integer NOT NULL,
            span_end     integer NOT NULL,
            created_at   timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # The reader reads every suppression in a story by walking paragraphs (mirror of the
    # entity_mentions reader feed), so index by paragraph.
    op.execute(
        "CREATE INDEX ix_mention_suppressions_paragraph_id ON mention_suppressions (paragraph_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_mention_suppressions_paragraph_id")
    op.execute("DROP TABLE IF EXISTS mention_suppressions")
    op.execute("ALTER TABLE entity_mentions DROP COLUMN IF EXISTS source")
