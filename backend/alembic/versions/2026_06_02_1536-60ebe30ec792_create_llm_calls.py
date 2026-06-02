"""create llm_calls

Revision ID: 60ebe30ec792
Revises: bdfb9ec11d7e
Create Date: 2026-06-02 15:36:15.494487

Creates the §6.6 cost ledger: one row per LLM call — including refusals and
failures — so daily / project / per-task-type spend can be aggregated and the
trail explains why a batch stopped. Tier/provider/model are recorded as written
by the router from the serving adapter (system-derived, INV-7), never echoed from
the caller.

Raw SQL (`op.execute`) to match the existing schema migration. Token counts are
nullable (free tiers, or a call that failed before returning usage); `cost_estimate`
is nullable (free tiers); `gpu_seconds` is nullable (only Ollama Cloud bills it).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "60ebe30ec792"  # pragma: allowlist secret  (alembic revision id, not a secret)
down_revision: str | Sequence[str] | None = "bdfb9ec11d7e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE llm_calls (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at    timestamptz NOT NULL DEFAULT now(),
            tier          text NOT NULL,
            provider      text NOT NULL,
            model         text,
            task_type     text NOT NULL,
            outcome       text NOT NULL,
            input_tokens  integer,
            output_tokens integer,
            gpu_seconds   double precision,
            cost_estimate double precision
        )
        """
    )
    # The budget gate and the dashboard both filter by day, so index the time axis.
    op.execute("CREATE INDEX ix_llm_calls_created_at ON llm_calls (created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS llm_calls")
