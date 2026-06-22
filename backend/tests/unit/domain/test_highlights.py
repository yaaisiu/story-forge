"""Unit tests for the inline-highlight span resolver (M4.S1, spec §3.5 / DM-IH-1, DM-IH-4).

The span resolver is the centre of gravity of the inline-highlights slice — a pure,
deterministic function over (paragraph text, accepted entities) → decorated ranges. These
tests encode the register decisions: render-time search over name + aliases (DM-IH-1a),
longest-match-wins overlap (DM-IH-4), omit-on-unresolvable / word-boundary discipline
(fail-closed, the "but what if" over-match cases).
"""

from __future__ import annotations

from uuid import UUID

import pytest

from story_forge.domain.highlights import (
    Highlight,
    HighlightTarget,
    ManualSpan,
    SpanInvalid,
    Suppression,
    reconcile_highlights,
    resolve_highlights,
    validate_manual_span,
)

JANEK = UUID("00000000-0000-4000-8000-000000000001")
MARIA = UUID("00000000-0000-4000-8000-000000000002")
JANEK_KOWALSKI = UUID("00000000-0000-4000-8000-000000000003")


def _target(entity_id: UUID, type_: str, *names: str) -> HighlightTarget:
    return HighlightTarget(entity_id=entity_id, type=type_, names=list(names))


def test_basic_two_entities_highlighted_at_their_offsets() -> None:
    text = "Janek met Maria."
    out = resolve_highlights(
        text,
        [_target(JANEK, "Character", "Janek"), _target(MARIA, "Character", "Maria")],
    )
    assert out == [
        Highlight(start=0, end=5, entity_id=JANEK, type="Character", text="Janek"),
        Highlight(start=10, end=15, entity_id=MARIA, type="Character", text="Maria"),
    ]


def test_inflected_form_matched_via_alias() -> None:
    # The headline DM-IH-1 win: "Janek" won't substring-match the inflected "Jankowi",
    # but a merge-accept stored "Jankowi" as an alias, so the alias search finds it.
    text = "Dał Jankowi książkę."
    out = resolve_highlights(text, [_target(JANEK, "Character", "Janek", "Jankowi")])
    assert out == [
        Highlight(start=4, end=11, entity_id=JANEK, type="Character", text="Jankowi"),
    ]


def test_unresolvable_entity_is_omitted_not_raised() -> None:
    # Fail-closed: a surface form absent from the paragraph yields no highlight.
    text = "Janek met Maria."
    out = resolve_highlights(text, [_target(UUID(int=99), "Character", "Zbyszek")])
    assert out == []


def test_no_substring_overmatch_word_boundary() -> None:
    # "Jan" must not match inside "Janek" — highlighting a sub-word is a wrong highlight.
    text = "Janek wszedł."
    out = resolve_highlights(text, [_target(UUID(int=42), "Character", "Jan")])
    assert out == []


def test_longest_match_wins_on_overlap() -> None:
    # "Janek" and "Janek Kowalski" both match; the more specific (longer) entity wins,
    # the shorter is dropped (DM-IH-4) — one highlight per character.
    text = "Janek Kowalski wszedł."
    out = resolve_highlights(
        text,
        [
            _target(JANEK, "Character", "Janek"),
            _target(JANEK_KOWALSKI, "Character", "Janek Kowalski"),
        ],
    )
    assert out == [
        Highlight(
            start=0,
            end=14,
            entity_id=JANEK_KOWALSKI,
            type="Character",
            text="Janek Kowalski",
        ),
    ]


def test_repeated_surface_form_highlights_all_occurrences() -> None:
    # Paragraph-level mentions carry no per-occurrence position, so render-time search
    # highlights every occurrence (the documented over-highlight tradeoff of DM-IH-1a).
    text = "Maria i Maria."
    out = resolve_highlights(text, [_target(MARIA, "Character", "Maria")])
    assert [(h.start, h.end) for h in out] == [(0, 5), (8, 13)]
    assert all(h.entity_id == MARIA for h in out)


def test_case_insensitive_match_preserves_original_casing() -> None:
    text = "maria wstała."
    out = resolve_highlights(text, [_target(MARIA, "Character", "Maria")])
    assert out == [
        Highlight(start=0, end=5, entity_id=MARIA, type="Character", text="maria"),
    ]


