"""Integration: the dismissed-duplicate-pair store against the throwaway test DB (S4a).

Exercises the real `PostgresDuplicateDismissalStore` (self-managed autocommit connection,
mirroring `PostgresCandidateStore`) against the migrated `story_forge_test` DB. Each test uses
a fresh `project_id` (uuid4) for isolation; the session DB is dropped at teardown, so no manual
cleanup is needed. `db_conn` is requested only to guarantee the schema is migrated.
"""

from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from story_forge.adapters.db import libpq_kwargs
from story_forge.adapters.postgres_duplicate_dismissal_store import (
    PostgresDuplicateDismissalStore,
)
from story_forge.config import settings
from story_forge.domain.duplicate_clusters import dismissal_pair_id

pytestmark = pytest.mark.integration


def _store() -> PostgresDuplicateDismissalStore:
    return PostgresDuplicateDismissalStore(libpq_kwargs(settings.test_database_url))


async def test_insert_then_list_contains_pair(db_conn: psycopg.AsyncConnection) -> None:
    store = _store()
    project, a, b = uuid4(), uuid4(), uuid4()
    await store.insert(project, a, b)
    assert dismissal_pair_id(project, a, b) in await store.list_pair_ids(project)


async def test_insert_is_order_independent_and_idempotent(
    db_conn: psycopg.AsyncConnection,
) -> None:
    store = _store()
    project, a, b = uuid4(), uuid4(), uuid4()
    await store.insert(project, a, b)
    await store.insert(project, b, a)  # same unordered pair, reversed — no duplicate row
    ids = await store.list_pair_ids(project)
    assert ids == {dismissal_pair_id(project, a, b)}


async def test_list_is_project_scoped(db_conn: psycopg.AsyncConnection) -> None:
    store = _store()
    project, other, a, b = uuid4(), uuid4(), uuid4(), uuid4()
    await store.insert(project, a, b)
    assert await store.list_pair_ids(other) == set()


async def test_delete_undismisses(db_conn: psycopg.AsyncConnection) -> None:
    store = _store()
    project, a, b = uuid4(), uuid4(), uuid4()
    await store.insert(project, a, b)
    await store.delete(project, b, a)  # order-independent un-dismiss
    assert await store.list_pair_ids(project) == set()
    # Deleting a non-dismissed pair is a silent no-op.
    await store.delete(project, uuid4(), uuid4())
