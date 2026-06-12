"""Postgres connection wiring for the API layer.

The repo functions (`postgres_repo`) each take an `AsyncConnection` and leave the
transaction boundary to the caller. This module provides that boundary for HTTP
requests: `get_connection` is a FastAPI dependency that opens one connection per
request, commits if the handler returns normally, and rolls back on error.

A connection pool is deliberately omitted — this is a single-user local app, and
a per-request connect is simple and sufficient. Add `psycopg_pool` here if and
when concurrency makes it worth it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pgvector.psycopg import register_vector_async
from psycopg import AsyncConnection
from sqlalchemy.engine import make_url

from story_forge.config import settings


async def connect(
    conninfo: dict[str, object] | None = None, *, autocommit: bool = False
) -> AsyncConnection:
    """Open a psycopg connection with the pgvector type registered.

    Every connection that touches a `vector` column (`paragraphs.embedding`,
    `entity_mentions.embedding`) must call `register_vector_async` first, or psycopg
    hands back a raw string on read (failing Pydantic's `list[float]`) and has no
    dumper for the column on write. Centralising it here means all three connect sites
    — the API request dependency, the mention store's autocommit connection, and the
    test fixture — register the type the same way. `conninfo` defaults to the app DB;
    pass the test DB's kwargs from the fixture.
    """
    conn = await AsyncConnection.connect(
        autocommit=autocommit,
        **(conninfo if conninfo is not None else libpq_kwargs(settings.database_url)),  # type: ignore[arg-type]
    )
    # Close the just-opened connection if registration fails (e.g. an unmigrated DB
    # where the `vector` type is absent raises) — otherwise it leaks, since the caller
    # only gets the connection to manage once this returns.
    try:
        await register_vector_async(conn)
    except BaseException:
        await conn.close()
        raise
    return conn


def libpq_kwargs(sqlalchemy_url: str) -> dict[str, object]:
    """Translate a `postgresql+psycopg://…` SQLAlchemy URL into psycopg kwargs.

    Query-string options (`sslmode`, `connect_timeout`, `target_session_attrs`, …)
    are preserved — managed Postgres commonly requires them, and dropping them
    silently would break a valid `DATABASE_URL`.
    """
    url = make_url(sqlalchemy_url)
    kwargs: dict[str, object] = {
        "host": url.host,
        "port": url.port,
        "user": url.username,
        "password": url.password,
        "dbname": url.database,
    }
    kwargs.update(url.query)
    return kwargs


async def get_connection() -> AsyncIterator[AsyncConnection]:
    """Yield a request-scoped connection; commit on success, roll back on error."""
    conn = await connect(autocommit=False)
    try:
        yield conn
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()
