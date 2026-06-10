"""Postgres repository for the document tree (spec §6.4).

Plain async psycopg 3, raw SQL, no ORM. Every function takes an
`AsyncConnection` so the caller owns the transaction boundary (the API layer
will commit; tests roll back for isolation). Rows map straight onto the domain
models because the column names and field names are identical.

Scope for now is create / read / delete — enough to round-trip the tree and
prove cascade deletes. The only realistic update is renumbering `order_index`
on reorder, which arrives with the chunking-persistence work; it is not added
speculatively here.

`embedding` is intentionally not written, and the read paths deliberately return
it as `NULL AS embedding` rather than selecting the real `vector(768)` column.
Reason: nothing writes embeddings yet, and reading the real column needs the
pgvector psycopg type registered (`register_vector_async`) or psycopg hands back
a string that fails Pydantic's `list[float] | None`. When the embedding pipeline
lands (it adds the `pgvector` dependency + type registration), switch these reads
to `SELECT ... embedding` and start writing the column. Tracked in docs/PLAN_SHORT.md
cross-cutting so the read path is not silently left returning None.
"""

from __future__ import annotations

from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import class_row

from story_forge.domain.models import (
    Chapter,
    EntityMention,
    Paragraph,
    Project,
    Scene,
    Story,
)

# --- Project ---------------------------------------------------------------


async def insert_project(conn: AsyncConnection, project: Project) -> None:
    await conn.execute(
        "INSERT INTO projects (id, name, language, world_id, style_anchor, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (
            project.id,
            project.name,
            project.language,
            project.world_id,
            project.style_anchor,
            project.created_at,
        ),
    )


async def get_project(conn: AsyncConnection, project_id: UUID) -> Project | None:
    async with conn.cursor(row_factory=class_row(Project)) as cur:
        await cur.execute(
            "SELECT id, name, language, world_id, style_anchor, created_at "
            "FROM projects WHERE id = %s",
            (project_id,),
        )
        return await cur.fetchone()


async def delete_project(conn: AsyncConnection, project_id: UUID) -> None:
    """Delete a project; stories/chapters/scenes/paragraphs cascade with it."""
    await conn.execute("DELETE FROM projects WHERE id = %s", (project_id,))


# --- Story -----------------------------------------------------------------


async def insert_story(conn: AsyncConnection, story: Story) -> None:
    await conn.execute(
        "INSERT INTO stories (id, project_id, title, raw_text, ingested_at) "
        "VALUES (%s, %s, %s, %s, %s)",
        (story.id, story.project_id, story.title, story.raw_text, story.ingested_at),
    )


async def get_story(conn: AsyncConnection, story_id: UUID) -> Story | None:
    async with conn.cursor(row_factory=class_row(Story)) as cur:
        await cur.execute(
            "SELECT id, project_id, title, raw_text, ingested_at FROM stories WHERE id = %s",
            (story_id,),
        )
        return await cur.fetchone()


async def get_story_for_update(conn: AsyncConnection, story_id: UUID) -> Story | None:
    """Locking variant of `get_story` — `SELECT ... FOR UPDATE`.

    Serializes concurrent writers against the same story row for the rest of the
    transaction. Used by the structure route to close a read-before-write race:
    without the lock, two parallel POSTs can each observe an empty outline and
    both insert a tree, producing duplicates. With it, the second request blocks
    until the first commits, then re-reads the now-non-empty outline and 409s.
    """
    async with conn.cursor(row_factory=class_row(Story)) as cur:
        await cur.execute(
            "SELECT id, project_id, title, raw_text, ingested_at FROM stories "
            "WHERE id = %s FOR UPDATE",
            (story_id,),
        )
        return await cur.fetchone()


async def update_story_raw_text(conn: AsyncConnection, story_id: UUID, raw_text: str) -> None:
    """Overwrite ``stories.raw_text`` for a story.

    Used by the structure route when the caller supplies a ``raw_text`` override
    in the request body (spec §7 step 2 "user accepts/edits"). The route runs
    this in the same transaction as the chapters/scenes/paragraphs insert, so a
    later GET sees the edited source instead of the originally-uploaded copy.
    """
    await conn.execute(
        "UPDATE stories SET raw_text = %s WHERE id = %s",
        (raw_text, story_id),
    )


# --- Chapter ---------------------------------------------------------------


async def insert_chapter(conn: AsyncConnection, chapter: Chapter) -> None:
    await conn.execute(
        "INSERT INTO chapters (id, story_id, order_index, title, summary) "
        "VALUES (%s, %s, %s, %s, %s)",
        (chapter.id, chapter.story_id, chapter.order_index, chapter.title, chapter.summary),
    )


async def get_chapter(conn: AsyncConnection, chapter_id: UUID) -> Chapter | None:
    async with conn.cursor(row_factory=class_row(Chapter)) as cur:
        await cur.execute(
            "SELECT id, story_id, order_index, title, summary FROM chapters WHERE id = %s",
            (chapter_id,),
        )
        return await cur.fetchone()


