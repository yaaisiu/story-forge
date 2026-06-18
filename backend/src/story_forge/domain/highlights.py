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
from uuid import UUID

from pydantic import BaseModel, Field


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
    """

    start: int
    end: int
    entity_id: UUID
    type: str
    text: str


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


def resolve_highlights(paragraph_text: str, targets: list[HighlightTarget]) -> list[Highlight]:
    """Resolve where each accepted entity appears in `paragraph_text` (DM-IH-1/4).

    Render-time search: for each target, find every word-boundary, case-insensitive
    occurrence of any of its surface forms; then arbitrate overlaps **longest-match-wins**
    (the most specific entity owns each character; ties broken deterministically). Returns
    non-overlapping ranges sorted by `start`. An entity whose forms don't occur is simply
    absent — fail-closed, the prose renders as plain text.
    """
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
                    )
                )

    # Longest first, then leftmost, then a stable entity-id tiebreak so the arbitration is
    # deterministic when two entities claim the same span (a shared alias) or equal length.
    candidates.sort(key=lambda h: (-(h.end - h.start), h.start, str(h.entity_id)))
    accepted: list[Highlight] = []
    for cand in candidates:
        if any(cand.start < kept.end and kept.start < cand.end for kept in accepted):
            continue
        accepted.append(cand)
    accepted.sort(key=lambda h: h.start)
    return accepted
