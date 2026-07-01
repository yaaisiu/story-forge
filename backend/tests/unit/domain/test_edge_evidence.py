"""Unit tests for `build_edge_evidence` — the pure edge-provenance assembly (graph-quality §3 S3).

No DB: the caller resolves the written rows + a paragraph-text lookup; this proves the pure mapping
(predicate from the rows, one row per source, one-to-many, the zero-row "manually added" case, and
the defensive missing-paragraph fallback).
"""

from __future__ import annotations

from uuid import uuid4

from story_forge.domain.candidates import StagedRelation
from story_forge.domain.edge_evidence import build_edge_evidence


def _written(*, story_id, edge_id, paragraph_id, quote) -> StagedRelation:
    return StagedRelation(
        id=uuid4(),
        story_id=story_id,
        paragraph_id=paragraph_id,
        subject="Janek",
        predicate="KNOWS",
        object="Mokosz",
        evidence_quote=quote,
        edge_id=edge_id,
        status="written",
    )


def test_no_rows_yields_null_predicate_and_empty_provenance() -> None:
    evidence = build_edge_evidence([], {})
    assert evidence.predicate is None
    assert evidence.source_provenance == []


def test_predicate_comes_from_the_rows() -> None:
    story_id, edge_id, para = uuid4(), uuid4(), uuid4()
    row = _written(story_id=story_id, edge_id=edge_id, paragraph_id=para, quote="Janek knew her.")
    evidence = build_edge_evidence([row], {para: "Janek knew Mokosz well."})
    assert evidence.predicate == "KNOWS"


def test_one_to_many_keeps_every_source_paragraph_and_quote() -> None:
    story_id, edge_id = uuid4(), uuid4()
    p1, p2 = uuid4(), uuid4()
    rows = [
        _written(story_id=story_id, edge_id=edge_id, paragraph_id=p1, quote="quote one"),
        _written(story_id=story_id, edge_id=edge_id, paragraph_id=p2, quote="quote two"),
    ]
    texts = {p1: "paragraph one text", p2: "paragraph two text"}

    evidence = build_edge_evidence(rows, texts)

    assert [
        (s.paragraph_id, s.paragraph_text, s.evidence_quote) for s in evidence.source_provenance
    ] == [
        (p1, "paragraph one text", "quote one"),
        (p2, "paragraph two text", "quote two"),
    ]


def test_missing_paragraph_text_falls_back_to_empty_string() -> None:
    story_id, edge_id, para = uuid4(), uuid4(), uuid4()
    row = _written(story_id=story_id, edge_id=edge_id, paragraph_id=para, quote=None)
    evidence = build_edge_evidence([row], {})  # lookup empty on purpose
    assert evidence.source_provenance[0].paragraph_text == ""
    assert evidence.source_provenance[0].evidence_quote is None
