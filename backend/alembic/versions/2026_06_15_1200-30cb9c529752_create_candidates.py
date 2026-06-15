"""create candidates staging + decisions + paragraph_processed marker

Revision ID: 30cb9c529752
Revises: cf0a36d67a73
Create Date: 2026-06-15 12:00:00.000000

M3.S4a intercept-before-write (DM6, ADR 0004). Three tables back the new write path:

- `candidates` — the staging store. Each extracted candidate persists here with the §3.3
  cascade's proposal (NEW vs a MERGE `target_entity_id`, the stage reached, confidence,
  the judge's reasoning, and the top-3 `alternatives`) + its ±200-char `context` and that
  context's `context_embedding vector(768)`. `status` is the persisted
  `[[candidate-lifecycle]]` state; nothing is written to Neo4j until a human accepts.
- `candidate_decisions` — append-only accept/reject evidence (INV-3 reversibility, DM-S4a-4).
  A focused decisions log, deliberately *not* the §4.2 `edit_history` text-edit dataset
  (different shape, different export — deferred to the editing milestone).
- `paragraph_processed` — the resume marker (DM-S4a-3). A row means the paragraph's candidates
  are staged, so a re-run skips it (even a zero-candidate paragraph). Carries the paragraph's
  raw relation proposals as JSONB; the relation graph-write + re-point is deferred to S4b.

`target_entity_id` references a **Neo4j** id and so carries no Postgres FK (the OQ-1 cross-store
seam). The `vector` type is already enabled (initial migration). No ANN index on
`context_embedding` at PoC: the cascade matches against *accepted-entity* vectors, so a staged
candidate's vector is write-mostly. Raw SQL (`op.execute`) to match the existing migrations.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "30cb9c529752"  # pragma: allowlist secret  (alembic revision id, not a secret)
down_revision: str | Sequence[str] | None = "cf0a36d67a73"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE candidates (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id        uuid NOT NULL,
            story_id          uuid NOT NULL,
            paragraph_id      uuid NOT NULL REFERENCES paragraphs (id) ON DELETE CASCADE,
            candidate_name    text NOT NULL,
            type              text NOT NULL,
            properties        jsonb NOT NULL DEFAULT '{}',
            context           text NOT NULL,
            context_embedding vector(768),
            proposal          text NOT NULL,
            target_entity_id  uuid,
            stage_reached     integer NOT NULL,
            confidence        double precision,
            reasoning         text,
            alternatives      jsonb NOT NULL DEFAULT '[]',
            status            text NOT NULL DEFAULT 'review-queued',
            created_at        timestamptz NOT NULL DEFAULT now(),
            updated_at        timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # The review queue reads a story's still-pending candidates (status filter).
    op.execute("CREATE INDEX ix_candidates_story_status ON candidates (story_id, status)")

    op.execute(
        """
        CREATE TABLE candidate_decisions (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id     uuid NOT NULL REFERENCES candidates (id) ON DELETE CASCADE,
            decision         text NOT NULL,
            target_entity_id uuid,
            actor            text NOT NULL DEFAULT 'human',
            shown_proposal   jsonb NOT NULL DEFAULT '{}',
            created_at       timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_candidate_decisions_candidate_id ON candidate_decisions (candidate_id)"
    )

    op.execute(
        """
        CREATE TABLE paragraph_processed (
            paragraph_id uuid PRIMARY KEY REFERENCES paragraphs (id) ON DELETE CASCADE,
            story_id     uuid NOT NULL,
            relations    jsonb NOT NULL DEFAULT '[]',
            processed_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS paragraph_processed")
    op.execute("DROP TABLE IF EXISTS candidate_decisions")
    op.execute("DROP TABLE IF EXISTS candidates")
