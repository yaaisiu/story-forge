"""add graph_edit grouping

Revision ID: 285403049b2b
Revises: 3d760a15b9f9
Create Date: 2026-06-20 20:33:35.971954

M4.S3b graph mutations (merge · delete · undo). A single author action now fans out into many
graph_edits rows that must be reversed as **one** unit (a merge re-points N edges, re-points M
mentions, folds B into A, deletes B), so the per-row S3a table gains **grouping**:

- `operation_id` + `seq` — the rows of one operation share an id and carry a per-operation
  sequence, so undo replays them as a single compensating transaction (DM-S3b-1).
- `op_kind` — names the grouped operation (`'merge'`; later `'delete'`/`'undo'`).
- `description` — the human-readable label the undo affordance previews before acting
  (DM-S3b-1, "see what I undo").
- `project_id` — scopes the undo stack per project (the read path `latest_live_operation`,
  M4.S3b-be2, filters on it).
- `undone_at` — NULL while live; set when the operation is undone (the `applied → undone`
  graph-operation state machine, consumed by undo in M4.S3b-be2).

All columns are **nullable** — existing S3a rows stay valid with no backfill (`operation_id IS
NULL` = "its own singleton operation"); merge writes always populate them. The grouping write
(`record_operation`) lands in be1; the undo read path (`latest_live_operation` /
`mark_operation_undone`, which `undone_at` serves) lands in be2 — the columns are added together
so the schema is one-and-done. Raw SQL (`op.execute`) to match the existing migrations.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "285403049b2b"  # pragma: allowlist secret  (alembic revision id, not a secret)
down_revision: str | Sequence[str] | None = "3d760a15b9f9"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE graph_edits ADD COLUMN operation_id uuid")
    op.execute("ALTER TABLE graph_edits ADD COLUMN seq integer")
    op.execute("ALTER TABLE graph_edits ADD COLUMN op_kind text")
    op.execute("ALTER TABLE graph_edits ADD COLUMN description text")
    op.execute("ALTER TABLE graph_edits ADD COLUMN project_id uuid")
    op.execute("ALTER TABLE graph_edits ADD COLUMN undone_at timestamptz")
    # Replay an operation's rows in order.
    op.execute("CREATE INDEX ix_graph_edits_operation ON graph_edits (operation_id, seq)")
    # Find the newest still-live operation in a project (the undo target, be2).
    op.execute(
        "CREATE INDEX ix_graph_edits_project_live "
        "ON graph_edits (project_id, undone_at, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_graph_edits_project_live")
    op.execute("DROP INDEX IF EXISTS ix_graph_edits_operation")
    op.execute("ALTER TABLE graph_edits DROP COLUMN IF EXISTS undone_at")
    op.execute("ALTER TABLE graph_edits DROP COLUMN IF EXISTS project_id")
    op.execute("ALTER TABLE graph_edits DROP COLUMN IF EXISTS description")
    op.execute("ALTER TABLE graph_edits DROP COLUMN IF EXISTS op_kind")
    op.execute("ALTER TABLE graph_edits DROP COLUMN IF EXISTS seq")
    op.execute("ALTER TABLE graph_edits DROP COLUMN IF EXISTS operation_id")
