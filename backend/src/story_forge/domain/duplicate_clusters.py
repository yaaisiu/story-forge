"""Duplicate-entity self-join over the already-accepted graph (graph-quality S4a).

The §3.3 cascade matcher scores a *new* candidate against the accepted entities at
intake. S4 re-points that same deterministic scoring **inward**: each accepted entity is
scored against every other, and above-floor pairs are surfaced as likely duplicates for
the author to review. It *suggests*, never merges (INV-1/INV-9): the human commits each
merge through the existing merge path.

Pure and deterministic (no I/O, no LLM), reusing the relocated `name_match_score`
(Stage-1 RapidFuzz) and `cosine_similarity` (Stage-2 embeddings) primitives — the
`entity_merge.py` analogue, one layer of the S4a backend slice. Decisions it encodes
(register DM-CD-1/2, INV-4):

- **Pairwise, not transitive** — a flat list of A–B pairs (the merge is pairwise anyway;
  transitive clustering risks over-grouping and is a named later refinement).
- **Eager / recall-first** — a pair qualifies on name *or* embedding similarity above a
  floor; nothing auto-merges, so a false positive costs one dismiss click while a missed
  duplicate stays hidden. The name floor is the tunable `duplicate_suggest_floor`; the
  embedding floor reuses the Stage-2 cosine bar.
- **Type is a soft signal, never a hard filter** (INV-4) — it only nudges ranking
  (same-type pairs rank marginally higher at an equal score); two duplicates the
  over-extractor typed differently must still be suggested — the very case S4 exists for.
- **Zero-vector safety** — an entity with no usable mention vectors is scored name-only;
  `cosine_similarity` raises on a zero-magnitude vector, so such vectors are skipped here.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid5

from story_forge.domain.candidates import AcceptedSnapshot
from story_forge.domain.graph import GraphEntity
from story_forge.domain.name_similarity import cosine_similarity, name_match_score

# Namespace for the deterministic dismissed-pair id (the project's uuid5 idiom; see
# `_ACCEPT_NS` / `_REL_STAGE_NS` in `domain/candidates.py`).
_DEDUP_PAIR_NS = UUID("a5f0c0de-0000-4000-8000-000000000004")


@dataclass(frozen=True)
class DuplicateSuggestion:
    """One suggested duplicate pair over the accepted graph.

    `entity_id_lo`/`entity_id_hi` are the pair's two entity ids in canonical (sorted)
    order, so the same pair has one stable identity regardless of iteration order.
    `cosine_score` is None when neither entity contributed a usable mention vector
    (name-only). `combined_score` is the rank key (name normalised to [0,1] vs cosine).
    """

    entity_id_lo: UUID
    entity_id_hi: UUID
    name_score: float
    cosine_score: float | None
    combined_score: float


def canonical_pair(a: UUID, b: UUID) -> tuple[UUID, UUID]:
    """The pair as (lo, hi) so an unordered {a, b} has one canonical form.

    The single source of pair ordering — shared by `dismissal_pair_id` (the id key) and the
    dismissal store's `entity_id_lo/hi` columns, so the stored order and the id can't drift.
    """
    return (a, b) if a <= b else (b, a)


def dismissal_pair_id(project_id: UUID, a: UUID, b: UUID) -> UUID:
    """Deterministic id for a dismissed (or suggested) unordered entity pair in a project.

    Order-independent (`{a, b}` == `{b, a}`) and project-scoped, so the dismissal store's
    primary key doubles as an idempotency key (`ON CONFLICT (id) DO NOTHING`) and the
    suggestion read can suppress a dismissed pair by computing the same id.
    """
    lo, hi = canonical_pair(a, b)
    return uuid5(_DEDUP_PAIR_NS, f"{project_id}|{lo}|{hi}")


def _surface_forms(entity: GraphEntity) -> list[str]:
    """Every non-empty surface form of an entity (both canonical names + aliases)."""
    candidates = [entity.canonical_name_pl, entity.canonical_name_en, *entity.aliases]
    return [name for name in candidates if name]


def _best_name_score(a: GraphEntity, b: GraphEntity) -> float:
    """Best RapidFuzz score across the cross-product of the two entities' surface forms.

    Symmetric (token_set_ratio is order-insensitive), so the pair is scored once. An
    entity with no surface forms scores 0.0 (it cannot be a name-duplicate of anything).
    """
    forms_a = _surface_forms(a)
    forms_b = _surface_forms(b)
    if not forms_a or not forms_b:
        return 0.0
    return max(name_match_score(form, forms_b) for form in forms_a)


def _best_cosine(a_vectors: list[list[float]], b_vectors: list[list[float]]) -> float | None:
    """Max cosine over the two entities' mention vectors, or None if none is usable.

    Skips zero-magnitude vectors (cosine is undefined there — `cosine_similarity` would
    raise) and dimension mismatches (defensive; real embeddings share one dimension).
    """
    best: float | None = None
    for va in a_vectors:
        if not any(x != 0.0 for x in va):
            continue
        for vb in b_vectors:
            if len(va) != len(vb) or not any(y != 0.0 for y in vb):
                continue
            score = cosine_similarity(va, vb)
            if best is None or score > best:
                best = score
    return best


def suggest_duplicate_pairs(
    snapshot: AcceptedSnapshot,
    *,
    name_floor: float,
    cosine_floor: float,
) -> list[DuplicateSuggestion]:
    """Rank the above-floor duplicate pairs over an accepted-graph snapshot (pure).

    A pair qualifies if its name score reaches `name_floor` *or* its best mention-vector
    cosine reaches `cosine_floor` (recall-first — either signal is enough). Results are
    ranked strongest-first by the normalised combined score, with a deterministic
    tiebreak: higher name score, then same-type pairs (the only place type is used — a
    soft nudge, never a filter, INV-4), then canonical id order.
    """
    entities = snapshot.entities
    ranked: list[tuple[float, float, bool, DuplicateSuggestion]] = []
    for i, a in enumerate(entities):
        for b in entities[i + 1 :]:
            name_score = _best_name_score(a, b)
            a_vectors = snapshot.mention_vectors.get(a.id, [])
            b_vectors = snapshot.mention_vectors.get(b.id, [])
            cosine = _best_cosine(a_vectors, b_vectors) if a_vectors and b_vectors else None
            qualifies = name_score >= name_floor or (cosine is not None and cosine >= cosine_floor)
            if not qualifies:
                continue
            combined = max(name_score / 100.0, cosine if cosine is not None else 0.0)
            lo, hi = canonical_pair(a.id, b.id)
            ranked.append(
                (
                    combined,
                    name_score,
                    a.type == b.type,
                    DuplicateSuggestion(
                        entity_id_lo=lo,
                        entity_id_hi=hi,
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
            not row[2],  # same-type pairs first (soft nudge)
            str(row[3].entity_id_lo),
            str(row[3].entity_id_hi),
        )
    )
    return [row[3] for row in ranked]
