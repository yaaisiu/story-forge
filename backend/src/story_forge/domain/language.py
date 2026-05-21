"""Detect the language of a story's text (spec §3.1, §7 step 1).

PL/EN is the scope for V1; `langdetect` discriminates them reliably on
prose-length input. The library is non-deterministic by default (it samples),
so we pin its seed at import for reproducible output across runs and tests.

I/O-pure: text in, an ISO 639-1 code out (in practice "pl" or "en" for this
app's inputs). Blank or feature-less text raises `ValueError` so the caller can
reject the upload with a 400 rather than persisting a guessed language.
"""

from __future__ import annotations

from langdetect import DetectorFactory, LangDetectException
from langdetect import detect as _detect

# Deterministic results: without a fixed seed langdetect's sampling can return
# different codes for the same short input on different runs.
DetectorFactory.seed = 0


def detect_language(text: str) -> str:
    """Return the detected ISO 639-1 language code (e.g. "pl", "en")."""
    if not text.strip():
        raise ValueError("cannot detect language of empty text")
    try:
        return str(_detect(text))
    except LangDetectException as exc:
        raise ValueError("could not detect a language from the text") from exc
