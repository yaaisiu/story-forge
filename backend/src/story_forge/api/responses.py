"""Shared HTTP response shapes used across API routers.

`ErrorResponse` is the one error body every route declares in its ``responses=`` map — the shape
FastAPI's ``HTTPException`` produces. Declaring it (rather than letting FastAPI emit only the
success status + the auto-added 422) lets the generated TypeScript client
(`frontend/src/lib/api/schema.d.ts`) model the expected failure outcomes (404 / 409 / 502 / …).
There must be exactly one such model shared by all routers (see `src/story_forge/AGENTS.md`).
"""

from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str
