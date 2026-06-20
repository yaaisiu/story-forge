"""Integration: the grouped-operation write on `PostgresEditStore` (M4.S3b, DM-S3b-1).

A merge fans out into many `graph_edits` rows that undo (be2) must reverse as one unit, so they
share an `operation_id`, carry a per-operation `seq`, and a human-readable `description` + `op_kind`
+ `project_id`. This pins that `record_operation` lands every row in one transaction with the
grouping columns set, that `ON CONFLICT (id) DO NOTHING` makes a re-record idempotent (the
crash-retry contract), and that the new columns exist (the grouping migration applied). No Neo4j —
`graph_edits` is a soft-keyed Postgres table; the test DB is dropped at session end.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from psycopg.rows import dict_row

from story_forge.adapters.db import libpq_kwargs
from story_forge.adapters.postgres_edit_store import PostgresEditStore
from story_forge.config import settings
from story_forge.domain.graph_edit import GraphEdit

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def store(_migrated_test_db: None) -> AsyncIterator[PostgresEditStore]:
    conninfo = libpq_kwargs(settings.test_database_url)
    async with await psycopg.AsyncConnection.connect(autocommit=True, **conninfo) as conn:  # type: ignore[arg-type]
        await conn.execute("DELETE FROM graph_edits")
    yield PostgresEditStore(conninfo)


async def _operation_rows(operation_id: UUID) -> list[dict[str, object]]:
    conninfo = libpq_kwargs(settings.test_database_url)
    async with await psycopg.AsyncConnection.connect(autocommit=True, **conninfo) as conn:  # type: ignore[arg-type]
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            "SELECT seq, op_kind, description, project_id, op, before, after, undone_at "
            "FROM graph_edits WHERE operation_id = %s ORDER BY seq",
            (operation_id,),
        )
        return await cur.fetchall()


def _row(operation_id: UUID, project_id: UUID, seq: int, **kw: object) -> GraphEdit:
    base: dict[str, object] = {
        "target_id": uuid4(),
        "target_kind": "relation",
        "op": "repoint_relation",
        "operation_id": operation_id,
        "seq": seq,
        "op_kind": "merge",
        "description": "merged Broniek into Bronisław",
        "project_id": project_id,
    }
    base.update(kw)
    return GraphEdit(**base)  # type: ignore[arg-type]


async def test_record_operation_lands_every_row_with_grouping_columns(
    store: PostgresEditStore,
) -> None:
    operation_id, project_id = uuid4(), uuid4()
    rows = [
        _row(operation_id, project_id, 0, op="merge_consolidate", target_kind="entity"),
        _row(operation_id, project_id, 1, before={"subject_id": "old"}),
        _row(operation_id, project_id, 2, before={"subject_id": "old2"}),
    ]
    await store.record_operation(rows)

    persisted = await _operation_rows(operation_id)
    assert [r["seq"] for r in persisted] == [0, 1, 2]  # grouped + ordered
    assert {r["op_kind"] for r in persisted} == {"merge"}
    assert {r["description"] for r in persisted} == {"merged Broniek into Bronisław"}
    assert {r["project_id"] for r in persisted} == {project_id}
    assert all(r["undone_at"] is None for r in persisted)  # a freshly-recorded op is live


async def test_record_operation_is_idempotent_on_re_record(store: PostgresEditStore) -> None:
    operation_id, project_id = uuid4(), uuid4()
    rows = [_row(operation_id, project_id, 0), _row(operation_id, project_id, 1)]
    await store.record_operation(rows)
    await store.record_operation(rows)  # a crash-retry re-derives the same row ids

    assert len(await _operation_rows(operation_id)) == 2  # ON CONFLICT DO NOTHING — no duplicates


async def test_record_operation_empty_is_a_noop(store: PostgresEditStore) -> None:
    await store.record_operation([])  # must not error / open a doomed transaction
