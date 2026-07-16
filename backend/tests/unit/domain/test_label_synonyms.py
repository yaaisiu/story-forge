"""Unit tests for the pure label-synonym self-join (domain/label_synonyms).

Graph-quality S6a. The self-join is the S4 duplicate matcher turned on a vocabulary of
label strings: it *suggests* synonymous predicate / entity-type names, never renames.
These tests pin the decided behaviour (register DM-NN-1/2, INV-4):
- two rungs — normalised name OR label-string embedding — recall-first, deterministic;
- the fuzzy rung is case-/separator-folded so `PERSON`/`Person`, `GROUP`/`group` qualify;
- the embedding rung carries token-disjoint synonyms the fuzzy rung misses;
- a label with no usable embedding falls back to name-only and never crashes;
- the dismissal id is order-, project-, and surface-independent.
"""

from __future__ import annotations

from uuid import uuid4

from story_forge.domain.label_synonyms import (
    LabelSynonymSuggestion,
    LabelVocabularyEntry,
    label_dismissal_id,
    suggest_label_synonyms,
)

_PROJECT = uuid4()


def _entry(
    label: str, *, count: int = 1, embedding: list[float] | None = None
) -> LabelVocabularyEntry:
    return LabelVocabularyEntry(label=label, count=count, embedding=embedding)


def test_empty_vocabulary_yields_nothing() -> None:
    assert suggest_label_synonyms([], name_floor=60.0, cosine_floor=0.85) == []


def test_single_label_yields_nothing() -> None:
    assert suggest_label_synonyms([_entry("PERSON")], name_floor=60.0, cosine_floor=0.85) == []


def test_case_variants_qualify_via_normalised_fuzzy() -> None:
    # PERSON vs Person scores ~17 case-sensitively; normalisation lifts it to 100 (no embedding).
    out = suggest_label_synonyms(
        [_entry("PERSON"), _entry("Person")], name_floor=60.0, cosine_floor=0.85
    )
    assert len(out) == 1
    assert out[0].name_score == 100.0
    assert out[0].cosine_score is None
    assert {out[0].label_lo, out[0].label_hi} == {"PERSON", "Person"}


def test_separator_variants_qualify_via_normalised_fuzzy() -> None:
    # GROUP vs group scores 0 case-sensitively; underscore/case folding makes them identical.
    out = suggest_label_synonyms(
        [_entry("GROUP"), _entry("group")], name_floor=60.0, cosine_floor=0.85
    )
    assert len(out) == 1
    assert out[0].name_score == 100.0


def test_unrelated_labels_not_suggested() -> None:
    out = suggest_label_synonyms(
        [_entry("PERSON"), _entry("DRAGON")], name_floor=60.0, cosine_floor=0.85
    )
    assert out == []


def test_subset_label_not_over_matched_by_name_rung() -> None:
    # Graph-quality S6c: a short label that is only a token-subset of a longer one
    # ("IN" inside "STORED_IN") must not score 100 on the name rung. With no embedding,
    # the pair now falls below the name floor and is not suggested — the `…_IN` family no
    # longer floods the list around a bare `IN`.
    out = suggest_label_synonyms(
        [_entry("IN"), _entry("STORED_IN")], name_floor=60.0, cosine_floor=0.85
    )
    assert out == []


def test_subset_label_still_reachable_via_embedding_rung() -> None:
    # Recall-first OR is intact: the name rung dropping a subset pair does not stop the
    # embedding rung from surfacing it when the label vectors agree.
    out = suggest_label_synonyms(
        [_entry("IN", embedding=[1.0, 0.0]), _entry("STORED_IN", embedding=[1.0, 0.0])],
        name_floor=60.0,
        cosine_floor=0.85,
    )
    assert len(out) == 1
    assert out[0].cosine_score == 1.0
    assert out[0].name_score < 60.0  # the fuzzy rung did not carry it


def test_embedding_qualifies_pair_the_names_miss() -> None:
    # Token-disjoint synonyms (fuzzy score stays far below floor even normalised) but
    # near-identical label embeddings → qualify on the embedding rung alone.
    out = suggest_label_synonyms(
        [
            _entry("LOCATION", embedding=[1.0, 0.0]),
            _entry("PLACE", embedding=[1.0, 0.0]),
        ],
        name_floor=60.0,
        cosine_floor=0.85,
    )
    assert len(out) == 1
    assert out[0].cosine_score == 1.0
    assert out[0].name_score < 60.0  # the fuzzy rung did not carry it


