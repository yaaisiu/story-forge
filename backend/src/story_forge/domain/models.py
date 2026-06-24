"""Document-tree domain models (spec §6.4).

The structural hierarchy is Project → Story → Chapter → Scene → Paragraph.
These are plain Pydantic models — no persistence concerns leak in here. IDs are
app-generated UUIDs (stable across the Postgres/Neo4j split: paragraph IDs are
referenced from Neo4j relations and `entity_mentions`), and timestamps default
to "now" so a freshly constructed object is already persistable.

Field names match the database columns and the JSON wire format one-to-one
(notably `order_index`, not the reserved word `order`) so there is no mapping
layer to reason about.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(UTC)


class Project(BaseModel):
    """Top-level container for one author's body of work."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    language: str  # "pl" | "en" — the project's primary language
    style_anchor: str | None = None
    created_at: datetime = Field(default_factory=_now)


class Story(BaseModel):
    """One narrative document uploaded into a project."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    title: str
    raw_text: str
    ingested_at: datetime = Field(default_factory=_now)


class Chapter(BaseModel):
    """A top-level division of a story; ordered among its siblings."""

    id: UUID = Field(default_factory=uuid4)
    story_id: UUID
    order_index: int
    title: str | None = None
    summary: str | None = None


class Scene(BaseModel):
    """A division of a chapter; ordered among its siblings."""

    id: UUID = Field(default_factory=uuid4)
    chapter_id: UUID
    order_index: int
    title: str | None = None
    summary: str | None = None


class Paragraph(BaseModel):
    """The leaf unit of text; ordered among its siblings within a scene.

    `embedding` is the pgvector(768) column; it stays None until the embedding
    pipeline (a later milestone) populates it.
    """

    id: UUID = Field(default_factory=uuid4)
    scene_id: UUID
    order_index: int
    content: str
    content_normalized: str | None = None
    embedding: list[float] | None = None


class EntityMention(BaseModel):
    """A back-reference recording where a graph entity appears in the text (§6.4).

    The cross-store seam (OQ-1): `paragraph_id` references a Postgres `paragraphs`
    row (a real FK, cascades with the tree), but `entity_id` references a **Neo4j**
    node and so carries *no* Postgres FK — the two stores cannot share a transaction.
    `span_start` / `span_end` / `confidence` are nullable because the LLM extraction
    path yields an evidence quote, not reliable character offsets.

    `embedding` is the per-mention context vector (pgvector(768), §3.3 Stage 2). It
    stays None under the foundation-only M3.S2 scope — EmbeddingAgent is built but not
    wired into the live extraction path until the cascade lands (M3.S4).

    `source` (M4.S3c) is `'extraction'` for a cascade-written mention (NULL offsets —
    highlighting is render-time search, DM-IH-1) and `'manual'` for a human tag carrying
    real `span_start`/`span_end` that overlays and wins over search (DM-S3c-1 B). An
    explicit flag, not a "non-null span" heuristic, so the two stay distinguishable.
    """

    id: UUID = Field(default_factory=uuid4)
    paragraph_id: UUID
    entity_id: UUID
    span_start: int | None = None
    span_end: int | None = None
    confidence: float | None = None
    embedding: list[float] | None = None
    source: Literal["extraction", "manual"] = "extraction"


class MentionSuppression(BaseModel):
    """A negative highlight record (M4.S3c, spec §6.4 / DM-S3c-1 B): "this `[start, end)`
    is **not** a highlight", written by the reader's right-click corrections.

    `entity_id` NULL = "not an entity" (the reader clears every claimant at the span);
    set = "not this entity" (clears that one entity's claim). Same cross-store seam as
    `EntityMention`: `paragraph_id` is a real Postgres FK, `entity_id` carries none.
    """

    id: UUID = Field(default_factory=uuid4)
    paragraph_id: UUID
    entity_id: UUID | None = None
    span_start: int
    span_end: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
