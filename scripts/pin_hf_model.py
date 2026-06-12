#!/usr/bin/env python3
"""Pin + verify the Stage-2 embedding model (§6.7 HuggingFace-model channel, M3.S2).

The Stage-2 model — paraphrase-multilingual-mpnet-base-v2 (768-dim, multilingual PL/EN) —
ships on the HuggingFace Hub, not PyPI, and sentence-transformers' default is to fetch it
from the Hub at first use: exactly the unpinned runtime fetch spec §6.7 forbids (the same
hole the spaCy-wheel channel closed). This script pins it by the model repo's **immutable
commit revision SHA** via a one-off `huggingface_hub.snapshot_download(repo_id,
revision=<40-char-SHA>)` — content-addressed bytes that cannot change under a fixed
revision, the integrity analogue of a locked wheel SHA-256.

The repo id, revision SHA, and expected dimensionality live in `EmbeddingAgent`
(`backend/src/story_forge/agents/embedding_agent.py`) and are imported here, so the pin
script and the runtime loader agree by construction — there is one home for the SHA.

The 14-day soak for the model *artifact* is a procedural check (the weights are not in
`uv.lock` for check_dependency_age.py to see): the pinned commit is dated **2025-08-19**
(verified at pin time via the Hub API), comfortably clearing the cutoff. OSV/advisory
scanning is N/A for the weights (not indexed, same as the spaCy wheels); residual
supply-chain risk is bounded by the official `sentence-transformers` publisher, the
immutable revision SHA, and the artifact carrying only weights + tokenizer config.

Run it (needs the optional `embeddings` group) from `backend/`:

    uv sync --group embeddings
    uv run python ../scripts/pin_hf_model.py        # downloads + verifies (CPU, 768-dim)
    uv run python ../scripts/pin_hf_model.py --download-only   # fetch the bytes, skip load

Exit codes: 0 = pinned (and verified, unless --download-only); 1 = any failure.
"""

from __future__ import annotations

import sys

from story_forge.agents.embedding_agent import (
    EMBEDDING_DIM,
    MODEL_REPO_ID,
    MODEL_REVISION,
    EmbeddingAgent,
)


def main(argv: list[str]) -> int:
    download_only = "--download-only" in argv[1:]

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print(
            "FAIL: huggingface_hub not installed — run `uv sync --group embeddings` first.",
            file=sys.stderr,
        )
        return 1

    print(f"Pinning {MODEL_REPO_ID} @ {MODEL_REVISION} ...")
    try:
        path = snapshot_download(repo_id=MODEL_REPO_ID, revision=MODEL_REVISION)
    except Exception as exc:  # noqa: BLE001 — surface any Hub/network error as a clean FAIL
        print(f"FAIL: snapshot_download failed: {exc}", file=sys.stderr)
        return 1
    print(f"OK: snapshot present at {path}")

    if download_only:
        return 0

    # Verify-at-build: the model loads on this (CPU) host and emits EMBEDDING_DIM dims.
    print("Verifying load + encode on CPU ...")
    try:
        vector = EmbeddingAgent().encode("Janek z młyna spojrzał na rzekę.")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: model load / encode failed: {exc}", file=sys.stderr)
        return 1
    if len(vector) != EMBEDDING_DIM:
        print(f"FAIL: expected {EMBEDDING_DIM} dims, got {len(vector)}", file=sys.stderr)
        return 1
    print(f"OK: encode emitted {len(vector)} dims on CPU.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