def test_missing_embedding_falls_back_to_name_only() -> None:
    # One label embedded, one not → cosine rung skipped, normalised name rung still qualifies.
    out = suggest_label_synonyms(
        [_entry("PERSON", embedding=[1.0, 0.0]), _entry("Person", embedding=None)],
        name_floor=60.0,
        cosine_floor=0.85,
    )
    assert len(out) == 1
    assert out[0].cosine_score is None


def test_zero_magnitude_embedding_is_skipped_not_raised() -> None:
    out = suggest_label_synonyms(
        [_entry("PERSON", embedding=[0.0, 0.0]), _entry("Person", embedding=[0.0, 0.0])],
        name_floor=60.0,
        cosine_floor=0.85,
    )
    assert len(out) == 1  # name rung still qualifies
    assert out[0].cosine_score is None  # zero-magnitude vectors skipped, no ValueError


def test_dimension_mismatch_embedding_is_skipped_not_raised() -> None:
    # Defensive: mismatched dims are skipped (name rung carries the pair), never a crash.
    out = suggest_label_synonyms(
        [_entry("PERSON", embedding=[1.0, 0.0, 0.0]), _entry("Person", embedding=[1.0, 0.0])],
        name_floor=60.0,
        cosine_floor=0.85,
    )
    assert len(out) == 1
    assert out[0].cosine_score is None


def test_counts_carried_in_canonical_order() -> None:
    out = suggest_label_synonyms(
        [_entry("Person", count=3), _entry("PERSON", count=7)],
        name_floor=60.0,
        cosine_floor=0.85,
    )
    assert len(out) == 1
    # label_lo/hi are sorted; the counts must follow the same order.
    assert out[0].label_lo == "PERSON" and out[0].label_hi == "Person"
    assert out[0].count_lo == 7 and out[0].count_hi == 3


def test_ranked_strongest_first_and_deterministic() -> None:
    entries = [
        _entry("KOWALSKI"),  # KOWALSKI vs KOWAL → ~77, a genuinely weaker pair
        _entry("KOWAL"),
        _entry("PERSON"),
        _entry("Person"),  # exact after folding → 100
    ]
    out = suggest_label_synonyms(entries, name_floor=60.0, cosine_floor=0.85)
    assert len(out) == 2
    assert out[0].combined_score > out[1].combined_score
    assert {out[0].label_lo, out[0].label_hi} == {"PERSON", "Person"}  # 100 outranks 77
    again = suggest_label_synonyms(entries, name_floor=40.0, cosine_floor=0.85)
    assert [(s.label_lo, s.label_hi) for s in out] == [(s.label_lo, s.label_hi) for s in again]


def test_suggestion_pair_labels_are_canonically_ordered() -> None:
    out = suggest_label_synonyms(
        [_entry("Person"), _entry("PERSON")], name_floor=60.0, cosine_floor=0.85
    )
    assert isinstance(out[0], LabelSynonymSuggestion)
    assert out[0].label_lo <= out[0].label_hi


def test_dismissal_id_order_project_and_surface_independent() -> None:
    assert label_dismissal_id(_PROJECT, "type", "PERSON", "Person") == label_dismissal_id(
        _PROJECT, "type", "Person", "PERSON"
    )
    # Different project → different id.
    assert label_dismissal_id(uuid4(), "type", "PERSON", "Person") != label_dismissal_id(
        _PROJECT, "type", "PERSON", "Person"
    )
    # Different surface → different id (a type dismissal must not suppress a predicate pair).
    assert label_dismissal_id(_PROJECT, "predicate", "PERSON", "Person") != label_dismissal_id(
        _PROJECT, "type", "PERSON", "Person"
    )


def test_dismissal_id_does_not_collide_on_a_separator_in_a_label() -> None:
    # Labels are open-world free strings (INV-4): a '|' inside a label must not let two
    # different pairs share an id. {"a|b", "c"} and {"a", "b|c"} are distinct pairs.
    assert label_dismissal_id(_PROJECT, "type", "a|b", "c") != label_dismissal_id(
        _PROJECT, "type", "a", "b|c"
    )
    # And a label containing the JSON separator/quote is still unambiguous.
    assert label_dismissal_id(_PROJECT, "type", 'x", "y', "z") != label_dismissal_id(
        _PROJECT, "type", "x", 'y", "z'
    )