async def list_chapters(conn: AsyncConnection, story_id: UUID) -> list[Chapter]:
    async with conn.cursor(row_factory=class_row(Chapter)) as cur:
        await cur.execute(
            "SELECT id, story_id, order_index, title, summary "
            "FROM chapters WHERE story_id = %s ORDER BY order_index",
            (story_id,),
        )
        return await cur.fetchall()


# --- Scene -----------------------------------------------------------------


async def insert_scene(conn: AsyncConnection, scene: Scene) -> None:
    await conn.execute(
        "INSERT INTO scenes (id, chapter_id, order_index, title, summary) "
        "VALUES (%s, %s, %s, %s, %s)",
        (scene.id, scene.chapter_id, scene.order_index, scene.title, scene.summary),
    )


async def get_scene(conn: AsyncConnection, scene_id: UUID) -> Scene | None:
    async with conn.cursor(row_factory=class_row(Scene)) as cur:
        await cur.execute(
            "SELECT id, chapter_id, order_index, title, summary FROM scenes WHERE id = %s",
            (scene_id,),
        )
        return await cur.fetchone()


async def list_scenes(conn: AsyncConnection, chapter_id: UUID) -> list[Scene]:
    async with conn.cursor(row_factory=class_row(Scene)) as cur:
        await cur.execute(
            "SELECT id, chapter_id, order_index, title, summary "
            "FROM scenes WHERE chapter_id = %s ORDER BY order_index",
            (chapter_id,),
        )
        return await cur.fetchall()


# --- Paragraph -------------------------------------------------------------


async def insert_paragraph(conn: AsyncConnection, paragraph: Paragraph) -> None:
    # embedding is left to its column default (NULL) until the embedding pipeline lands.
    await conn.execute(
        "INSERT INTO paragraphs (id, scene_id, order_index, content, content_normalized) "
        "VALUES (%s, %s, %s, %s, %s)",
        (
            paragraph.id,
            paragraph.scene_id,
            paragraph.order_index,
            paragraph.content,
            paragraph.content_normalized,
        ),
    )


async def list_story_paragraphs(conn: AsyncConnection, story_id: UUID) -> list[Paragraph]:
    """Every paragraph in a story, in document order (chapter → scene → paragraph).

    The batch extraction driver walks a whole story, so it needs the leaves across
    the tree, not one scene's. Ordered by the three `order_index` levels so the
    sequence matches reading order (and so resume processes paragraphs predictably).
    """
    async with conn.cursor(row_factory=class_row(Paragraph)) as cur:
        await cur.execute(
            "SELECT p.id, p.scene_id, p.order_index, p.content, p.content_normalized, "
            "NULL AS embedding "
            "FROM paragraphs p "
            "JOIN scenes sc ON sc.id = p.scene_id "
            "JOIN chapters ch ON ch.id = sc.chapter_id "
            "WHERE ch.story_id = %s "
            "ORDER BY ch.order_index, sc.order_index, p.order_index",
            (story_id,),
        )
        return await cur.fetchall()


async def get_paragraph(conn: AsyncConnection, paragraph_id: UUID) -> Paragraph | None:
    async with conn.cursor(row_factory=class_row(Paragraph)) as cur:
        await cur.execute(
            "SELECT id, scene_id, order_index, content, content_normalized, NULL AS embedding "
            "FROM paragraphs WHERE id = %s",
            (paragraph_id,),
        )
        return await cur.fetchone()


async def list_paragraphs(conn: AsyncConnection, scene_id: UUID) -> list[Paragraph]:
    async with conn.cursor(row_factory=class_row(Paragraph)) as cur:
        await cur.execute(
            "SELECT id, scene_id, order_index, content, content_normalized, NULL AS embedding "
            "FROM paragraphs WHERE scene_id = %s ORDER BY order_index",
            (scene_id,),
        )
        return await cur.fetchall()


# --- Entity mention (cross-store back-reference, §6.4) ---------------------


async def insert_entity_mention(conn: AsyncConnection, mention: EntityMention) -> None:
    """Record that a Neo4j entity was mentioned in a paragraph.

    Written *after* the Neo4j node (OQ-1: Neo4j owns identity, so an orphaned node
    is more benign than a mention pointing at a node that was never created). There
    is no FK on `entity_id` — the referenced entity lives in Neo4j, not Postgres.
    """
    await conn.execute(
        "INSERT INTO entity_mentions "
        "(id, paragraph_id, entity_id, span_start, span_end, confidence) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (
            mention.id,
            mention.paragraph_id,
            mention.entity_id,
            mention.span_start,
            mention.span_end,
            mention.confidence,
        ),
    )


async def list_entity_mentions_for_paragraph(
    conn: AsyncConnection, paragraph_id: UUID
) -> list[EntityMention]:
    async with conn.cursor(row_factory=class_row(EntityMention)) as cur:
        await cur.execute(
            "SELECT id, paragraph_id, entity_id, span_start, span_end, confidence "
            "FROM entity_mentions WHERE paragraph_id = %s",
            (paragraph_id,),
        )
        return await cur.fetchall()