def test_output_is_sorted_and_non_overlapping() -> None:
    text = "Maria met Janek."
    out = resolve_highlights(
        text,
        [_target(JANEK, "Character", "Janek"), _target(MARIA, "Character", "Maria")],
    )
    starts = [h.start for h in out]
    assert starts == sorted(starts)
    # non-overlapping: each range starts at or after the previous one's end
    for prev, nxt in zip(out, out[1:], strict=False):
        assert nxt.start >= prev.end


def test_empty_inputs() -> None:
    assert resolve_highlights("", [_target(JANEK, "Character", "Janek")]) == []
    assert resolve_highlights("Janek met Maria.", []) == []


def test_expanding_codepoint_does_not_crash_and_offsets_stay_correct() -> None:
    # Regression: 'ß' casefolds to 'ss' (length-changing), so a casefolded-copy approach
    # pushed an offset past the original text and raised IndexError. Matching against the
    # original text keeps offsets exact and never crashes.
    text = "daß Maria wstała."
    out = resolve_highlights(text, [_target(MARIA, "Character", "Maria")])
    assert out == [
        Highlight(start=4, end=9, entity_id=MARIA, type="Character", text="Maria"),
    ]


def test_name_with_regex_metacharacters_is_matched_literally() -> None:
    # A surface form containing regex metachars must be matched literally, not as a pattern.
    text = "The C++ guild met."
    out = resolve_highlights(text, [_target(UUID(int=5), "Organization", "C++")])
    assert out == [
        Highlight(start=4, end=7, entity_id=UUID(int=5), type="Organization", text="C++"),
    ]


def test_blank_name_never_matches_everything() -> None:
    # A degenerate empty/blank surface form must not match at every position.
    text = "Janek met Maria."
    out = resolve_highlights(text, [_target(UUID(int=7), "Character", "", "   ")])
    assert out == []


# ── reconcile_highlights — the M4.S3c overlay/suppression resolver (DM-S3c-1 B) ──
#
# A manual tag persists a STORED span (real offsets) that OVERLAYS and WINS over the
# render-time search layer; a rejected highlight writes a SUPPRESSION the resolver
# subtracts. Arbitration is manual-wins-then-longest-match (DM-S3c-1); suppressions
# subtract from the FINAL reconciled set (post-overlay, DM-S3c build-call 2). Each
# resolved highlight carries `source` + (for manual) a `mention_id` (DM-S3c-6).

MENTION_1 = UUID("00000000-0000-4000-8000-0000000000a1")
MENTION_2 = UUID("00000000-0000-4000-8000-0000000000a2")


def _manual(mention_id: UUID, entity_id: UUID, type_: str, start: int, end: int) -> ManualSpan:
    return ManualSpan(
        mention_id=mention_id, entity_id=entity_id, type=type_, span_start=start, span_end=end
    )


def test_reconcile_with_no_manual_or_suppressions_equals_search() -> None:
    # Regression guard: with empty overlay/suppression inputs, reconcile must return
    # exactly what resolve_highlights does (the S1/S2 reader path is unchanged) — only
    # the default source="search"/mention_id=None decoration is added.
    text = "Janek met Maria."
    targets = [_target(JANEK, "Character", "Janek"), _target(MARIA, "Character", "Maria")]
    assert reconcile_highlights(text, targets, [], []) == [
        Highlight(start=0, end=5, entity_id=JANEK, type="Character", text="Janek", source="search"),
        Highlight(
            start=10, end=15, entity_id=MARIA, type="Character", text="Maria", source="search"
        ),
    ]


def test_manual_span_beats_overlapping_search_hit() -> None:
    # The author tagged [0,5] as MARIA; search would put JANEK at [0,5]. Manual wins:
    # only the manual MARIA span survives, carrying source="manual" + its mention_id.
    text = "Janek met Maria."
    out = reconcile_highlights(
        text,
        [_target(JANEK, "Character", "Janek")],
        [_manual(MENTION_1, MARIA, "Character", 0, 5)],
        [],
    )
    assert out == [
        Highlight(
            start=0,
            end=5,
            entity_id=MARIA,
            type="Character",
            text="Janek",
            source="manual",
            mention_id=MENTION_1,
        ),
    ]


