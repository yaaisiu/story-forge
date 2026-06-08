"""Shared helpers for turning a model's raw text into parseable JSON.

Every agent that asks an LLM for structured output meets the same nuisance: a
sampling model often wraps its JSON in a markdown code fence (```json … ```)
even when told not to. `extract_json` strips that fence so the agent can hand the
inner text to Pydantic. It lives here, shared by `ChunkingAgent` and
`ExtractionAgent`, rather than duplicated per agent — the moment it earned a home
was the second consumer.

It does *not* parse or validate — that stays in each agent, which owns its schema
and its retry loop. This is purely the text-cleanup step before validation.
"""

from __future__ import annotations


def extract_json(text: str) -> str:
    """Strip a surrounding markdown code fence if the model wrapped its JSON.

    Handles a leading ```` ```json ```` / ```` ``` ```` line and a trailing ```` ``` ````.
    Text with no fence is returned stripped of surrounding whitespace, unchanged
    otherwise — so a clean JSON response passes through untouched.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped[3:]
        fence = stripped.rfind("```")
        if fence != -1:
            stripped = stripped[:fence]
    return stripped.strip()
