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

from psycopg import AsyncConnection
from sqlalchemy.engine import make_url

from story_forge.config import settings


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
    conn = await AsyncConnection.connect(
        autocommit=False,
        **libpq_kwargs(settings.database_url),  # type: ignore[arg-type]
    )
    try:
        yield conn
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()
