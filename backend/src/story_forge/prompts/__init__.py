"""Prompt-template loading (spec §6.5 — prompts live here, never as f-strings).

One Jinja2 template per (logical prompt, language): `<name>.<lang>.j2`. A template
is a chat transcript marked up with `[SYSTEM]` / `[USER]` / `[ASSISTANT]` lines.

`render_messages` splits the *template source* on those markers first, then renders
each segment body with the context. Roles therefore come only from the trusted
template author — never from rendered output. This is deliberate: rendering first
and reparsing the result would let untrusted content (e.g. an uploaded story
containing a line `[SYSTEM]`) forge new turns and rewrite the transcript. User
content stays confined to the body it was rendered into.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

from story_forge.adapters.llm.base import Message


class PromptNotFound(Exception):
    """No prompt template exists for the requested name/language.

    Wraps Jinja2's `TemplateNotFound` so callers (agents) depend on this layer's
    error, not on the templating library — keeping jinja2 out of the agent layer.
    """


_PROMPTS_DIR = Path(__file__).parent

# autoescape stays off: these are LLM prompts, not HTML; StrictUndefined turns a
# missing template variable into a loud error instead of a silent empty string.
_loader = FileSystemLoader(_PROMPTS_DIR)
_env = Environment(
    loader=_loader,
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

    Raises `PromptNotFound` if no template exists for that language.
    """
    try:
        source, _, _ = _loader.get_source(_env, f"{name}.{language}.j2")
    except TemplateNotFound as exc:
        raise PromptNotFound(f"no prompt template {name!r} for language {language!r}") from exc

    messages: list[Message] = []
    for role, body in _split_template(source):
        # Render each segment separately: markers were already taken from the
        # trusted source above, so user content rendered here cannot add turns.
        content = _env.from_string(body).render(**context).strip()
        if content:
            messages.append(Message(role=role, content=content))
    if not messages:
        raise ValueError("prompt template produced no messages")
    return messages


def _split_template(source: str) -> list[tuple[Literal["system", "user", "assistant"], str]]:
    """Split a template's source on `[ROLE]` marker lines into (role, body) pairs."""
    segments: list[tuple[Literal["system", "user", "assistant"], list[str]]] = []
    for line in source.splitlines():
        role = _ROLE_MARKERS.get(line.strip())
        if role is not None:
            segments.append((role, []))
        elif segments:  # lines before the first marker are ignored
            segments[-1][1].append(line)
    return [(role, "\n".join(lines)) for role, lines in segments]
