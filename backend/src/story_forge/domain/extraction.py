"""Entity-extraction domain types (spec §3.2, §7 steps 3–4).

`CandidateSpan` is the Pre-NER baseline's output (spec §7 step 3): a single
low-confidence proper-noun span found by spaCy and typed against the §3.2
taxonomy. It is deliberately minimal — text, char offsets, the raw spaCy label
(kept for provenance/debugging), and the mapped taxonomy type. The richer
entity shape (aliases, free-form properties, embedding) belongs to the LLM
ExtractionAgent in M2.S3, which consumes these candidates as hints; we do not
build that shape here (spec §3.2; no speculative fields).
"""

from __future__ import annotations

from pydantic import BaseModel


class CandidateSpan(BaseModel):
    """One spaCy-found entity candidate, typed against the §3.2 taxonomy."""

    text: str  # the surface form, exactly as it appears in the paragraph
    char_start: int  # offset into the paragraph; text == paragraph[start:end]
    char_end: int
    spacy_label: str  # raw spaCy NER label, e.g. "persName" (PL) or "PERSON" (EN)
    mapped_type: str  # §3.2 type, e.g. "Character" | "Location" | "Organization"
