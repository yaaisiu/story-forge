"""PostgresMentionStore — the `entity_mentions` writer + resume checkpoint (§6.4).

Like `PostgresCostStore`, each operation opens its own short-lived **autocommit**
connection rather than sharing a request transaction. That is what makes the batch
ingest resumable (OQ-2): each paragraph's mention is committed as it is written, so a
mid-batch pause (budget/quota) or crash leaves a durable record of which paragraphs
are already done. Sharing the request transaction would roll all of them back on the
pause, and the re-run would redo everything — duplicating nodes under the no-dedupe
contract (INV-8).
"""

from __future__ import annotations

from uuid import UUID

import psycopg

from story_forge.adapters import postgres_repo
from story_forge.adapters.db import connect, libpq_kwargs
from story_forge.config import settings
from story_forge.domain.models import EntityMention


class PostgresMentionStore:
    """`MentionStore` backed by the `entity_mentions` table."""

    def __init__(self, conninfo: dict[str, object] | None = None) -> None:
        self._conninfo = conninfo if conninfo is not None else libpq_kwargs(settings.database_url)

    async def _connect(self) -> psycopg.AsyncConnection:
        # Via db.connect so the pgvector type is registered — entity_mentions now has an
        # `embedding vector(768)` column, so even the autocommit checkpoint connection
        # needs the dumper/loader (a NULL write today, a real vector once M3.S4 wires it).
        return await connect(self._conninfo, autocommit=True)

    async def add_mention(self, mention: EntityMention) -> None:
        # Reuse the single INSERT in `postgres_repo` so the table write lives in one
        # place; only the *connection* differs — its own autocommit one (durable,
        # resume checkpoint) rather than a caller's request transaction.
        async with await self._connect() as conn:
            await postgres_repo.insert_entity_mention(conn, mention)

    async def paragraphs_with_mentions(self, paragraph_ids: list[UUID]) -> set[UUID]:
        """Which of `paragraph_ids` already carry ≥1 mention — the resume checkpoint."""
        if not paragraph_ids:
            return set()
        async with await self._connect() as conn:
            cur = await conn.execute(
                "SELECT DISTINCT paragraph_id FROM entity_mentions WHERE paragraph_id = ANY(%s)",
                (paragraph_ids,),
            )
            rows = await cur.fetchall()
        return {row[0] for row in rows}
