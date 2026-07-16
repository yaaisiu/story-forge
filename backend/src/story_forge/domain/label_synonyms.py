"""Label-vocabulary synonym self-join over the accepted graph (graph-quality S6a).

S4 (`domain/duplicate_clusters.py`) suggests duplicate *entities*; S6 suggests synonymous
*labels* — the same self-join turned on a vocabulary of label strings instead of on
entities. It *suggests*, never renames (INV-1/INV-9): the human commits each graph-wide
rename through the apply path (S6a-2). This module is the read/suggest half's pure core.

Two vocabularies are normalised, each with its own call to `suggest_label_synonyms`:

- **predicate names** — the Neo4j relationship types (`PASSENGER_ON`, `ON_SHIP`, …);
- **entity-type labels** — the `type` node property (`PERSON`, `Person`, `GROUP`, …).

They are never cross-compared (a predicate is not a synonym of a type), so the caller runs
one self-join per surface and stamps the surface onto the results + dismissal keys.

Pure and deterministic (no I/O, no LLM), reusing the `label_match_score` (RapidFuzz) and
`cosine_similarity` (embeddings) primitives from `name_similarity.py`. Decisions it encodes
(register DM-NN-1/2, INV-4):

- **Two rungs, recall-first** — a pair qualifies on normalised-name similarity *or*
  label-string embedding cosine above a floor; nothing auto-renames, so a false positive
  costs one dismiss click while a missed synonym stays hidden. The name floor is the
  tunable `name_normalise_suggest_floor`; the embedding floor reuses the Stage-2 cosine bar.
- **Fuzzy rung is normalised** — the raw label is case- and separator-sensitive (`PERSON`
  vs `Person` scores ~17, `GROUP` vs `group` scores 0), yet these casing/separator variants
  are exactly the type-vocabulary noise S6 must catch. So the fuzzy rung compares
  **case-folded, separator-split** labels (`PERSON`→`person`, `PASSENGER_ON`→`passenger on`);
  the raw label is kept for display + dismissal keying.
- **Fuzzy rung is subset-INtolerant** (`label_match_score`, S6c) — it scores with
  `token_sort_ratio`, not the subset-tolerant `token_set_ratio` of `name_match_score`. A
  bare `IN` is a token-subset of `STORED_IN`, `STORES_IN`, and the whole `…_IN` family, and
  `token_set_ratio` would score every one of them 100 (a short label is a subset of every
  longer one that contains it), flooding the list. `token_sort_ratio` is length-aware — the
  subset noise drops below the floor — while genuine variants (`STORED_IN`↔`STORES_IN`) stay
  high, and the embedding rung still carries any true synonym the name rung now misses.
- **Embedding rung is the label string itself** — encoded by the caller via
  `EmbeddingAgent.encode` (not mention vectors, unlike S4). It carries the token-disjoint
  synonyms fuzzy can't reach (`LOCATION`↔`PLACE`, `PASSENGER_ON`↔`ON_SHIP`). An entry with
  no usable embedding is scored name-only; `cosine_similarity` raises on a zero-magnitude
  vector, so such vectors are skipped here.
- **Nothing auto-collapses** (INV-4) — the vocabularies stay open-world free strings; this
  only ranks candidates for a human.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID, uuid5

from story_forge.domain.name_similarity import cosine_similarity, label_match_score

# Namespace for the deterministic dismissed-label-pair id (the project's uuid5 idiom; the
# label-surface analogue of `_DEDUP_PAIR_NS` in `domain/duplicate_clusters.py`).
_LABEL_PAIR_NS = UUID("a5f0c0de-0000-4000-8000-000000000006")


@dataclass(frozen=True)
class LabelCount:
    """One distinct label in a vocabulary and how many graph elements bear it.

    `count` is the number of edges (predicate vocabulary) or nodes (type vocabulary)
    carrying the label — shown to the author so they can normalise toward the common form.
    """

    label: str
    count: int


@dataclass(frozen=True)
class LabelVocabularyEntry:
    """A vocabulary label paired with its occurrence count and optional embedding.

    `embedding` is the label string encoded by `EmbeddingAgent.encode`, or None when the
    embedding rung is unavailable/demoted — in which case the label is scored name-only.
    """

    label: str
    count: int
    embedding: list[float] | None


@dataclass(frozen=True)
class LabelSynonymSuggestion:
    """One suggested synonymous label pair within a single vocabulary (one surface).

    `label_lo`/`label_hi` are the pair's two labels in canonical (sorted) order, so the
    same unordered pair has one stable identity; `count_lo`/`count_hi` are their counts in
    that same order. `cosine_score` is None when neither label carried a usable embedding
    (name-only). `combined_score` is the rank key (name normalised to [0, 1] vs cosine).
    """

    label_lo: str
    label_hi: str
    count_lo: int
    count_hi: int
    name_score: float
    cosine_score: float | None
    combined_score: float


def canonical_label_pair(a: str, b: str) -> tuple[str, str]:
    """The label pair as (lo, hi) so an unordered {a, b} has one canonical form.

    The single source of pair ordering — shared by `label_dismissal_id` (the id key) and the
    dismissal store's `label_lo/hi` columns, so the stored order and the id can't drift.
    """
    return (a, b) if a <= b else (b, a)


def label_dismissal_id(project_id: UUID, surface: str, a: str, b: str) -> UUID:
    """Deterministic id for a dismissed (or suggested) unordered label pair on a surface.

    Order-independent (`{a, b}` == `{b, a}`), project-scoped, and **surface-scoped** — so a
    dismissed type pair never suppresses an identically-spelled predicate pair. The
    dismissal store's primary key doubles as an idempotency key (`ON CONFLICT (id) DO
    NOTHING`) and the suggestion read suppresses a dismissed pair by recomputing the id.

    The seed is a JSON array of the components, not a `|`-joined string: labels are
    open-world free strings (INV-4), so a `|` inside a label would let `{"a|b", "c"}` and
    `{"a", "b|c"}` collide on one id (JSON escaping makes the encoding unambiguous). The S4
    `dismissal_pair_id` joins UUIDs, which cannot contain the separator, so it does not need
    this — a label pair does.
    """
    lo, hi = canonical_label_pair(a, b)
    seed = json.dumps([str(project_id), surface, lo, hi], ensure_ascii=False)
    return uuid5(_LABEL_PAIR_NS, seed)


def _normalise_label(label: str) -> str:
    """Case-fold and split underscores/whitespace so casing/separator variants match.

    `PERSON`/`Person`/`person` all normalise to `person`; `PASSENGER_ON` to `passenger on`.
    Without this the RapidFuzz rung scores `PERSON` vs `Person` at ~17 — the exact
    type-vocabulary casing noise S6 exists to catch would fall below the name floor.
    """
    return " ".join(label.replace("_", " ").split()).casefold()


def suggest_label_synonyms(
    entries: Sequence[LabelVocabularyEntry],
    *,
    name_floor: float,
    cosine_floor: float,
) -> list[LabelSynonymSuggestion]:
    """Rank the above-floor synonym pairs within one label vocabulary (pure).

    A pair qualifies if its normalised-name score reaches `name_floor` *or* its label-string
    embedding cosine reaches `cosine_floor` (recall-first — either signal is enough).
    Results are ranked strongest-first by the normalised combined score, with a
    deterministic tiebreak: higher name score, then canonical label order.
    """
    ranked: list[tuple[float, float, LabelSynonymSuggestion]] = []
    for i, a in enumerate(entries):
        for b in entries[i + 1 :]:
            name_score = label_match_score(_normalise_label(a.label), _normalise_label(b.label))
            cosine = _pair_cosine(a.embedding, b.embedding)
            qualifies = name_score >= name_floor or (cosine is not None and cosine >= cosine_floor)
            if not qualifies:
                continue
            combined = max(name_score / 100.0, cosine if cosine is not None else 0.0)
            lo, hi = canonical_label_pair(a.label, b.label)
            count_lo, count_hi = (a.count, b.count) if a.label == lo else (b.count, a.count)
            ranked.append(
                (
                    combined,
                    name_score,
                    LabelSynonymSuggestion(
                        label_lo=lo,
                        label_hi=hi,
                        count_lo=count_lo,
                        count_hi=count_hi,
                        name_score=name_score,
                        cosine_score=cosine,
                        combined_score=combined,
                    ),
                )
            )
    ranked.sort(
        key=lambda row: (
            -row[0],  # combined score, strongest first
            -row[1],  # name score
            row[2].label_lo,  # canonical label order (deterministic tiebreak)
            row[2].label_hi,
        )
    )
    return [row[2] for row in ranked]


def _pair_cosine(a: list[float] | None, b: list[float] | None) -> float | None:
    """Cosine of two label embeddings, or None if either is missing/zero/mismatched.

    Skips a missing embedding, a zero-magnitude vector (cosine is undefined there —
    `cosine_similarity` would raise), and a dimension mismatch (defensive; real embeddings
    share one dimension).
    """
    if a is None or b is None:
        return None
    if len(a) != len(b):
        return None
    if not any(x != 0.0 for x in a) or not any(y != 0.0 for y in b):
        return None
    return cosine_similarity(a, b)