def test_manual_span_with_no_overlapping_search_hit_is_added() -> None:
    # A manual span over a pronoun/inflected form search can never re-find (the motivating
    # case) appears as a standalone manual highlight alongside the search hits.
    text = "Janek met her."  # "her" is no entity's surface form
    out = reconcile_highlights(
        text,
        [_target(JANEK, "Character", "Janek")],
        [_manual(MENTION_1, MARIA, "Character", 10, 13)],
        [],
    )
    assert out == [
        Highlight(start=0, end=5, entity_id=JANEK, type="Character", text="Janek", source="search"),
        Highlight(
            start=10,
            end=13,
            entity_id=MARIA,
            type="Character",
            text="her",
            source="manual",
            mention_id=MENTION_1,
        ),
    ]


def test_manual_span_no_double_count_with_its_own_search_form() -> None:
    # A manual span at [0,5] for MARIA AND MARIA's name also search-matches [0,5] → one
    # highlight, the manual one wins (not two stacked on the same range).
    text = "Maria wstała."
    out = reconcile_highlights(
        text,
        [_target(MARIA, "Character", "Maria")],
        [_manual(MENTION_1, MARIA, "Character", 0, 5)],
        [],
    )
    assert out == [
        Highlight(
            start=0,
            end=5,
            entity_id=MARIA,
            type="Character",
            text="Maria",
            source="manual",
            mention_id=MENTION_1,
        ),
    ]


def test_suppression_removes_a_search_hit() -> None:
    # "not an entity" at [0,5] (entity_id=None) clears the JANEK search hit there; the
    # other paragraph hit (MARIA) is untouched.
    text = "Janek met Maria."
    out = reconcile_highlights(
        text,
        [_target(JANEK, "Character", "Janek"), _target(MARIA, "Character", "Maria")],
        [],
        [Suppression(span_start=0, span_end=5, entity_id=None)],
    )
    assert out == [
        Highlight(
            start=10, end=15, entity_id=MARIA, type="Character", text="Maria", source="search"
        ),
    ]


def test_suppression_one_entity_only_clears_that_entity() -> None:
    # "not this entity" keyed to JANEK at [0,5] clears only JANEK's claim there; a
    # MARIA manual span at the same offsets survives (entity-scoped suppression).
    text = "Janek met Maria."
    out = reconcile_highlights(
        text,
        [_target(JANEK, "Character", "Janek")],
        [_manual(MENTION_1, MARIA, "Character", 0, 5)],
        [Suppression(span_start=0, span_end=5, entity_id=JANEK)],
    )
    # The manual MARIA span won arbitration over the JANEK search hit; a JANEK-scoped
    # suppression does not touch it.
    assert out == [
        Highlight(
            start=0,
            end=5,
            entity_id=MARIA,
            type="Character",
            text="Janek",
            source="manual",
            mention_id=MENTION_1,
        ),
    ]


def test_suppression_all_entities_clears_a_manual_span_too() -> None:
    # Post-overlay subtraction (build-call 2): "not an entity" (entity_id=None) genuinely
    # clears the span even if a manual tag sits there.
    text = "Janek met Maria."
    out = reconcile_highlights(
        text,
        [],
        [_manual(MENTION_1, MARIA, "Character", 0, 5)],
        [Suppression(span_start=0, span_end=5, entity_id=None)],
    )
    assert out == []


def test_reconcile_output_sorted_by_start() -> None:
    text = "Maria met Janek."
    out = reconcile_highlights(
        text,
        [_target(JANEK, "Character", "Janek"), _target(MARIA, "Character", "Maria")],
        [],
        [],
    )
    assert [h.start for h in out] == sorted(h.start for h in out)


# ── validate_manual_span — fail-closed span guard for a manual tag (M4.S3c) ─────────────────


def test_validate_manual_span_accepts_an_in_bounds_span() -> None:
    validate_manual_span("Janek met Maria.", 0, 5)  # no raise


def test_validate_manual_span_accepts_a_pronoun_or_inflected_form() -> None:
    # The motivating case: a span over a form no name matches is *valid* — it is stored verbatim.
    validate_manual_span("Dał mu książkę.", 4, 6)  # "mu" — a pronoun, no entity name


def test_validate_manual_span_rejects_zero_length() -> None:
    with pytest.raises(SpanInvalid):
        validate_manual_span("Janek met Maria.", 5, 5)


def test_validate_manual_span_rejects_reversed() -> None:
    with pytest.raises(SpanInvalid):
        validate_manual_span("Janek met Maria.", 6, 2)


def test_validate_manual_span_rejects_out_of_bounds() -> None:
    with pytest.raises(SpanInvalid):
        validate_manual_span("Janek", -1, 3)
    with pytest.raises(SpanInvalid):
        validate_manual_span("Janek", 0, 99)
