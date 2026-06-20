"""Postgres repository for the document tree (spec §6.4).

Plain async psycopg 3, raw SQL, no ORM. Every function takes an
`AsyncConnection` so the caller owns the transaction boundary (the API layer
will commit; tests roll back for isolation). Rows map straight onto the domain
models because the column names and field names are identical.

Scope for now is create / read / delete — enough to round-trip the tree and
prove cascade deletes. The only realistic update is renumbering `order_index`
on reorder, which arrives with the chunking-persistence work; it is not added
speculatively here.

Embedding columns are real `vector(768)` now (M3.S2): the reads select the actual
`paragraphs.embedding` / `entity_mentions.embedding` column, which deserializes to
`list[float]` because every connection is opened via `db.connect` (it calls
`register_vector_async`). `paragraphs.embedding` has no producer yet, so it reads
back None; `entity_mentions.embedding` is written by `insert_entity_mention` (as a
pgvector `Vector`), currently always None under the foundation-only M3.S2 scope —
EmbeddingAgent is wired into the live path with the cascade in M3.S4.
"""

from __future__ import annotations

from uuid import UUID

from pgvector import Vector
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
            "p.embedding "
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
            "SELECT id, scene_id, order_index, content, content_normalized, embedding "
            "FROM paragraphs WHERE id = %s",
            (paragraph_id,),
        )
        return await cur.fetchone()


