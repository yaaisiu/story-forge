"""Unit tests for EmbeddingAgent (§3.3 Stage-2 encoder, M3.S2).

Two tiers, like test_prener_agent.py: the pure/structural tests (lazy construction,
the pinned-revision guard) always run in CI; the model-loading test skips when the
optional `embeddings` group is absent (CI stays lean — spec §6.7). Per the backend
AGENTS.md rule we assert the agent's *contract* (768-dim float vector, lazy load,
revision pinned), never the model's embedding *accuracy*.
"""

from __future__ import annotations

import importlib.util

import pytest

from story_forge.agents.embedding_agent import (
    EMBEDDING_DIM,
    MODEL_REVISION,
    EmbeddingAgent,
)

# sentence-transformers + torch (~2 GB) live in the optional `embeddings` group, not
# installed by default. The model-loading test skips itself when absent; run
# `uv sync --group embeddings` to enable it locally (CI skips it).
requires_embeddings = pytest.mark.skipif(
    importlib.util.find_spec("sentence_transformers") is None,
    reason="embeddings group not installed — run `uv sync --group embeddings` (CI skips it)",
)


# --- structural / pure (always run in CI) ----------------------------------


def test_construction_does_not_load_the_model() -> None:
    """Constructing the agent must not import or load the heavy stack (laziness)."""
    agent = EmbeddingAgent()
    assert agent._encoder is None


def test_model_revision_is_a_pinned_40char_sha() -> None:
    """The §6.7 HF-model channel pins by immutable commit SHA — guard against a
    non-pinned/HEAD load slipping in (an integrity regression)."""
    assert len(MODEL_REVISION) == 40
    assert all(c in "0123456789abcdef" for c in MODEL_REVISION)


def test_embedding_dim_is_768() -> None:
    assert EMBEDDING_DIM == 768


# --- model load (skips in CI; the verify-at-build contract) -----------------


@requires_embeddings
def test_encode_emits_a_768_float_vector_on_cpu() -> None:
    agent = EmbeddingAgent()
    vector = agent.encode("Janek z młyna spojrzał na rzekę.")
    assert len(vector) == EMBEDDING_DIM
    assert all(isinstance(x, float) for x in vector)
    # A real embedding is never the zero vector — guards a silently-empty load.
    assert any(x != 0.0 for x in vector)
