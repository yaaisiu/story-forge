"""Story ingest routes (spec §7, step 1: upload → validate → detect → persist).

Thin HTTP layer: validate the upload, delegate parsing/detection to `domain/`,
sandbox the original via the storage adapter, and persist a `Project` (carrying
the detected language) plus a `Story` (carrying the raw text) through the repo.
Each upload creates its own project for now — project selection arrives with the
frontend, and a `Story` needs a `project_id` to exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from psycopg import AsyncConnection
from pydantic import BaseModel

from story_forge.adapters.db import get_connection
from story_forge.adapters.postgres_repo import insert_project, insert_story
from story_forge.adapters.upload_storage import save_upload
from story_forge.config import settings
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
    declared = (file.content_type or "").lower()
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
