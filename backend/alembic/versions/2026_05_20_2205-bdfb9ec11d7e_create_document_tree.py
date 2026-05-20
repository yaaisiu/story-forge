"""create document tree

Revision ID: bdfb9ec11d7e
Revises:
Create Date: 2026-05-20 22:05:33.479936

Creates the Postgres document hierarchy from spec §6.4:
Project → Story → Chapter → Scene → Paragraph.

Written as raw SQL (`op.execute`) rather than `op.create_table` so it is a
faithful transcription of the spec — including the pgvector `vector(768)`
column — without pulling in a SQLAlchemy vector type just to express it.
Children cascade-delete with their parent. Sibling order is `order_index`
(an integer ordinal; never the reserved word `order`).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bdfb9ec11d7e"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector must exist before any vector(...) column is declared.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE projects (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name         text NOT NULL,
            language     text NOT NULL,
            world_id     uuid,
            style_anchor text,
            created_at   timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE stories (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id  uuid NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
            title       text NOT NULL,
            raw_text    text NOT NULL,
            ingested_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE chapters (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            story_id    uuid NOT NULL REFERENCES stories (id) ON DELETE CASCADE,
            order_index integer NOT NULL,
            title       text,
            summary     text
        )
        """
    )

    op.execute(
        """
        CREATE TABLE scenes (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            chapter_id  uuid NOT NULL REFERENCES chapters (id) ON DELETE CASCADE,
            order_index integer NOT NULL,
            title       text,
            summary     text
        )
        """
    )

    op.execute(
        """
        CREATE TABLE paragraphs (
            id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            scene_id           uuid NOT NULL REFERENCES scenes (id) ON DELETE CASCADE,
            order_index        integer NOT NULL,
            content            text NOT NULL,
            content_normalized text,
            embedding          vector(768)
        )
        """
    )

    # Children are routinely fetched and ordered by parent; index those paths.
    op.execute("CREATE INDEX ix_stories_project_id ON stories (project_id)")
    op.execute("CREATE INDEX ix_chapters_story_id ON chapters (story_id, order_index)")
    op.execute("CREATE INDEX ix_scenes_chapter_id ON scenes (chapter_id, order_index)")
    op.execute("CREATE INDEX ix_paragraphs_scene_id ON paragraphs (scene_id, order_index)")


def downgrade() -> None:
    # Drop in reverse dependency order. The vector extension is left installed:
    # it may be shared, and dropping it is not this migration's concern.
    op.execute("DROP TABLE IF EXISTS paragraphs")
    op.execute("DROP TABLE IF EXISTS scenes")
    op.execute("DROP TABLE IF EXISTS chapters")
    op.execute("DROP TABLE IF EXISTS stories")
    op.execute("DROP TABLE IF EXISTS projects")
