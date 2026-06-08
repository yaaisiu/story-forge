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

import string


def extract_json(text: str) -> str:
    """Strip a surrounding markdown code fence if the model wrapped its JSON.

    Handles the body on its own line after a ```` ```json ```` / ```` ``` ```` opener,
    and the one-line form (```` ```json{…}``` ````) where a language tag is glued to
    the JSON. Text with no fence is returned with only surrounding whitespace stripped
    — so a clean JSON response passes through untouched.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    body = stripped[3:]  # drop the opening ```
    # The body is on the next line; or, for a one-liner (```json{…}```), right after a
    # language tag glued to the JSON — drop the tag's leading word characters.
    newline = body.find("\n")
    body = body[newline + 1 :] if newline != -1 else body.lstrip(string.ascii_letters)

    fence = body.rfind("```")
    if fence != -1:
        body = body[:fence]  # drop the closing fence
    return body.strip()
