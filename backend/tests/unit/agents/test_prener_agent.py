"""Unit tests for the PreNERAgent (spec §7 step 3, §6.5 agent table, Appendix B).

The Pre-NER baseline is deterministic: spaCy in, low-confidence candidate spans
out. No LLM, no router, no network — so these tests load the real spaCy models
and assert against the known proper nouns in the Appendix B.2 fixture.

Per spec §B.3 the baseline is *expected* to miss the worldbuilding entities
("Pani Wód", "Modlitwa Zarzutu") — those need the LLM ExtractionAgent (M2.S3).
So these tests only require the obvious proper-noun spans a statistical NER
model reliably finds, matching the handoff's "at least the obvious spans".

The spaCy-label → §3.2-taxonomy mapping is a pure function and is tested
directly, with no model load, mirroring `select_chunking_tier`.
"""

from __future__ import annotations

import importlib.util

import pytest

from story_forge.agents.prener_agent import PreNERAgent, map_spacy_label
from story_forge.domain.extraction import CandidateSpan

# The pretrained pipeline wheels are ~950 MB and live in the optional `models`
# dependency group, so they are not installed by default (CI stays lean — spec §6.7).
# Tests that actually load a model skip themselves when the model package is absent;
# run `uv sync --group models` to enable them locally. The pure mapping tests and the
# unsupported-language guard need no model and always run.
_REQUIRED_MODELS = ("pl_core_news_lg", "en_core_web_lg")
requires_models = pytest.mark.skipif(
    any(importlib.util.find_spec(m) is None for m in _REQUIRED_MODELS),
    reason="spaCy models not installed — run `uv sync --group models` (CI skips them)",
)

# Appendix B.2 — the canonical "Wody Święte" PL fragment and its EN gloss.
PL_PARAGRAPH = (
    "Stary Bronek siedział nad Czarną Hańczą od świtu. Wiedział, że Pani Wód nie "
    "lubi pośpiechu — kij musi leżeć cierpliwie, jak ofiarny nóż na ołtarzu. "
    "Pamiętał słowa stryja Kazimierza, który nauczył go pierwszej Modlitwy "
    'Zarzutu: "Nie biorę ryby. Ryba daje mi się sama, jeśli jestem godzien". '
    "Trzy karpie tego ranka — to znak. Loża z Augustowa dawno czekała na taki dowód."
)
EN_PARAGRAPH = (
    "Old Bronek had been sitting by the Czarna Hancza river since dawn. He knew "
    "the Lady of the Waters dislikes haste. He remembered the words of uncle "
    "Kazimierz, who taught him the first Casting Prayer. The Lodge of Augustow "
    "had long waited for such proof."
)


# ── Pure mapping: spaCy NER label → §3.2 taxonomy (no model load) ─────────────


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        # Polish NKJP label set (pl_core_news_lg).
        ("persName", "Character"),
        ("placeName", "Location"),
        ("geogName", "Location"),
        ("orgName", "Organization"),
        # English OntoNotes label set (en_core_web_lg).
        ("PERSON", "Character"),
        ("GPE", "Location"),
        ("LOC", "Location"),
        ("ORG", "Organization"),
    ],
)
def test_map_spacy_label_to_taxonomy(label: str, expected: str) -> None:
    assert map_spacy_label(label) == expected


@pytest.mark.parametrize("label", ["date", "DATE", "time", "CARDINAL", "MONEY", ""])
def test_map_spacy_label_drops_non_entity_labels(label: str) -> None:
    # Labels with no §3.2 home return None; the agent filters those spans out.
    assert map_spacy_label(label) is None


# ── Extraction against the real spaCy models (Appendix B.2 fixtures) ──────────


@pytest.fixture(scope="module")
def agent() -> PreNERAgent:
    """One agent for the module — loads spaCy models lazily, once."""
    return PreNERAgent()


def _types(spans: list[CandidateSpan]) -> set[str]:
    return {s.mapped_type for s in spans}


@requires_models
def test_extract_pl_finds_obvious_proper_nouns(agent: PreNERAgent) -> None:
    spans = agent.extract(PL_PARAGRAPH, language="pl")

    assert spans, "expected at least one candidate span from the PL fragment"
    # Every emitted span carries a mapped §3.2 type (unmapped labels dropped).
    assert all(s.mapped_type for s in spans)
    # Offsets are consistent: the slice round-trips to the span's own text.
    assert all(PL_PARAGRAPH[s.char_start : s.char_end] == s.text for s in spans)

    # Bronek is the clearest proper noun — a Character candidate must cover it.
    characters = [s for s in spans if s.mapped_type == "Character"]
    assert any("Bronek" in s.text for s in characters)
    # The baseline should also surface a place (Czarna Hańcza / Augustów).
    assert "Location" in _types(spans)


@requires_models
def test_extract_en_finds_obvious_proper_nouns(agent: PreNERAgent) -> None:
    spans = agent.extract(EN_PARAGRAPH, language="en")

    assert spans
    assert all(s.mapped_type for s in spans)
    assert all(EN_PARAGRAPH[s.char_start : s.char_end] == s.text for s in spans)

    # The baseline is for recall, not precision (spec §B.3): en_core_web_lg
    # mislabels the unfamiliar "Old Bronek" as ORG, so we only require that the
    # obvious proper noun is *covered* as some candidate — the LLM ExtractionAgent
    # corrects types in M2.S3. We also require the person → Character mapping to
    # fire on a person the model does get right ("uncle Kazimierz").
    assert any("Bronek" in s.text for s in spans)
    assert "Character" in _types(spans)


@requires_models
def test_extract_carries_the_raw_spacy_label(agent: PreNERAgent) -> None:
    # The candidate keeps the original spaCy label for debugging/provenance,
    # alongside the mapped taxonomy type.
    spans = agent.extract(EN_PARAGRAPH, language="en")
    person = next(s for s in spans if s.mapped_type == "Character")
    assert person.spacy_label  # non-empty raw label, e.g. "PERSON"


def test_unsupported_language_raises(agent: PreNERAgent) -> None:
    # No auto-detect at this layer — the Story already carries its language, so
    # an unsupported code is a programming error, not something to guess around.
    with pytest.raises(ValueError):
        agent.extract(EN_PARAGRAPH, language="fr")
