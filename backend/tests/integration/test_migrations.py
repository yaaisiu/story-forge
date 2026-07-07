"""Migration smoke tests: the schema builds, and downgrade is reversible.

These run against the `story_forge_test` database created by the session fixture
in conftest (which has already applied `alembic upgrade head`). We assert the
spec §6.4 tables exist with the agreed `order_index` column, the pgvector
extension is enabled, and that a full down/up cycle leaves the schema intact.
"""

from __future__ import annotations

import psycopg
import pytest
from alembic import command
from alembic.config import Config

EXPECTED_TABLES = {
    "projects",
    "stories",
    "chapters",
    "scenes",
    "paragraphs",
    "entity_mentions",
    "mention_suppressions",
    "duplicate_suggestion_dismissals",
}


async def _public_tables(conn: psycopg.AsyncConnection) -> set[str]:
    cur = await conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    )
    return {row[0] for row in await cur.fetchall()}


@pytest.mark.integration
async def test_head_creates_expected_tables(db_conn: psycopg.AsyncConnection) -> None:
    assert await _public_tables(db_conn) >= EXPECTED_TABLES


@pytest.mark.integration
async def test_ordering_column_is_order_index(db_conn: psycopg.AsyncConnection) -> None:
    # The decided convention (§6.4): siblings order by `order_index`, never `order`.
    for table in ("chapters", "scenes", "paragraphs"):
        cur = await db_conn.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
            (table, "order_index"),
        )
        assert await cur.fetchone() is not None, f"{table}.order_index missing"


@pytest.mark.integration
async def test_entity_mentions_source_column_defaults_to_extraction(
    db_conn: psycopg.AsyncConnection,
) -> None:
    # M4.S3c: a `source` column distinguishes cascade-written ('extraction') from human-tagged
    # ('manual') mentions; existing/extraction rows default to 'extraction' (no backfill).
    cur = await db_conn.execute(
        "SELECT column_default, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'entity_mentions' AND column_name = 'source'"
    )
    row = await cur.fetchone()
    assert row is not None, "entity_mentions.source missing"
    default, is_nullable = row
    assert "extraction" in default
    assert is_nullable == "NO"


@pytest.mark.integration
async def test_mention_suppressions_schema(db_conn: psycopg.AsyncConnection) -> None:
    # M4.S3c: the suppression table — paragraph_id NOT NULL (FK), entity_id nullable
    # (NULL = "not an entity" / all; set = "not this entity" / one), spans NOT NULL.
    cur = await db_conn.execute(
        "SELECT column_name, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'mention_suppressions'"
    )
    nullability = dict(await cur.fetchall())
    assert nullability["paragraph_id"] == "NO"
    assert nullability["entity_id"] == "YES"
    assert nullability["span_start"] == "NO"
    assert nullability["span_end"] == "NO"


@pytest.mark.integration
async def test_duplicate_suggestion_dismissals_schema(db_conn: psycopg.AsyncConnection) -> None:
    # Graph-quality S4a (DM-CD-3): staging-side pair-dismissal store — id PK (app-supplied
    # uuid5, no default), project_id + both entity ids NOT NULL and un-FK'd (Neo4j ids), plus a
    # created_at. All columns NOT NULL.
    cur = await db_conn.execute(
        "SELECT column_name, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'duplicate_suggestion_dismissals'"
    )
    nullability = dict(await cur.fetchall())
    assert set(nullability) == {
        "id",
        "project_id",
        "entity_id_lo",
        "entity_id_hi",
        "created_at",
    }
    assert all(v == "NO" for v in nullability.values())


@pytest.mark.integration
async def test_projects_world_id_column_dropped(db_conn: psycopg.AsyncConnection) -> None:
    # M4 multi-story (DM-MS-5): the always-null `projects.world_id` was vestigial dead
    # weight for a world-graph parent that the PoC cut (§3.6 → backlog). The drop-column
    # migration removed it; assert it is gone.
    cur = await db_conn.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'projects' AND column_name = 'world_id'"
    )
    assert await cur.fetchone() is None, "projects.world_id should have been dropped"


@pytest.mark.integration
async def test_pgvector_extension_enabled(db_conn: psycopg.AsyncConnection) -> None:
    cur = await db_conn.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
    assert await cur.fetchone() is not None


@pytest.mark.integration
async def test_downgrade_then_upgrade_is_reversible(
    db_conn: psycopg.AsyncConnection, alembic_cfg: Config
) -> None:
    # Release any read snapshot/locks before running DDL on Alembic's own connection.
    assert await _public_tables(db_conn) >= EXPECTED_TABLES
    await db_conn.rollback()

    command.downgrade(alembic_cfg, "base")
    assert EXPECTED_TABLES.isdisjoint(await _public_tables(db_conn))

    # Restore head so the rest of the session sees the full schema again.
    command.upgrade(alembic_cfg, "head")
    assert await _public_tables(db_conn) >= EXPECTED_TABLES
