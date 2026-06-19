"""Graph-edit evidence model (spec §11 reversibility / INV-3; M4.S3a, DM-S3a-2).

Append-only before→after record of a human edit to committed graph state — the graph-edit twin
of `CandidateDecision`. One shape covers both node-field edits and edge add/remove:
`target_kind` discriminates, `op` names the operation, and `before`/`after` hold the JSON images
(`before` is `None` for an add, `after` `None` for a remove). It is the substrate for INV-3 undo
and for the correction-as-training-data flywheel — *not* the §4.2 `edit_history` text-edit
dataset (which stays deferred).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(UTC)


GraphEditKind = Literal["entity", "relation"]


class GraphEdit(BaseModel):
    """One human edit of a committed entity or edge (INV-3 reversibility, DM-S3a-2).

    `target_id` is a **Neo4j** id (entity id or edge id) — a soft cross-store key, no FK.
    `before`/`after` carry the changed state: for an entity field edit, the changed-fields maps;
    for an edge add, only `after`; for an edge remove, only `before`.
    """

    id: UUID = Field(default_factory=uuid4)
    target_id: UUID
    target_kind: GraphEditKind
    op: str
    before: dict[str, object] | None = None
    after: dict[str, object] | None = None
    actor: str = "human"
    created_at: datetime = Field(default_factory=_now)
