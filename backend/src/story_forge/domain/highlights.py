"""Inline-highlight span resolution (M4.S1, spec §3.5 — the reader's highlights).

A read-only projection of the accepted graph onto the prose: given a paragraph's text
and the accepted entities known to appear in it, decide *where* each entity sits so the
reader can wrap it in a `<mark>`. The hard finding this module exists for (DM-IH-1): an
`entity_mention` records `paragraph_id` + `entity_id` but its char offsets are usually
**null** (the LLM path stores an evidence quote, not reliable offsets, and the spaCy
`CandidateSpan` that *does* carry offsets is discarded at accept time). So highlighting is
first a *where-does-this-entity-sit* problem, solved here by **render-time string search**
over the entity's surface forms — its `canonical_name` plus every `alias` (and aliases
accumulate the actual surface forms seen in the prose, since each merge-accept adds the
candidate's surface name as an alias — so inflected forms that were themselves extracted
become searchable here).

Matching is case-insensitive and runs against the *original* paragraph text (via
`re.IGNORECASE`), so the offsets index that text directly — never a casefolded copy whose
length could diverge from the source on an expanding codepoint (ß→ss, İ→i̇) and corrupt or
crash the offset math.

Pure and deterministic — no store, no model, no I/O (the layer the project unit-tests
hardest). The accompanying read endpoint (DM-IH-2) does the cross-store join and feeds the
surface forms in; the React reader (DM-IH-3) renders the ranges this returns.

Failure posture is **omit, don't guess** ([[fail-closed]]): an entity whose surface forms
don't occur in the paragraph yields no highlight (the prose renders as plain text) rather
than a guessed range — a wrong highlight (pointing the author at the wrong entity) is worse
than a missing one.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SpanInvalid(ValueError):
    """A manual span the author asked to tag is not a valid `[start, end)` range within the
    paragraph (M4.S3c) — out of bounds, zero-length, or reversed. Fail-closed: reject (the route
    maps it to 400), never clamp-and-guess a range the author didn't select."""


def validate_manual_span(paragraph_text: str, start: int, end: int) -> None:
    """Guard a manual tag's span against the paragraph it is offset into (M4.S3c, the Errors layer).

    The span must be in-bounds (`0 <= start < end <= len(text)`) and non-empty. A *pronoun* or
    *inflected* form that no entity name matches is perfectly valid — that is the whole point of a
    stored manual span (search can't re-find it). Cross-paragraph selection is impossible by
    construction: the API addresses one `paragraph_id`, so a span is always offsets into that one
    paragraph's text. Raises `SpanInvalid` (→400) on a bad range."""
    if start < 0 or end > len(paragraph_text):
        raise SpanInvalid(
            f"span [{start}, {end}) is out of bounds for a {len(paragraph_text)}-char paragraph"
        )
    if start >= end:
        raise SpanInvalid(f"span [{start}, {end}) is empty or reversed")


class HighlightTarget(BaseModel):
    """An accepted entity to search for in a paragraph (the search input).

    `names` is the entity's `canonical_name` + every `alias` — the surface forms to match,
    in no particular order. `type` is the open-world entity type (INV-4), carried through
    so the renderer can colour-by-type without a second lookup.
    """

    entity_id: UUID
    type: str
    names: list[str] = Field(default_factory=list)


class Highlight(BaseModel):
    """A resolved highlight range `[start, end)` within one paragraph's text.

    `text` is the exact matched substring (`paragraph_text[start:end]`, original casing) —
    handy for tests and for a renderer that wants the surface form. Ranges returned by
    `resolve_highlights` are non-overlapping and sorted by `start`.

    `source` + `mention_id` (M4.S3c / DM-S3c-6) carry occurrence identity: a pure
    render-time search hit is `source="search"`, `mention_id=None`; a stored manual span
    (an author's explicit tag) is `source="manual"` and carries the `entity_mentions` row
    id so a correction can address that exact occurrence. The defaults keep
    `resolve_highlights` output (search-only) valid for the S1/S2 reader unchanged.
    """

    start: int
    end: int
    entity_id: UUID
    type: str
    text: str
    source: Literal["search", "manual"] = "search"
    mention_id: UUID | None = None


class ManualSpan(BaseModel):
    """An author-asserted stored mention (M4.S3c, DM-S3c-1 B): a real `[start, end)`
    char range the author tagged, persisted in `entity_mentions` with `source='manual'`.

    Unlike a `HighlightTarget` (which the resolver *searches* for), a manual span carries
    its own offsets verbatim — it is never re-searched, so it can mark a pronoun, an
    inflected form, or a brand-new entity that no surface-form search could re-find.
    """

    mention_id: UUID
    entity_id: UUID
    type: str
    span_start: int
    span_end: int


class Suppression(BaseModel):
    """A negative record (M4.S3c, DM-S3c-1 B): "this `[start, end)` is **not** a highlight".

    Written by the right-click corrections — "not an entity" (`entity_id=None`, clears
    every claimant at the span) and "not this entity" (`entity_id` set, clears that one
    entity's claim). The resolver subtracts suppressions from the final reconciled set.
    """

    span_start: int
    span_end: int
    entity_id: UUID | None = None


def _is_word_char(ch: str) -> bool:
    """Word-boundary test. `str.isalnum()` is Unicode-aware, so Polish letters (ł, ą, …)
    count as word characters — "Jan" must not match inside "Janek"."""
    return ch.isalnum()


