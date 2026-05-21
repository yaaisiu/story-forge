"""Unit tests for PL/EN detection (`domain/language.py`).

The helper seeds langdetect for determinism, so these assertions are stable.
"""

from __future__ import annotations

import pytest

from story_forge.domain.language import detect_language


def test_detects_polish() -> None:
    pl = (
        "Janek wszedł do starego młyna i rozejrzał się dookoła. "
        "Było ciemno, cicho i pachniało wilgotnym drewnem. "
        "Gdzieś w górze przeleciał nietoperz, a podłoga zaskrzypiała pod jego butami."
    )
    assert detect_language(pl) == "pl"


def test_detects_english() -> None:
    en = (
        "John walked into the old mill and looked around. "
        "It was dark, quiet, and smelled of damp wood. "
        "Somewhere above him a bat flew past, and the floor creaked under his boots."
    )
    assert detect_language(en) == "en"


def test_blank_text_raises() -> None:
    with pytest.raises(ValueError):
        detect_language("   \n  ")
