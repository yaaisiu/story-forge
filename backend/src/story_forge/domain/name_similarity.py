"""Pure name/vector similarity primitives shared across the §3.3 matching surfaces.

Three deterministic, local scoring helpers with no I/O and no model:

- `name_match_score` — the RapidFuzz `token_set_ratio` core (0–100) of the Stage-1
  fuzzy match: the best score of a query against a set of surface forms. **Subset-
  tolerant** by design (a token-subset scores 100), because a partial *name* — the
  honorific in "Stary Bronek" matched by "Bronek" — is a wanted signal there.
- `label_match_score` — the RapidFuzz `token_sort_ratio` (0–100) of two *labels*.
  **Subset-INtolerant** (length-aware), because for a label vocabulary a bare `IN`
  being a token-subset of `STORED_IN` is pure noise, not a synonym (graph-quality S6c).
- `cosine_similarity` — the Stage-2 embedding distance (in [-1, 1]) over two vectors.

They live in `domain/` (not in the matcher) because both the intake cascade
(`agents/matching_agent.py`) *and* the curation-time duplicate self-join
(`domain/duplicate_clusters.py`, graph-quality S4) score with the exact same signals —
and `domain/` may not import from `agents/`. Keeping the primitives here lets the pure
self-join reuse them without a layering break, and the matcher imports them from here so
there is one home for the math (relocated from `matching_agent` at graph-quality S4a).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from rapidfuzz import fuzz


def name_match_score(query: str, names: Sequence[str]) -> float:
    """Best RapidFuzz `token_set_ratio` (0–100) of `query` against any of `names`.

    Order-insensitive token-set matching, so "Old Bronek" and "Bronek, old" score high.
    An empty `names` (an entity with no surface forms) scores 0.0. This is the shared
    Stage-1 ranking core: the intake matcher scores a candidate's surface form against an
    existing entity's canonical_name + aliases, and the duplicate self-join scores one
    accepted entity's surface forms against another's — the same signal both ways.
    """
    return max((fuzz.token_set_ratio(query, name) for name in names), default=0.0)


def label_match_score(a: str, b: str) -> float:
    """RapidFuzz `token_sort_ratio` (0–100) of two labels — subset-INtolerant.

    The label-vocabulary counterpart of `name_match_score`, differing in exactly one way:
    it uses `token_sort_ratio`, not `token_set_ratio`, so a short label that is merely a
    token-subset of a longer one does **not** score 100. `token_set_ratio` treats a subset
    as a perfect match — the wanted honorific/partial-name tolerance for *entity names*
    (`Bronek` ⊂ `Stary Bronek`), but pure noise for a *label* vocabulary, where a bare `IN`
    (1 use) would otherwise score 100 against `STORED_IN`, `STORES_IN`, and the whole `…_IN`
    family (graph-quality S6c). `token_sort_ratio` is length-aware — `in` vs `stored in`
    scores ~36 — while staying order-insensitive, so casing/separator/spelling variants
    (`stored in` vs `stores in`) still score high. Both labels are expected to be already
    normalised (case-folded, separator-split) by the caller.

    A degenerate label that normalises to empty (junk like `_` or whitespace-only) matches
    nothing — `token_sort_ratio("", "")` is 100 (two "identical" empty strings), which would
    otherwise surface two empty-normalising labels as a spurious top-ranked synonym, so the
    empty case is guarded to 0.0 (mirroring `name_match_score`'s empty-forms → 0.0 contract).
    """
    if not a or not b:
        return 0.0
    return fuzz.token_sort_ratio(a, b)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two equal-length vectors, in [-1.0, 1.0].

    Pure — no model — so the §3.3 Stage-2 distance math is unit-tested in CI without
    loading the ~2 GB embedding stack. Raises on a length mismatch (a candidate vector
    and a stored mention vector must share the model's dimensionality) and on a
    zero-magnitude vector (cosine is undefined there; a real embedding is never all-zero).
    A caller scoring possibly-vectorless entities (the duplicate self-join) must guard the
    zero-magnitude case itself rather than rely on this raising.
    """
    if len(a) != len(b):
        raise ValueError(f"vector length mismatch: {len(a)} != {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        raise ValueError("cosine similarity is undefined for a zero-magnitude vector")
    return dot / (norm_a * norm_b)