def _iter_boundary_matches(text: str, needle: str) -> Iterator[tuple[int, int]]:
    """Yield every `[start, end)` where `needle` occurs in `text`, case-insensitive and
    flanked by word boundaries.

    Matching is done with `re.finditer` over the *original* `text` (`re.escape` so a name's
    regex metacharacters are literal; `re.IGNORECASE` for caseless match), so the offsets it
    yields index `text` directly — no casefolded copy whose length could diverge from the
    source and push an offset past the end.
    """
    if not needle:
        return
    full_len = len(text)
    for match in re.finditer(re.escape(needle), text, re.IGNORECASE):
        start, end = match.start(), match.end()
        left_ok = start == 0 or not _is_word_char(text[start - 1])
        right_ok = end == full_len or not _is_word_char(text[end])
        if left_ok and right_ok:
            yield start, end


def _search_candidates(paragraph_text: str, targets: list[HighlightTarget]) -> list[Highlight]:
    """Build the (unsorted) render-time search candidates: every word-boundary,
    case-insensitive occurrence of any target's surface forms, deduped per target."""
    candidates: list[Highlight] = []
    for target in targets:
        seen: set[tuple[int, int]] = set()  # dedupe a target's own aliases hitting one span
        for name in target.names:
            needle = name.strip()
            if not needle:
                continue
            for start, end in _iter_boundary_matches(paragraph_text, needle):
                if (start, end) in seen:
                    continue
                seen.add((start, end))
                candidates.append(
                    Highlight(
                        start=start,
                        end=end,
                        entity_id=target.entity_id,
                        type=target.type,
                        text=paragraph_text[start:end],
                        source="search",
                    )
                )
    return candidates


def _greedy_non_overlap(sorted_candidates: list[Highlight]) -> list[Highlight]:
    """Walk pre-sorted candidates, keeping the first to claim each character range and
    dropping any later candidate that overlaps an already-kept one. Returns the survivors
    sorted by `start`. The caller's sort order decides who wins an overlap."""
    accepted: list[Highlight] = []
    for cand in sorted_candidates:
        if any(cand.start < kept.end and kept.start < cand.end for kept in accepted):
            continue
        accepted.append(cand)
    accepted.sort(key=lambda h: h.start)
    return accepted


def resolve_highlights(paragraph_text: str, targets: list[HighlightTarget]) -> list[Highlight]:
    """Resolve where each accepted entity appears in `paragraph_text` (DM-IH-1/4).

    Render-time search: for each target, find every word-boundary, case-insensitive
    occurrence of any of its surface forms; then arbitrate overlaps **longest-match-wins**
    (the most specific entity owns each character; ties broken deterministically). Returns
    non-overlapping ranges sorted by `start`. An entity whose forms don't occur is simply
    absent — fail-closed, the prose renders as plain text.
    """
    candidates = _search_candidates(paragraph_text, targets)
    # Longest first, then leftmost, then a stable entity-id tiebreak so the arbitration is
    # deterministic when two entities claim the same span (a shared alias) or equal length.
    candidates.sort(key=lambda h: (-(h.end - h.start), h.start, str(h.entity_id)))
    return _greedy_non_overlap(candidates)


def reconcile_highlights(
    paragraph_text: str,
    targets: list[HighlightTarget],
    manual_spans: list[ManualSpan],
    suppressions: list[Suppression],
) -> list[Highlight]:
    """Reconcile the three highlight sources into the final ranges (M4.S3c, DM-S3c-1 B).

    The reader's highlight layer is no longer purely derived: it merges render-time
    **search** hits (DM-IH-1), author-asserted **stored manual spans** (real offsets), and
    **suppressions** (negative records), under two rules:

    - **manual-wins-then-longest-match** — a manual span (the author's explicit assertion)
      beats an overlapping search hit; within a source class the longest, then leftmost,
      then a stable id tiebreak holds (the same arbitration `resolve_highlights` uses).
    - **suppressions subtract post-overlay** — after arbitration, drop any surviving
      highlight whose `[start, end)` matches a suppression keyed to all entities
      (`entity_id is None`, "not an entity") or to that highlight's entity ("not this
      entity"). So "not an entity" genuinely clears a span even if a manual tag sits there.

    With empty `manual_spans`/`suppressions` this returns exactly `resolve_highlights`'
    output (the S1/S2 reader path is unaffected). Pure and deterministic — no store, no I/O.
    """
    candidates = _search_candidates(paragraph_text, targets)
    for span in manual_spans:
        candidates.append(
            Highlight(
                start=span.span_start,
                end=span.span_end,
                entity_id=span.entity_id,
                type=span.type,
                text=paragraph_text[span.span_start : span.span_end],
                source="manual",
                mention_id=span.mention_id,
            )
        )

    # Source class first (0 = manual wins over 1 = search), then the same longest/leftmost/
    # id arbitration so a manual span evicts any search hit it overlaps.
    candidates.sort(
        key=lambda h: (
            0 if h.source == "manual" else 1,
            -(h.end - h.start),
            h.start,
            str(h.entity_id),
        )
    )
    arbitrated = _greedy_non_overlap(candidates)

    def _suppressed(h: Highlight) -> bool:
        return any(
            s.span_start == h.start
            and s.span_end == h.end
            and (s.entity_id is None or s.entity_id == h.entity_id)
            for s in suppressions
        )

    return [h for h in arbitrated if not _suppressed(h)]
