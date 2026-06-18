"""Unit tests for the inline-highlight span resolver (M4.S1, spec §3.5 / DM-IH-1, DM-IH-4).

The span resolver is the centre of gravity of the inline-highlights slice — a pure,
deterministic function over (paragraph text, accepted entities) → decorated ranges. These
tests encode the register decisions: render-time search over name + aliases (DM-IH-1a),
longest-match-wins overlap (DM-IH-4), omit-on-unresolvable / word-boundary discipline
(fail-closed, the "but what if" over-match cases).
"""

from __future__ import annotations

from uuid import UUID

from story_forge.domain.highlights import (
    Highlight,
    HighlightTarget,
    resolve_highlights,
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
