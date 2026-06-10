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
