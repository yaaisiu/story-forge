"""Story ingest routes (spec §7, step 1: upload → validate → detect → persist).

Thin HTTP layer: validate the upload, delegate parsing/detection to `domain/`,
sandbox the original via the storage adapter, and persist a `Project` (carrying
the detected language) plus a `Story` (carrying the raw text) through the repo.
Each upload creates its own project for now — project selection arrives with the
frontend, and a `Story` needs a `project_id` to exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from psycopg import AsyncConnection
from pydantic import BaseModel

from story_forge.adapters.db import get_connection
from story_forge.adapters.postgres_repo import (
    get_project,
    get_story,
    get_story_for_update,
    insert_chapter,
    insert_paragraph,
    insert_project,
    insert_scene,
    insert_story,
    list_chapters,
)
from story_forge.adapters.upload_storage import save_upload
from story_forge.agents.chunking_agent import ChunkingError
from story_forge.agents.chunking_coordinator import (
    ChunkingCoordinator,
    ChunkingTooLongError,
)
from story_forge.config import settings
from story_forge.domain.chunking import outline_to_tree
from story_forge.domain.language import detect_language
from story_forge.domain.models import Project, Story
from story_forge.domain.parsing import ParseError, parse_document

router = APIRouter(prefix="/stories", tags=["stories"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB — generous for 5k–50k-word stories.

# Per-extension allowlist of acceptable declared content types. A missing or
# generic type is tolerated (browsers are inconsistent, esp. for .md); a type
# that is positively wrong for the extension is rejected. Real content validation
# is the parser itself, which rejects bytes that don't match the format.
_GENERIC_TYPES = {"", "application/octet-stream"}
_ALLOWED_TYPES: dict[str, set[str]] = {
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/x-markdown", "text/plain"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
}


class StoryUploadResponse(BaseModel):
    """What the upload route returns once a story is persisted."""

    project_id: UUID
    story_id: UUID
    title: str
    language: str
    paragraph_count: int


@router.post("/upload", status_code=201)
async def upload_story(
    file: UploadFile,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
) -> StoryUploadResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail=f"unsupported file type: {suffix or 'none'!r}")
    # Strip any parameters (e.g. "text/plain; charset=utf-8") before matching.
    declared = (file.content_type or "").split(";")[0].strip().lower()
    if declared not in _GENERIC_TYPES and declared not in _ALLOWED_TYPES[suffix]:
        raise HTTPException(
            status_code=415, detail=f"content type {declared!r} does not match {suffix}"
        )

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file exceeds the maximum upload size")
    if not data:
        raise HTTPException(status_code=400, detail="uploaded file is empty")

    try:
        parsed = parse_document(data, suffix)
        language = detect_language(parsed.raw_text)
    except (ParseError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    title = Path(file.filename or "").stem or "untitled"
    project = Project(name=title, language=language)
    story = Story(project_id=project.id, title=title, raw_text=parsed.raw_text)

    # Sandbox the original before the DB write so a storage failure aborts the row.
    save_upload(settings.upload_dir, story.id, suffix, data)
    await insert_project(conn, project)
    await insert_story(conn, story)

    return StoryUploadResponse(
        project_id=project.id,
        story_id=story.id,
        title=title,
        language=language,
        paragraph_count=len(parsed.paragraphs),
    )


def get_chunking_coordinator(request: Request) -> ChunkingCoordinator:
    """The app-lifetime coordinator wired in `main.py` (provider + agent + knobs)."""
    coordinator: ChunkingCoordinator = request.app.state.chunking_coordinator
    return coordinator


ChunkingMode = Literal["auto", "manual", "hybrid"]


class StructureResponse(BaseModel):
    """What the structure route returns once the outline is persisted."""

    story_id: UUID
    mode: ChunkingMode
    chapter_count: int
    scene_count: int
    paragraph_count: int


@router.post("/{story_id}/structure", status_code=201)
async def structure_story(
    story_id: UUID,
    mode: ChunkingMode,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    coordinator: Annotated[ChunkingCoordinator, Depends(get_chunking_coordinator)],
) -> StructureResponse:
    """Build the document tree for a story (spec §7 step 2) and persist it.

    Reads the story's stored raw text — which already carries the author's
    `##` / `###` anchors for manual/hybrid — builds the outline in the chosen
    mode, and inserts chapters → scenes → paragraphs. One-shot: the accept/edit
    loop is the frontend's job (Session 6). Re-structuring is refused (409) rather
    than silently appending a second tree.

    Locking strategy: the outline is built *without* holding a DB write lock,
    because auto/hybrid awaits an LLM call that can take seconds. The story row
    is then `SELECT ... FOR UPDATE`-locked only for the small write window —
    re-check `list_chapters` under the lock, then insert. Two concurrent POSTs
    serialize on the lock: the second sees the persisted tree and 409s instead
    of duplicating.
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    project = await get_project(conn, story.project_id)
    language = project.language if project is not None else "en"

    try:
        outline = await coordinator.build_outline(
            raw_text=story.raw_text, language=language, mode=mode
        )
    except ChunkingTooLongError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ChunkingError as exc:
        # Unusable LLM output, give-up after retries, or no prompt for the language.
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Take the lock now — the writes are the short, hot path; the LLM call above
    # is done. Re-fetch under the lock so a vanished-meanwhile story is still
    # honestly 404'd, then re-check `list_chapters` for the 409 race.
    if await get_story_for_update(conn, story_id) is None:
        raise HTTPException(status_code=404, detail="story not found")
    if await list_chapters(conn, story_id):
        raise HTTPException(status_code=409, detail="story already has a structure")

    chapters, scenes, paragraphs = outline_to_tree(outline, story_id)
    for chapter in chapters:
        await insert_chapter(conn, chapter)
    for scene in scenes:
        await insert_scene(conn, scene)
    for paragraph in paragraphs:
        await insert_paragraph(conn, paragraph)

    return StructureResponse(
        story_id=story_id,
        mode=mode,
        chapter_count=len(chapters),
        scene_count=len(scenes),
        paragraph_count=len(paragraphs),
    )
