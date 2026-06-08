"""Unit tests for the shared `extract_json` markdown-fence stripper.

Both ChunkingAgent and ExtractionAgent feed model output through this before
Pydantic validation, so its edge cases are exercised directly here rather than only
through each agent.
"""

from __future__ import annotations

import pytest

from story_forge.agents.json_output import extract_json

JSON = '{"entities":[],"relations":[]}'


@pytest.mark.parametrize(
    "wrapped",
    [
        JSON,  # no fence — passes through
        f"  {JSON}  ",  # surrounding whitespace only
        f"```json\n{JSON}\n```",  # fenced with language tag on its own line
        f"```\n{JSON}\n```",  # fenced without a language tag
        f"```json\n{JSON}```",  # no trailing newline before the closing fence
        f"```json{JSON}```",  # one-liner: language tag glued to the JSON (the N1 case)
        f"```{JSON}```",  # one-liner with no language tag
    ],
)
def test_extract_json_recovers_the_payload(wrapped: str) -> None:
    assert extract_json(wrapped) == JSON


def test_extract_json_handles_a_json_array_one_liner() -> None:
    # The leading-letter strip must not eat a `[` (array) — only the language tag.
    assert extract_json("```json[1,2,3]```") == "[1,2,3]"
