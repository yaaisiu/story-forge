"""Project listing routes (multi-story, DM-MS-4).

Read-only backend-for-frontend reads that let a project/story picker enumerate the author's
projects and a project's stories. Project *creation* stays implicit-on-upload (an explicit
`POST /projects` is deferred — no UX demand yet); these are the two list surfaces the picker needs.
Thin HTTP wrappers: the rollups live in the Postgres repo, the listing shapes in `domain/models`.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection

from story_forge.adapters.db import get_connection
from story_forge.adapters.postgres_repo import (
    get_project,
    list_projects,
    list_stories_for_project,
)
from story_forge.api.responses import ErrorResponse
from story_forge.domain.models import ProjectSummary, StorySummary

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
async def list_projects_route(
    conn: Annotated[AsyncConnection, Depends(get_connection)],
) -> list[ProjectSummary]:
    """Every project with its story count, newest first (the picker's project list)."""
    return await list_projects(conn)


@router.get(
    "/{project_id}/stories",
    responses={404: {"model": ErrorResponse, "description": "Project not found."}},
)
async def list_project_stories_route(
    project_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
) -> list[StorySummary]:
    """A project's stories, newest first. 404s an unknown project (fail-closed) so the picker
    distinguishes "no such project" from "a project with no stories yet"."""
    if await get_project(conn, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return await list_stories_for_project(conn, project_id)