async def list_paragraphs(conn: AsyncConnection, scene_id: UUID) -> list[Paragraph]:
    async with conn.cursor(row_factory=class_row(Paragraph)) as cur:
        await cur.execute(
            "SELECT id, scene_id, order_index, content, content_normalized, embedding "
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
    # pgvector's psycopg dumper is registered for Vector / numpy.ndarray, not a bare
    # list — wrap the embedding so it adapts to the `vector` column (None → NULL stays
    # NULL). Under M3.S4a the accept path writes a real per-mention vector (copied from the
    # candidate's context embedding). `ON CONFLICT (id) DO NOTHING` makes an accept-path retry
    # (a crash before the candidate's status flip) idempotent when the mention id is derived
    # deterministically from the candidate.
    await conn.execute(
        "INSERT INTO entity_mentions "
        "(id, paragraph_id, entity_id, span_start, span_end, confidence, embedding) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
        (
            mention.id,
            mention.paragraph_id,
            mention.entity_id,
            mention.span_start,
            mention.span_end,
            mention.confidence,
            None if mention.embedding is None else Vector(mention.embedding),
        ),
    )


async def repoint_entity_mentions(
    conn: AsyncConnection, *, from_entity_id: UUID, to_entity_id: UUID
) -> list[UUID]:
    """Move every mention of one entity onto another — the cross-store half of a merge (M4.S3b,
    DM-S3b-4). When B is merged into A, B's `entity_mentions` rows must follow or the reader
    silently drops B's highlights / the side panel shows a ghost. There is no FK on `entity_id`
    (the entity lives in Neo4j), so this is a plain bulk `UPDATE`; the per-mention `embedding`
    `vector(768)` follows the row for free. Idempotent: a re-run after the move matches no rows
    (B is gone) and returns ``[]``. **Returns the ids of the rows it moved** (via `RETURNING`) —
    the merge records them in the before-image so undo (M4.S3b-be2) re-points *exactly* those
    rows back to B, not A's own mentions."""
    cur = await conn.execute(
        "UPDATE entity_mentions SET entity_id = %s WHERE entity_id = %s RETURNING id",
        (to_entity_id, from_entity_id),
    )
    return [row[0] for row in await cur.fetchall()]


async def reassign_entity_mentions(
    conn: AsyncConnection, *, mention_ids: list[UUID], to_entity_id: UUID
) -> None:
    """Move *specific* mention rows onto an entity by id — the inverse of a merge's mention
    re-point (M4.S3b-be2 undo). Unlike `repoint_entity_mentions` (which moves *all* of one
    entity's mentions), undo must move back **exactly** the ids the merge recorded, never the
    survivor's own mentions. A no-op for an empty id list."""
    if not mention_ids:
        return
    await conn.execute(
        "UPDATE entity_mentions SET entity_id = %s WHERE id = ANY(%s)",
        (to_entity_id, mention_ids),
    )


async def list_entity_mentions_for_entity(
    conn: AsyncConnection, entity_id: UUID
) -> list[EntityMention]:
    """Every mention of one entity — the full-row snapshot a whole-entity delete captures for undo
    (M4.S3b-be2, DM-S3b-5). Unlike a merge (which only *moves* mentions), a delete *removes* them,
    so undo must re-insert the whole row, embedding and all — hence the full select."""
    async with conn.cursor(row_factory=class_row(EntityMention)) as cur:
        await cur.execute(
            "SELECT id, paragraph_id, entity_id, span_start, span_end, confidence, embedding "
            "FROM entity_mentions WHERE entity_id = %s",
            (entity_id,),
        )
        return await cur.fetchall()


async def delete_entity_mentions(conn: AsyncConnection, entity_id: UUID) -> None:
    """Drop every mention of one entity — the Postgres half of a whole-entity delete (the Neo4j
    half is `DETACH DELETE`; spec §3.4 "its text occurrences"). The caller snapshots them first
    (`list_entity_mentions_for_entity`) so undo can restore them."""
    await conn.execute("DELETE FROM entity_mentions WHERE entity_id = %s", (entity_id,))


async def list_entity_mentions_for_paragraph(
    conn: AsyncConnection, paragraph_id: UUID
) -> list[EntityMention]:
    async with conn.cursor(row_factory=class_row(EntityMention)) as cur:
        await cur.execute(
            "SELECT id, paragraph_id, entity_id, span_start, span_end, confidence, embedding "
            "FROM entity_mentions WHERE paragraph_id = %s",
            (paragraph_id,),
        )
        return await cur.fetchall()


async def list_entity_mentions_for_story(
    conn: AsyncConnection, story_id: UUID
) -> list[EntityMention]:
    """Every entity mention across a story's paragraphs (the §3.5 reader's per-paragraph join).

    The reader highlights, in each paragraph, only the entities a human *accepted* as mentioned
    there — and `entity_mentions` rows are written only by the accept path, so this is
    accepted-only by construction (the read-side echo of INV-1, DM-IH-7). One query over the
    document tree instead of per-paragraph fan-out; the route groups by `paragraph_id`.
    """
    async with conn.cursor(row_factory=class_row(EntityMention)) as cur:
        await cur.execute(
            "SELECT m.id, m.paragraph_id, m.entity_id, m.span_start, m.span_end, "
            "m.confidence, m.embedding "
            "FROM entity_mentions m "
            "JOIN paragraphs p ON p.id = m.paragraph_id "
            "JOIN scenes sc ON sc.id = p.scene_id "
            "JOIN chapters ch ON ch.id = sc.chapter_id "
            "WHERE ch.story_id = %s",
            (story_id,),
        )
        return await cur.fetchall()


async def list_mention_vectors_for_entities(
    conn: AsyncConnection, entity_ids: list[UUID]
) -> dict[UUID, list[list[float]]]:
    """Stored mention vectors grouped by entity (the §3.3 Stage-2 read).

    Stage 2 matches a candidate's context vector against an accepted entity's mention
    vectors. Keyed by the (Neo4j) `entity_id`; mentions with a NULL embedding are skipped.
    Read once per ingest run for a project's accepted entities (the C4 read-once pattern).
    `embedding` deserialises to `list[float]` because the connection registers pgvector.
    """
    if not entity_ids:
        return {}
    cur = await conn.execute(
        "SELECT entity_id, embedding FROM entity_mentions "
        "WHERE entity_id = ANY(%s) AND embedding IS NOT NULL",
        (entity_ids,),
    )
    grouped: dict[UUID, list[list[float]]] = {}
    for entity_id, embedding in await cur.fetchall():
        grouped.setdefault(entity_id, []).append([float(x) for x in embedding])
    return grouped


async def list_recent_mention_texts_for_entities(
    conn: AsyncConnection, entity_ids: list[UUID], *, limit_per_entity: int = 3
) -> dict[UUID, list[str]]:
    """Up to `limit_per_entity` mention paragraph texts per entity (the Stage-3 judge context).

    The judge reasons over an existing entity's recent mentions (spec Appendix C.3). Bounded
    per entity so the prompt stays small; ordering is by mention id (entity_mentions carries
    no timestamp at PoC — "recent" is approximated as a stable sample, documented as such).
    """
    if not entity_ids:
        return {}
    cur = await conn.execute(
        "SELECT entity_id, content FROM ("
        "  SELECT m.entity_id, p.content, "
        "         row_number() OVER (PARTITION BY m.entity_id ORDER BY m.id) AS rn "
        "  FROM entity_mentions m JOIN paragraphs p ON p.id = m.paragraph_id "
        "  WHERE m.entity_id = ANY(%s)"
        ") t WHERE rn <= %s",
        (entity_ids, limit_per_entity),
    )
    grouped: dict[UUID, list[str]] = {}
    for entity_id, content in await cur.fetchall():
        grouped.setdefault(entity_id, []).append(content)
    return grouped
