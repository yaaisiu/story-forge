"""EmbeddingAgent — the §3.3 Stage-2 encoder of the dedupe cascade (M3.S2).

Deterministic local compute — no LLM, no router, no network at inference. Encodes a
candidate's context (its source sentence, spec §3.3 Stage 2) to a 768-dim vector with
sentence-transformers; `MatchingAgent.stage2` then takes the max cosine of that vector
against an entity's stored mention vectors.

`sentence_transformers` (and the ~2 GB torch stack under it) is imported lazily inside
`_model`, not at module top, and the loaded model is cached — so importing this module,
constructing the agent, or reading the pin constants costs nothing. This is the same
deterministic-local-NLP exception that lets `PreNERAgent` import spaCy directly
(`src/story_forge/AGENTS.md`): a single local implementation, no provider to abstract.

The weights are pinned by **immutable commit revision** (the §6.7 HuggingFace-model
channel): `_model` loads `MODEL_REPO_ID` at `MODEL_REVISION`, so even a cold cache fetches
the exact pinned bytes, never HEAD — the integrity analogue of a locked wheel hash.
`scripts/pin_hf_model.py` pre-fetches and verifies the same revision (it imports these
constants, so the pin script and the runtime loader agree by construction).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

# The Stage-2 embedding model (DM2): paraphrase-multilingual-mpnet-base-v2 — multilingual
# PL/EN, 768-dim (the spec §3.3 example). Pinned by commit SHA per the §6.7 HF-model
# channel; that commit is dated 2025-08-19, clearing the 14-day soak at pin time. Loaded
# on CPU — the dev host is GPU-less (spec §6.5).
MODEL_REPO_ID = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
# pragma: allowlist secret — a model commit SHA (content address), not a credential.
MODEL_REVISION = "4328cf26390c98c5e3c738b4460a05b95f4911f5"  # pragma: allowlist secret
EMBEDDING_DIM = 768


class EmbeddingAgent:
    """Encodes text to a 768-dim vector with the pinned multilingual model (CPU)."""

    def __init__(self) -> None:
        self._encoder: SentenceTransformer | None = None

    def _model(self) -> SentenceTransformer:
        """Lazily load and cache the pinned sentence-transformers model on CPU."""
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer

            self._encoder = SentenceTransformer(
                MODEL_REPO_ID, revision=MODEL_REVISION, device="cpu"
            )
        return self._encoder

    def encode(self, text: str) -> list[float]:
        """Encode one text (a candidate's context sentence) to a 768-dim vector."""
        vector = self._model().encode(text, normalize_embeddings=False)
        return [float(x) for x in vector]
