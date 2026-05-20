"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from story_forge.config import settings

app = FastAPI(
    title="Story Forge",
    version="0.0.0",
    description="Agent-orchestrated narrative analysis with a Neo4j knowledge graph.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe used by the frontend smoke check and by CI."""
    return {"status": "ok"}
