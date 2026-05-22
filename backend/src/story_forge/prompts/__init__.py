"""Prompt-template loading (spec §6.5 — prompts live here, never as f-strings).

One Jinja2 template per (logical prompt, language): `<name>.<lang>.j2`. A template
is a chat transcript marked up with `[SYSTEM]` / `[USER]` / `[ASSISTANT]` lines;
`render_messages` renders it with the given context and splits it into the typed
`list[Message]` a provider expects. Keeping the role markup inside the template
(rather than splitting roles in code) lets the whole prompt be read and reviewed
as one artifact — it mirrors the Appendix C.1/C.2 skeletons one-to-one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from story_forge.adapters.llm.base import Message

_PROMPTS_DIR = Path(__file__).parent

# autoescape stays off: these are LLM prompts, not HTML; StrictUndefined turns a
# missing template variable into a loud error instead of a silent empty string.
_env = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    autoescape=False,
    undefined=StrictUndefined,
    keep_trailing_newline=True,
)

_ROLE_MARKERS: dict[str, Literal["system", "user", "assistant"]] = {
    "[SYSTEM]": "system",
    "[USER]": "user",
    "[ASSISTANT]": "assistant",
}


def render_messages(name: str, language: str, /, **context: object) -> list[Message]:
    """Render `<name>.<language>.j2` into chat messages.

    Raises `jinja2.TemplateNotFound` if no template exists for that language —
    callers translate that into their own domain error.
    """
    template = _env.get_template(f"{name}.{language}.j2")
    return _split_into_messages(template.render(**context))


def _split_into_messages(text: str) -> list[Message]:
    """Split a rendered transcript on `[ROLE]` marker lines into messages."""
    segments: list[tuple[Literal["system", "user", "assistant"], list[str]]] = []
    for line in text.splitlines():
        role = _ROLE_MARKERS.get(line.strip())
        if role is not None:
            segments.append((role, []))
        elif segments:  # lines before the first marker are ignored
            segments[-1][1].append(line)
    messages = [Message(role=role, content="\n".join(lines).strip()) for role, lines in segments]
    messages = [m for m in messages if m.content]
    if not messages:
        raise ValueError("prompt template produced no messages")
    return messages
