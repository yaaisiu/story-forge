"""create entity_mentions

Revision ID: d721987b4168
Revises: 60ebe30ec792
Create Date: 2026-06-09 19:33:10.309020

Creates the §6.4 `entity_mentions` table — the Postgres back-reference recording
where a graph entity appears in the document tree (paragraph ↔ entity). This is
the M2.S4 cross-store seam: a mention's `paragraph_id` is a real Postgres FK
(paragraphs live here, cascade with the tree), but `entity_id` references a Neo4j
node and therefore carries **no** Postgres FK — the two stores cannot share a
transaction (OQ-1). `span_start` / `span_end` / `confidence` are nullable: the LLM
extraction path yields an evidence quote, not reliable character offsets, so a
mention may be written without spans.

Raw SQL (`op.execute`) to match the existing schema migrations.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d721987b4168"  # pragma: allowlist secret  (alembic revision id, not a secret)
down_revision: str | Sequence[str] | None = "60ebe30ec792"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE entity_mentions (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            paragraph_id uuid NOT NULL REFERENCES paragraphs (id) ON DELETE CASCADE,
            entity_id    uuid NOT NULL,
            span_start   integer,
            span_end     integer,
            confidence   double precision
        )
        """
    )
    # Mentions are fetched both ways: "where does this entity appear?" (by entity_id)
    # and "what entities are in this paragraph?" (by paragraph_id). Index both.
    op.execute("CREATE INDEX ix_entity_mentions_paragraph_id ON entity_mentions (paragraph_id)")
    op.execute("CREATE INDEX ix_entity_mentions_entity_id ON entity_mentions (entity_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS entity_mentions")
