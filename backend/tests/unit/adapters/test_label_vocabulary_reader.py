"""Unit tests for LabelVocabularyReader — the vocabulary-assembly composition (S6a).

The reader composes two Neo4j `DISTINCT`-and-count reads with a label-string encoder into the
`(predicate, type)` entry lists the pure self-join consumes. Both collaborators are faked (no
graph, no ~2 GB embedding model), so these assert the *composition* the CI otherwise wouldn't
cover: labels/counts carried through, each label encoded, and an empty surface short-circuited.
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from story_forge.adapters.label_vocabulary_reader import LabelVocabularyReader
from story_forge.domain.label_synonyms import LabelCount


class _FakeNeo4j:
    def __init__(self, predicates: list[LabelCount], types: list[LabelCount]) -> None:
        self._predicates = predicates
        self._types = types

    async def list_predicate_vocabulary(self, project_id: UUID) -> list[LabelCount]:
        return self._predicates

    async def list_type_vocabulary(self, project_id: UUID) -> list[LabelCount]:
        return self._types


class _FakeEncoder:
    """Deterministic per-label vector; records what it was asked to encode."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def encode(self, text: str) -> list[float]:
        self.seen.append(text)
        return [float(len(text)), 1.0]


async def test_assembles_both_surfaces_with_counts_and_embeddings() -> None:
    neo4j = _FakeNeo4j(
        predicates=[LabelCount("PASSENGER_ON", 5), LabelCount("ON_SHIP", 2)],
        types=[LabelCount("PERSON", 9)],
    )
    encoder = _FakeEncoder()
    reader = LabelVocabularyReader(neo4j, encoder)  # type: ignore[arg-type]

    predicates, types = await reader.load_vocabulary(uuid4())

    assert [(e.label, e.count) for e in predicates] == [("PASSENGER_ON", 5), ("ON_SHIP", 2)]
    assert [(e.label, e.count) for e in types] == [("PERSON", 9)]
    # Every label was encoded, and the embedding is carried onto the entry.
    assert set(encoder.seen) == {"PASSENGER_ON", "ON_SHIP", "PERSON"}
    assert predicates[0].embedding == [float(len("PASSENGER_ON")), 1.0]


async def test_empty_surface_short_circuits_without_encoding() -> None:
    neo4j = _FakeNeo4j(predicates=[], types=[LabelCount("PERSON", 1)])
    encoder = _FakeEncoder()
    reader = LabelVocabularyReader(neo4j, encoder)  # type: ignore[arg-type]

    predicates, types = await reader.load_vocabulary(uuid4())

    assert predicates == []
    assert [e.label for e in types] == ["PERSON"]
    assert encoder.seen == ["PERSON"]  # the empty predicate surface encoded nothing


async def test_a_label_is_encoded_once_and_reused_across_loads() -> None:
    # The reader is app-lifetime, and the normalise-names queue reloads the whole vocabulary
    # after *every* decision. Re-encoding an unchanged label each time is what made one load
    # cost ~14 s on the real Oakhaven vocabulary (Session 100 walk), so labels are cached by
    # string: only labels never seen before reach the encoder.
    neo4j = _FakeNeo4j(
        predicates=[LabelCount("PASSENGER_ON", 5), LabelCount("ON_SHIP", 2)],
        types=[LabelCount("PERSON", 9)],
    )
    encoder = _FakeEncoder()
    reader = LabelVocabularyReader(neo4j, encoder)  # type: ignore[arg-type]
    project = uuid4()

    first_predicates, first_types = await reader.load_vocabulary(project)
    second_predicates, second_types = await reader.load_vocabulary(project)

    # Three distinct labels, encoded once in total — the second load hits the cache.
    assert encoder.seen == ["PASSENGER_ON", "ON_SHIP", "PERSON"]
    # And the cached load returns identical data, not a degraded one.
    assert [(e.label, e.count, e.embedding) for e in second_predicates] == [
        (e.label, e.count, e.embedding) for e in first_predicates
    ]
    assert [(e.label, e.count, e.embedding) for e in second_types] == [
        (e.label, e.count, e.embedding) for e in first_types
    ]


async def test_only_labels_not_seen_before_reach_the_encoder() -> None:
    # A rename changes the vocabulary by roughly one label, so the next load must pay for that
    # one label only — not the whole vocabulary again.
    neo4j = _FakeNeo4j(predicates=[LabelCount("STANDS_ON", 1)], types=[])
    encoder = _FakeEncoder()
    reader = LabelVocabularyReader(neo4j, encoder)  # type: ignore[arg-type]
    project = uuid4()
    await reader.load_vocabulary(project)

    # The vocabulary shifts: STANDS_ON survives, STAND_ON is new.
    neo4j._predicates = [LabelCount("STANDS_ON", 1), LabelCount("STAND_ON", 3)]
    predicates, _ = await reader.load_vocabulary(project)

    assert encoder.seen == ["STANDS_ON", "STAND_ON"]
    assert [(e.label, e.count) for e in predicates] == [("STANDS_ON", 1), ("STAND_ON", 3)]


async def test_a_repeated_label_within_one_load_is_encoded_once() -> None:
    # The same string can occur on *both* surfaces (a predicate and a type may share a label,
    # both are open-world free strings — INV-4), and it is one vector either way.
    neo4j = _FakeNeo4j(predicates=[LabelCount("GUARD", 2)], types=[LabelCount("GUARD", 7)])
    encoder = _FakeEncoder()
    reader = LabelVocabularyReader(neo4j, encoder)  # type: ignore[arg-type]

    predicates, types = await reader.load_vocabulary(uuid4())

    assert encoder.seen == ["GUARD"]
    assert predicates[0].embedding == types[0].embedding
    assert (predicates[0].count, types[0].count) == (2, 7)


async def test_the_cache_is_shared_across_projects_not_scoped_to_one() -> None:
    # The reader is app-lifetime, and the key is the bare label *by design*: an embedding depends
    # only on the string, so two projects using "PERSON" need the same vector. Pinned because the
    # tempting "safety" refactor — keying on (project_id, label) — would pass every other test here
    # while silently restoring the ~14 s load for anyone working a second project.
    shared = LabelCount("PERSON", 4)
    neo4j = _FakeNeo4j(predicates=[], types=[shared])
    encoder = _FakeEncoder()
    reader = LabelVocabularyReader(neo4j, encoder)  # type: ignore[arg-type]

    _, first_types = await reader.load_vocabulary(uuid4())
    _, second_types = await reader.load_vocabulary(uuid4())  # a DIFFERENT project

    assert encoder.seen == ["PERSON"]
    assert first_types[0].embedding == second_types[0].embedding


async def test_concurrent_cold_loads_encode_each_label_once() -> None:
    # Two requests arriving on a cold cache must not both start an encode — each would trip
    # EmbeddingAgent's unguarded lazy model init and load ~2 GB twice. The lock serialises them and
    # the second re-checks, so it finds the work already done.
    neo4j = _FakeNeo4j(predicates=[LabelCount("HUNTS", 1)], types=[LabelCount("PERSON", 2)])
    encoder = _FakeEncoder()
    reader = LabelVocabularyReader(neo4j, encoder)  # type: ignore[arg-type]

    await asyncio.gather(
        reader.load_vocabulary(uuid4()),
        reader.load_vocabulary(uuid4()),
        reader.load_vocabulary(uuid4()),
    )

    assert sorted(encoder.seen) == ["HUNTS", "PERSON"]
