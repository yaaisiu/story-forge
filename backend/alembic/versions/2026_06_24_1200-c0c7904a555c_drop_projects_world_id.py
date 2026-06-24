"""drop vestigial projects.world_id

Revision ID: c0c7904a555c
Revises: d5971b7919ab
Create Date: 2026-06-24 12:00:00.000000

M4 multi-story (DM-MS-5). `projects.world_id` was an always-null placeholder for a
world-graph parent: a shared graph spanning several projects, with a `worlds` table to
come later. The PoC cut the world graph (§3.6 → backlog, owner S44), so there is no
`worlds` table and the column never held a value. It is dead weight — drop it and its
plumbing across the domain models, the two repos, and the §3.4 GraphNode docstring.

Pure deletion; no data migration (every value is NULL). Downgrade re-adds the column as
the nullable `uuid` it was, so a full down/up cycle restores the original schema.

Raw SQL (`op.execute`) to match the existing schema migrations.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c0c7904a555c"  # pragma: allowlist secret  (alembic revision id, not a secret)
down_revision: str | Sequence[str] | None = "d5971b7919ab"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE projects DROP COLUMN world_id")


def downgrade() -> None:
    op.execute("ALTER TABLE projects ADD COLUMN world_id uuid")
