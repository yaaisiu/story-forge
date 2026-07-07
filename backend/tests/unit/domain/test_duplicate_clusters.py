"""Unit tests for the pure duplicate self-join (domain/duplicate_clusters).

Graph-quality S4a. The self-join re-points the §3.3 matcher inward over an
`AcceptedSnapshot`: it *suggests* likely-duplicate entity pairs, never merges. These
tests pin the decided behaviour (register DM-CD-1/2, INV-4):
- pairwise, ranked strongest-first, deterministic;
- name OR embedding qualifies; type never filters (only a soft tiebreak);
- a vector-less entity falls back to name-only and never crashes.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from story_forge.domain.candidates import AcceptedSnapshot
from story_forge.domain.duplicate_clusters import (
    DuplicateSuggestion,
    dismissal_pair_id,
    suggest_duplicate_pairs,
)
from story_forge.domain.graph import GraphEntity

_PROJECT = uuid4()


def _entity(
    *,
    name_pl: str | None = None,
    name_en: str | None = None,
    aliases: list[str] | None = None,
    type_: str = "Person",
    entity_id: UUID | None = None,
) -> GraphEntity:
    return GraphEntity(
        id=entity_id or uuid4(),
        type=type_,
        canonical_name_pl=name_pl,
        canonical_name_en=name_en,
        aliases=aliases or [],
        project_id=_PROJECT,
    )


def test_empty_snapshot_yields_nothing() -> None:
    assert suggest_duplicate_pairs(AcceptedSnapshot(), name_floor=60.0, cosine_floor=0.85) == []


def test_identical_names_are_suggested_above_floor() -> None:
    a = _entity(name_pl="Bronek")
    b = _entity(name_pl="Bronek")
    snap = AcceptedSnapshot(entities=[a, b])
    out = suggest_duplicate_pairs(snap, name_floor=60.0, cosine_floor=0.85)
    assert len(out) == 1
    assert {out[0].entity_id_lo, out[0].entity_id_hi} == {a.id, b.id}
    assert out[0].name_score == 100.0
    assert out[0].cosine_score is None  # no mention vectors → name-only


def test_below_floor_is_not_suggested() -> None:
    snap = AcceptedSnapshot(entities=[_entity(name_pl="Aleksander"), _entity(name_pl="Zofia")])
    assert suggest_duplicate_pairs(snap, name_floor=60.0, cosine_floor=0.85) == []


def test_vectorless_entity_falls_back_to_name_only_without_crashing() -> None:
    a = _entity(name_pl="Katarzyna", entity_id=uuid4())
    b = _entity(name_pl="Katarzyna", entity_id=uuid4())
    # a has a vector, b has none → cosine rung skipped, name rung still qualifies.
    snap = AcceptedSnapshot(entities=[a, b], mention_vectors={a.id: [[1.0, 0.0, 0.0]]})
    out = suggest_duplicate_pairs(snap, name_floor=60.0, cosine_floor=0.85)
    assert len(out) == 1
    assert out[0].cosine_score is None


def test_all_zero_vector_is_skipped_not_raised() -> None:
    a = _entity(name_pl="Marek")
    b = _entity(name_pl="Marek")
    snap = AcceptedSnapshot(
        entities=[a, b],
        mention_vectors={a.id: [[0.0, 0.0]], b.id: [[0.0, 0.0]]},
    )
    out = suggest_duplicate_pairs(snap, name_floor=60.0, cosine_floor=0.85)
    assert len(out) == 1  # name still qualifies
    assert out[0].cosine_score is None  # zero-magnitude vectors skipped, no ValueError


def test_embedding_qualifies_pair_names_miss() -> None:
    # Different surface names (below the name floor) but near-identical mention vectors.
    a = _entity(name_pl="Statek", entity_id=uuid4())
    b = _entity(name_pl="Okręt", entity_id=uuid4())
    snap = AcceptedSnapshot(
        entities=[a, b],
        mention_vectors={a.id: [[1.0, 0.0]], b.id: [[1.0, 0.0]]},
    )
    out = suggest_duplicate_pairs(snap, name_floor=60.0, cosine_floor=0.85)
    assert len(out) == 1
    assert out[0].cosine_score == 1.0


def test_type_is_soft_never_a_filter() -> None:
    # Two same-named entities the over-extractor typed differently must still be suggested
    # (INV-4: type never a hard filter — the very case S4 exists to catch).
    a = _entity(name_pl="Bronek", type_="Person")
    b = _entity(name_pl="Bronek", type_="Organization")
    snap = AcceptedSnapshot(entities=[a, b])
    assert len(suggest_duplicate_pairs(snap, name_floor=60.0, cosine_floor=0.85)) == 1


def test_ranked_strongest_first_and_deterministic() -> None:
    strong_a = _entity(name_pl="Aleksandra Nowak")
    strong_b = _entity(name_pl="Aleksandra Nowak")  # exact → 100
    weak_a = _entity(name_pl="Piotr Kowalski")
    weak_b = _entity(name_pl="Piotr Kowal")  # partial → lower
    snap = AcceptedSnapshot(entities=[weak_a, weak_b, strong_a, strong_b])
    out = suggest_duplicate_pairs(snap, name_floor=60.0, cosine_floor=0.85)
    assert len(out) == 2
    assert out[0].combined_score >= out[1].combined_score
    assert {out[0].entity_id_lo, out[0].entity_id_hi} == {strong_a.id, strong_b.id}
    # Deterministic: same input → same order.
    again = suggest_duplicate_pairs(snap, name_floor=60.0, cosine_floor=0.85)
    assert [(s.entity_id_lo, s.entity_id_hi) for s in out] == [
        (s.entity_id_lo, s.entity_id_hi) for s in again
    ]


def test_dismissal_pair_id_is_order_independent() -> None:
    a, b = uuid4(), uuid4()
    assert dismissal_pair_id(_PROJECT, a, b) == dismissal_pair_id(_PROJECT, b, a)
    # Different project → different id (the pair-store is project-scoped).
    assert dismissal_pair_id(uuid4(), a, b) != dismissal_pair_id(_PROJECT, a, b)


def test_suggestion_pair_ids_are_canonically_ordered() -> None:
    a = _entity(name_pl="Ewa", entity_id=uuid4())
    b = _entity(name_pl="Ewa", entity_id=uuid4())
    snap = AcceptedSnapshot(entities=[a, b])
    out = suggest_duplicate_pairs(snap, name_floor=60.0, cosine_floor=0.85)
    assert isinstance(out[0], DuplicateSuggestion)
    assert out[0].entity_id_lo <= out[0].entity_id_hi
