"""Unit tests for LabelVocabularyReader — the vocabulary-assembly composition (S6a).

The reader composes two Neo4j `DISTINCT`-and-count reads with a label-string encoder into the
`(predicate, type)` entry lists the pure self-join consumes. Both collaborators are faked (no
graph, no ~2 GB embedding model), so these assert the *composition* the CI otherwise wouldn't
cover: labels/counts carried through, each label encoded, and an empty surface short-circuited.
"""

from __future__ import annotations

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
