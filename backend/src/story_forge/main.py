"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from story_forge.adapters.llm.ollama import OllamaProvider
from story_forge.agents.chunking_agent import ChunkingAgent
from story_forge.agents.chunking_coordinator import ChunkingCoordinator
from story_forge.api import stories
from story_forge.config import settings

app = FastAPI(
    title="Story Forge",
    version="0.0.0",
    description="Agent-orchestrated narrative analysis with a Neo4j knowledge graph.",
)

# Chunking dependency wiring (spec §6.5). One provider instance for the app: on a
# GPU-less host the default tier is cloud_free, so it points at Ollama Cloud. The
# tier label the agent records is cosmetic until the router lands; the local_small
# path is enabled by config (a GPU host) without touching this code.
_chunking_provider = OllamaProvider(
    host=settings.ollama_cloud_host,
    model=settings.chunking_model,
    api_key=settings.ollama_cloud_api_key or None,
)
app.state.chunking_coordinator = ChunkingCoordinator(
    ChunkingAgent(_chunking_provider, local_max_words=settings.chunking_local_max_words)
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(stories.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe used by the frontend smoke check and by CI."""
    return {"status": "ok"}
