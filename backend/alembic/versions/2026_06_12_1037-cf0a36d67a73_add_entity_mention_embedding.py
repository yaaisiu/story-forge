"""add entity_mention embedding

Revision ID: cf0a36d67a73
Revises: 2b5e854961e1
Create Date: 2026-06-12 10:37:11.801189

Adds the per-mention `embedding vector(768)` column to `entity_mentions` — the storage
for the §3.3 Stage-2 cascade (DM3/DM4, M3.S2). Each mention carries the embedding of its
context, and Stage 2 takes the max cosine of a candidate's context vector against an
entity's stored mention vectors. The column is **nullable**: under the foundation-only
M3.S2 scope the extraction path records mentions with a NULL embedding (EmbeddingAgent is
built but not yet wired into the live coordinator — that lands with the cascade in M3.S4),
and the dimensionality matches the multilingual mpnet model (paraphrase-multilingual-
mpnet-base-v2, 768-dim).

The `vector` type is already enabled (CREATE EXTENSION in the create_document_tree
migration, which `paragraphs.embedding vector(768)` also uses) — no extension step here.
Raw SQL (`op.execute`) to match the existing schema migrations.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cf0a36d67a73"  # pragma: allowlist secret  (alembic revision id, not a secret)
down_revision: str | Sequence[str] | None = "2b5e854961e1"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE entity_mentions ADD COLUMN embedding vector(768)")


def downgrade() -> None:
    op.execute("ALTER TABLE entity_mentions DROP COLUMN IF EXISTS embedding")
