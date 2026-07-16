"""Unit tests for the pure name/vector similarity primitives (domain/name_similarity)."""

from __future__ import annotations

import pytest

from story_forge.domain.name_similarity import (
    cosine_similarity,
    label_match_score,
    name_match_score,
)


def test_name_match_score_best_over_names() -> None:
    # Best score wins across the surface forms; token-set order-insensitive.
    assert name_match_score("Bronek", ["Bronisław", "Bronek"]) == pytest.approx(100.0)
    # Reordered tokens score identically (token *set*, order-insensitive).
    assert name_match_score("Bronek Kowalski", ["Kowalski Bronek"]) == pytest.approx(100.0)


def test_name_match_score_keeps_subset_tolerance() -> None:
    # The shared §3.3 / S4 primitive is deliberately UNCHANGED by the S6c label fix: a
    # partial name still scores 100 — the "Bronek" ↔ "Stary Bronek" honorific case the
    # live extraction Stage-1 matcher (spec §3.3) relies on.
    assert name_match_score("Bronek", ["Stary Bronek"]) == pytest.approx(100.0)


def test_name_match_score_empty_names_is_zero() -> None:
    assert name_match_score("anything", []) == 0.0


def test_name_match_score_is_symmetric() -> None:
    # token_set_ratio is symmetric — the self-join relies on this to score a pair once.
    a, b = "Katarzyna Nowak", "Kasia Nowak"
    assert name_match_score(a, [b]) == pytest.approx(name_match_score(b, [a]))


def test_label_match_score_rejects_token_subset() -> None:
    # Graph-quality S6c: unlike name_match_score, the label scorer is subset-INtolerant.
    # A short label that is merely a token-subset of a longer one ("in" inside "stored in")
    # must NOT score 100 — token_sort_ratio is length-aware, so it lands well below the 60
    # name floor and the noisy `…_IN` family stops over-matching a bare `IN`.
    assert label_match_score("in", "stored in") < 60.0
    assert label_match_score("of", "part of") < 60.0


def test_label_match_score_keeps_genuine_variants() -> None:
    # Casing/separator/spelling variants (already _normalise_label'd by the caller) stay
    # above the floor — the label rung still catches the vocabulary noise S6 exists for.
    assert label_match_score("person", "person") == pytest.approx(100.0)
    assert label_match_score("stored in", "stores in") >= 60.0
    assert label_match_score("located in", "stored in") >= 60.0


def test_label_match_score_is_order_insensitive() -> None:
    # token_sort keeps order-insensitivity (a reordered multiword label still matches),
    # so the underscore-split normalisation is robust to token order.
    assert label_match_score("passenger on", "on passenger") == pytest.approx(100.0)


def test_label_match_score_is_symmetric() -> None:
    assert label_match_score("stored in", "stores in") == pytest.approx(
        label_match_score("stores in", "stored in")
    )


def test_cosine_identical_and_orthogonal() -> None:
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 2.0], [3.0, 6.0]) == pytest.approx(1.0)


def test_cosine_raises_on_length_mismatch() -> None:
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 2.0], [1.0])


def test_cosine_raises_on_zero_magnitude() -> None:
    with pytest.raises(ValueError):
        cosine_similarity([0.0, 0.0], [1.0, 1.0])
