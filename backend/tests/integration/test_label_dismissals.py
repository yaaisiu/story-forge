"""Integration: the dismissed-label-pair store against the throwaway test DB (S6a).

Exercises the real `PostgresLabelDismissalStore` (self-managed autocommit connection,
mirroring `PostgresDuplicateDismissalStore`) against the migrated `story_forge_test` DB. Each
test uses a fresh `project_id` (uuid4) for isolation; the session DB is dropped at teardown, so
no manual cleanup is needed. `db_conn` is requested only to guarantee the schema is migrated.
"""

from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from story_forge.adapters.db import libpq_kwargs
from story_forge.adapters.postgres_label_dismissal_store import PostgresLabelDismissalStore
from story_forge.config import settings
from story_forge.domain.label_synonyms import label_dismissal_id

pytestmark = pytest.mark.integration


def _store() -> PostgresLabelDismissalStore:
    return PostgresLabelDismissalStore(libpq_kwargs(settings.test_database_url))


async def test_insert_then_list_contains_pair(db_conn: psycopg.AsyncConnection) -> None:
    store = _store()
    project = uuid4()
    await store.insert(project, "type", "PERSON", "Person")
    assert label_dismissal_id(project, "type", "PERSON", "Person") in await store.list_pair_ids(
        project
    )


async def test_insert_is_order_independent_and_idempotent(
    db_conn: psycopg.AsyncConnection,
) -> None:
    store = _store()
    project = uuid4()
    await store.insert(project, "type", "PERSON", "Person")
    await store.insert(project, "type", "Person", "PERSON")  # reversed — no duplicate row
    ids = await store.list_pair_ids(project)
    assert ids == {label_dismissal_id(project, "type", "PERSON", "Person")}


async def test_surface_scoped(db_conn: psycopg.AsyncConnection) -> None:
    # A dismissed type pair must not suppress an identically-spelled predicate pair.
    store = _store()
    project = uuid4()
    await store.insert(project, "type", "OWNS", "owns")
    ids = await store.list_pair_ids(project)
    assert label_dismissal_id(project, "type", "OWNS", "owns") in ids
    assert label_dismissal_id(project, "predicate", "OWNS", "owns") not in ids


async def test_list_is_project_scoped(db_conn: psycopg.AsyncConnection) -> None:
    store = _store()
    project, other = uuid4(), uuid4()
    await store.insert(project, "type", "PERSON", "Person")
    assert await store.list_pair_ids(other) == set()


async def test_delete_undismisses(db_conn: psycopg.AsyncConnection) -> None:
    store = _store()
    project = uuid4()
    await store.insert(project, "type", "PERSON", "Person")
    await store.delete(project, "type", "Person", "PERSON")  # order-independent un-dismiss
    assert await store.list_pair_ids(project) == set()
    # Deleting a non-dismissed pair is a silent no-op.
    await store.delete(project, "type", "FOO", "BAR")
