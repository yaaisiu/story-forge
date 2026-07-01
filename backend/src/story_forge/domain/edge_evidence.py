"""Edge evidence — the read-side [[provenance]] of a committed graph edge (graph-quality §3 S3).

A committed relation's source paragraph(s) + the LLM's supporting quote survive commit in the
Postgres `staged_relations` table as `status='written'` rows, keyed by the content-addressed
`edge_id`. The *same fact* asserted in N paragraphs collapses to one edge but keeps N rows, so an
edge's evidence is **one-to-many** (`build_edge_evidence` never assumes a single row).

This module is the pure assembly boundary (no I/O): given the written rows and a paragraph-id →
text lookup the caller resolved, it builds the `EdgeEvidence` the BFF route returns. A tapped edge
with *zero* rows is a valid case — a manually-added edge (the `EntityEditService` write path stages
no relation) — and yields an empty `source_provenance` (the client renders "added manually").
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from pydantic import BaseModel

from story_forge.domain.candidates import StagedRelation


class EdgeEvidenceSource(BaseModel):
    """One source of an edge: the paragraph it was asserted in + the model's supporting quote.

    `evidence_quote` is the LLM-provided string (may paraphrase — a soft flag, not an offset), so
    the client shows it *alongside* the paragraph text rather than asserting a character offset.
    """

    paragraph_id: UUID
    paragraph_text: str
    evidence_quote: str | None


class EdgeEvidence(BaseModel):
    """All recorded provenance behind one graph edge — its predicate + every source paragraph."""

    predicate: str | None
    source_provenance: list[EdgeEvidenceSource]


def build_edge_evidence(
    rows: list[StagedRelation], paragraph_texts: Mapping[UUID, str]
) -> EdgeEvidence:
    """Assemble an edge's evidence from its `written` rows + a resolved paragraph-text lookup.

    Pure: the caller does the I/O (fetch the rows by `edge_id`, fetch each paragraph's text) and
    passes the results in. The predicate is taken from the rows (all rows for one content-addressed
    edge share the resolved triple, so the predicate is stable); a zero-row edge has no predicate
    and an empty provenance list. A paragraph missing from the lookup falls back to an empty string
    (defensive — the `paragraph_id` FK cascades, so a written row's paragraph normally exists).
    """
    predicate = rows[0].predicate if rows else None
    sources = [
        EdgeEvidenceSource(
            paragraph_id=row.paragraph_id,
            paragraph_text=paragraph_texts.get(row.paragraph_id, ""),
            evidence_quote=row.evidence_quote,
        )
        for row in rows
    ]
    return EdgeEvidence(predicate=predicate, source_provenance=sources)
