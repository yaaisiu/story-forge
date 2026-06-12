"""Shared pytest fixtures.

The integration suite runs against a throwaway database (`story_forge_test` by
default, see `settings.test_database_url`). One session-scoped fixture owns its
whole lifecycle: it connects to the server's maintenance database, drops any
leftover test DB, creates a fresh one, runs `alembic upgrade head` to build the
schema, yields for the duration of the test session, then drops it again. Dev
data in the main `storyforge` database is never touched.

Unit tests that never request `db_conn` (or the migration fixture) trigger none
of this, so `pytest -m "not integration"` needs no Postgres at all.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import psycopg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from story_forge.adapters.db import connect, libpq_kwargs
from story_forge.config import settings

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _assert_disposable_test_db(test_db_name: object) -> None:
    """Refuse to run if `TEST_DATABASE_URL` could destroy real data.

    The session fixture `DROP DATABASE ... WITH (FORCE)` on this name, so a
    misconfigured env (pointing at the dev/app DB) would wipe it at test startup.
    Two cheap guards: it must not be the app database, and it must follow the
    `*test*` naming convention.
    """
    if not isinstance(test_db_name, str) or not test_db_name:
        raise RuntimeError("TEST_DATABASE_URL has no database name")
    app_db_name = make_url(settings.database_url).database
    if test_db_name == app_db_name:
        raise RuntimeError(
            f"refusing to run integration tests: TEST_DATABASE_URL names the app "
            f"database ({test_db_name!r}); it must be a separate throwaway DB"
        )
    if "test" not in test_db_name.lower():
        raise RuntimeError(
            f"refusing to DROP {test_db_name!r}: a disposable test DB name must "
            f"contain 'test' (e.g. story_forge_test)"
        )


def _build_alembic_cfg() -> Config:
    """Alembic Config pinned to the test DB, with absolute paths so it runs
    correctly regardless of the working directory pytest was invoked from."""
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.test_database_url)
    return cfg


@pytest.fixture(scope="session")
def alembic_cfg() -> Config:
    """The migration config aimed at the test database (read-only to consumers)."""
    return _build_alembic_cfg()


@pytest.fixture(scope="session")
def _migrated_test_db() -> Iterator[None]:
    """Create the test DB, migrate it to head, drop it when the session ends."""
    params = libpq_kwargs(settings.test_database_url)
    test_db_name = params["dbname"]
    _assert_disposable_test_db(test_db_name)
    admin_params = {**params, "dbname": "postgres"}

    def _drop_and_create() -> None:
        with psycopg.connect(autocommit=True, **admin_params) as admin:  # type: ignore[arg-type]
            # Identifiers can't be parameterised; the name comes from our own
            # config, not user input, and make_url has already validated it.
            admin.execute(f'DROP DATABASE IF EXISTS "{test_db_name}" WITH (FORCE)')
            admin.execute(f'CREATE DATABASE "{test_db_name}"')

    _drop_and_create()

    command.upgrade(_build_alembic_cfg(), "head")

    yield

    with psycopg.connect(autocommit=True, **admin_params) as admin:  # type: ignore[arg-type]
        admin.execute(f'DROP DATABASE IF EXISTS "{test_db_name}" WITH (FORCE)')


@pytest_asyncio.fixture
async def db_conn(_migrated_test_db: None) -> AsyncIterator[psycopg.AsyncConnection]:
    """An async connection to the migrated test DB, rolled back after each test.

    Each test runs inside a transaction that is rolled back on teardown, so tests
    stay isolated without re-creating the schema between them.
    """
    # Via db.connect so the pgvector type is registered on the test connection too —
    # the embedding-column reads/writes need the loader/dumper (same as the app).
    conn = await connect(libpq_kwargs(settings.test_database_url), autocommit=False)
    try:
        yield conn
        await conn.rollback()
    finally:
        await conn.close()
