"""LabelVocabularyReader — assembles the label vocabularies the synonym self-join scores (S6a).

The S6 suggest half needs, per project, the two distinct label vocabularies (relationship
predicate names, entity-type labels) with their occurrence counts *and* a label-string
embedding for the semantic rung (DM-NN-2). This reader does that assembly in one pass: two
Neo4j `DISTINCT`-and-count reads, then a single off-thread encode of the labels it has not
already embedded — so the pure `suggest_label_synonyms` fn downstream is fed ready data and
stays store-free.

The **embedding cache** is what keeps the normalise-names queue usable: that queue reloads the
whole vocabulary after every decision, so without it each load re-encodes an unchanged
vocabulary from scratch (~14 s on the real Oakhaven graph). See `_encode_labels`.

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
from story_forge.domain.label_synonyms import LabelVocabularyEntry


class LabelEncoder(Protocol):
    """A label-string encoder (structurally satisfied by `EmbeddingAgent`)."""

    def encode(self, text: str) -> list[float]: ...


class LabelVocabularyReader:
    """Reads a project's predicate + type vocabularies from Neo4j and embeds their labels."""

    def __init__(self, neo4j_repo: Neo4jRepo, encoder: LabelEncoder) -> None:
        self._neo4j = neo4j_repo
        self._encoder = encoder
        # label → vector, for the app's lifetime. A label's embedding depends on nothing but the
        # string, so it can never go stale; see `_encode_labels` for why this is load-bearing.
        self._embeddings: dict[str, list[float]] = {}
        # Serialises the encode step across *requests*. `asyncio.gather` only ever made the two
        # vocabulary reads concurrent within one request; two concurrent requests on a cold cache
        # would each hop to a worker thread and each trip `EmbeddingAgent._model()`'s unguarded
        # lazy init, loading the ~2 GB model twice (an OOM on an 8 GB dev host).
        self._encode_lock = asyncio.Lock()

    async def load_vocabulary(
        self, project_id: UUID
    ) -> tuple[list[LabelVocabularyEntry], list[LabelVocabularyEntry]]:
        """The (predicate, type) vocabularies as embedded entries, ready for the self-join."""
        predicates, types = await asyncio.gather(
            self._neo4j.list_predicate_vocabulary(project_id),
            self._neo4j.list_type_vocabulary(project_id),
        )
        # Encode in ONE off-thread pass, and only what isn't cached — blocking + CPU-bound, so off
        # the loop. When every label is already cached there is nothing to encode and no thread hop
        # at all, which is the common case after the first load.
        counts = [*predicates, *types]
        if any(c.label not in self._embeddings for c in counts):
            # Under the lock, so concurrent requests on a cold cache can't each start a model load
            # (see `_encode_lock`). Re-check `missing` *inside* it: whoever waited may find the
            # labels already encoded by the holder and skip the thread hop entirely.
            async with self._encode_lock:
                missing = list(
                    dict.fromkeys(c.label for c in counts if c.label not in self._embeddings)
                )
                if missing:
                    await asyncio.to_thread(self._encode_labels, missing)
        embeddings = [self._embeddings[c.label] for c in counts]
        entries = [
            LabelVocabularyEntry(label=c.label, count=c.count, embedding=embedding)
            for c, embedding in zip(counts, embeddings, strict=True)
        ]
        return entries[: len(predicates)], entries[len(predicates) :]

    def _encode_labels(self, labels: list[str]) -> None:
        """Encode labels into the cache. Runs off the event loop — see `load_vocabulary`.

        This is what makes the normalise-names queue usable. That queue reloads the *whole*
        vocabulary after every decision, and re-encoding every unchanged label made one load cost
        ~14 s on the real Oakhaven vocabulary (227 predicates + 45 types) — long enough that
        deciding a few pairs in quick succession queued refetches until the browser ran out of
        connections and the rest of the app starved behind them (Session 100 walk). A rename
        changes the vocabulary by about one label, so with the cache the next load encodes one
        label instead of 272.

        Unbounded, and the real bound is wider than one project: the reader is constructed once in
        `main.py` and held on `app.state`, so this dict accumulates the union of **every project's**
        predicate and type labels for the process lifetime — plus every label ever renamed *away*,
        since nothing evicts. Working a 300-item queue therefore leaves a few hundred dead keys
        behind. That is accepted rather than overlooked: an entry is never *invalid* (a vector
        depends only on its string, which is also why the key is the bare label and sharing across
        projects is correct), and at ~25 KB per vector a few thousand labels is a few tens of MB
        against a process already holding a ~2 GB model. Revisit if a corpus ever pushes the label
        vocabulary into the tens of thousands — an LRU is the obvious answer, not per-project keys,
        which would forfeit the sharing this exists for.
        """
        for label in labels:
            self._embeddings[label] = self._encoder.encode(label)
