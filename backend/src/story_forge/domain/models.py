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
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(UTC)


class Project(BaseModel):
    """Top-level container for one author's body of work."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    language: str  # "pl" | "en" — the project's primary language
    world_id: UUID | None = None  # optional shared-graph parent (worlds table is later)
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
