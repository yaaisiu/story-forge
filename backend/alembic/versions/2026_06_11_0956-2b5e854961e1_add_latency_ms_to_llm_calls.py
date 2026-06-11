"""add latency_ms to llm_calls

Revision ID: 2b5e854961e1
Revises: d721987b4168
Create Date: 2026-06-11 09:56:47.050105

Adds the §6.6 per-call latency column (OQ-9, resolved 2026-06-11). `latency_ms`
is the wall-clock duration the router measured around the provider call, in
milliseconds; nullable because a call refused before dispatch (the fail-closed
budget gate) never timed a provider. The §8.5 agent activity panel surfaces it.

Raw SQL (`op.execute`) to match the existing schema migrations.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2b5e854961e1"  # pragma: allowlist secret  (alembic revision id, not a secret)
down_revision: str | Sequence[str] | None = "d721987b4168"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE llm_calls ADD COLUMN latency_ms integer")


def downgrade() -> None:
    op.execute("ALTER TABLE llm_calls DROP COLUMN IF EXISTS latency_ms")
