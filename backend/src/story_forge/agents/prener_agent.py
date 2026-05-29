"""Pre-NER baseline agent (spec §7 step 3, §6.5 agent table).

Deterministic — no LLM, no router, no network. spaCy runs NER over a paragraph
and we emit the entity mentions as low-confidence `CandidateSpan`s, each typed
against the §3.2 taxonomy. These are hints for the LLM ExtractionAgent (M2.S3);
spec §B.3 is explicit that this baseline misses worldbuilding entities like
"Pani Wód" or "Modlitwa Zarzutu" — recovering those is the LLM's job, not ours.

spaCy itself is imported lazily inside `_pipeline` (not at module top) and the
loaded models are cached per language, so callers that only need the pure
`map_spacy_label` mapping — or that hit the unsupported-language guard — pay no
import or model-load cost. Language is supplied by the caller (the Story already
carries it, spec §3.1); we do not auto-detect at this layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from story_forge.domain.extraction import CandidateSpan

if TYPE_CHECKING:
    from spacy.language import Language

# spaCy NER label → §3.2 entity type. Covers both label sets we use: the Polish
# NKJP set (pl_core_news_lg) and the English OntoNotes set (en_core_web_lg).
# Labels with no §3.2 home (dates, numbers, ordinals, …) are intentionally
# absent so `map_spacy_label` returns None and the agent drops those spans.
_LABEL_TO_TYPE: dict[str, str] = {
    # Polish — NKJP
    "persName": "Character",
    "placeName": "Location",
    "geogName": "Location",
    "orgName": "Organization",
    # English — OntoNotes
    "PERSON": "Character",
    "GPE": "Location",
    "LOC": "Location",
    "ORG": "Organization",
}

_MODEL_BY_LANGUAGE: dict[str, str] = {
    "pl": "pl_core_news_lg",
    "en": "en_core_web_lg",
}


def map_spacy_label(label: str) -> str | None:
    """Map a raw spaCy NER label to a §3.2 type, or None to drop the span."""
    return _LABEL_TO_TYPE.get(label)


class PreNERAgent:
    """Per-paragraph spaCy baseline emitting typed `CandidateSpan`s."""

    def __init__(self) -> None:
        self._pipelines: dict[str, Language] = {}

    def _pipeline(self, language: str) -> Language:
        """Lazily load and cache the spaCy model for `language`."""
        model_name = _MODEL_BY_LANGUAGE.get(language)
        if model_name is None:
            raise ValueError(f"unsupported language for Pre-NER: {language!r}")
        if language not in self._pipelines:
            import spacy

            self._pipelines[language] = spacy.load(model_name)
        return self._pipelines[language]

    def extract(self, paragraph_text: str, language: str) -> list[CandidateSpan]:
        """Return the proper-noun candidates spaCy finds in one paragraph."""
        nlp = self._pipeline(language)
        candidates: list[CandidateSpan] = []
        for ent in nlp(paragraph_text).ents:
            mapped_type = map_spacy_label(ent.label_)
            if mapped_type is None:
                continue
            candidates.append(
                CandidateSpan(
                    text=ent.text,
                    char_start=ent.start_char,
                    char_end=ent.end_char,
                    spacy_label=ent.label_,
                    mapped_type=mapped_type,
                )
            )
        return candidates
