"""LabelVocabularyReader — assembles the label vocabularies the synonym self-join scores (S6a).

The S6 suggest half needs, per project, the two distinct label vocabularies (relationship
predicate names, entity-type labels) with their occurrence counts *and* a label-string
embedding for the semantic rung (DM-NN-2). This reader does that assembly in one pass: two
Neo4j `DISTINCT`-and-count reads, then a single off-thread encode of the labels — so the
pure `suggest_label_synonyms` fn downstream is fed ready data and stays store-free.

Like `AcceptedEntityReader`, it produces a domain shape and stays free of an `agents/`
import: it types its encoder against the local `LabelEncoder` Protocol, which
`EmbeddingAgent` satisfies structurally (the `Router`-Protocol pattern — the concrete agent
meets the reader only at the `main.py` composition root). That also lets a test inject a fake
encoder instead of loading the ~2 GB model.
"""

from __future__ import annotations

import asyncio
from typing import Protocol
from uuid import UUID

from story_forge.adapters.neo4j_repo import Neo4jRepo
from story_forge.domain.label_synonyms import LabelCount, LabelVocabularyEntry


class LabelEncoder(Protocol):
    """A label-string encoder (structurally satisfied by `EmbeddingAgent`)."""

    def encode(self, text: str) -> list[float]: ...


class LabelVocabularyReader:
    """Reads a project's predicate + type vocabularies from Neo4j and embeds their labels."""

    def __init__(self, neo4j_repo: Neo4jRepo, encoder: LabelEncoder) -> None:
        self._neo4j = neo4j_repo
        self._encoder = encoder

    async def load_vocabulary(
        self, project_id: UUID
    ) -> tuple[list[LabelVocabularyEntry], list[LabelVocabularyEntry]]:
        """The (predicate, type) vocabularies as embedded entries, ready for the self-join."""
        predicates, types = await asyncio.gather(
            self._neo4j.list_predicate_vocabulary(project_id),
            self._neo4j.list_type_vocabulary(project_id),
        )
        predicate_entries, type_entries = await asyncio.gather(
            self._to_entries(predicates),
            self._to_entries(types),
        )
        return predicate_entries, type_entries

    async def _to_entries(self, counts: list[LabelCount]) -> list[LabelVocabularyEntry]:
        if not counts:
            return []
        # Encoding the ~2 GB model is CPU-bound and blocking — run it off the event loop.
        embeddings = await asyncio.to_thread(self._encode_labels, [c.label for c in counts])
        return [
            LabelVocabularyEntry(label=c.label, count=c.count, embedding=embedding)
            for c, embedding in zip(counts, embeddings, strict=True)
        ]

    def _encode_labels(self, labels: list[str]) -> list[list[float]]:
        return [self._encoder.encode(label) for label in labels]
