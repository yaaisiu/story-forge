"""Unit tests for the pure name/vector similarity primitives (domain/name_similarity)."""

from __future__ import annotations

import pytest

from story_forge.domain.name_similarity import cosine_similarity, name_match_score


def test_name_match_score_best_over_names() -> None:
    # Best score wins across the surface forms; token-set order-insensitive.
    assert name_match_score("Bronek", ["Bronisław", "Bronek"]) == pytest.approx(100.0)
    # Reordered tokens score identically (token *set*, order-insensitive).
    assert name_match_score("Bronek Kowalski", ["Kowalski Bronek"]) == pytest.approx(100.0)


def test_name_match_score_empty_names_is_zero() -> None:
    assert name_match_score("anything", []) == 0.0


def test_name_match_score_is_symmetric() -> None:
    # token_set_ratio is symmetric — the self-join relies on this to score a pair once.
    a, b = "Katarzyna Nowak", "Kasia Nowak"
    assert name_match_score(a, [b]) == pytest.approx(name_match_score(b, [a]))


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
