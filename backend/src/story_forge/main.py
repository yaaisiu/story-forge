"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from neo4j import AsyncGraphDatabase

from story_forge.adapters.llm.base import LLMProvider, ModelTier
from story_forge.adapters.llm.ollama import OllamaProvider
from story_forge.adapters.llm.postgres_cost_store import PostgresCostStore
from story_forge.adapters.llm.router import LLMRouter
from story_forge.adapters.neo4j_repo import Neo4jRepo
from story_forge.adapters.postgres_mention_store import PostgresMentionStore
from story_forge.agents.chunking_agent import ChunkingAgent
from story_forge.agents.chunking_coordinator import ChunkingCoordinator
from story_forge.agents.extraction_agent import ExtractionAgent
from story_forge.agents.extraction_coordinator import ExtractionCoordinator
from story_forge.api import llm, stories
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

# The §6.6 cost ledger. App-lifetime singleton: it opens its own short-lived
# connection per write so a usage row survives even if the request that triggered
# the call rolls back. The status endpoint reads this store; the router records into it.
app.state.cost_store = PostgresCostStore()

# Extraction + graph-write wiring (M2.S4, spec §7 step 4 / §9 M2). The router is
# wired with its first real consumer here: extraction is "medium" weight → cloud_free
# (§6.5), so only that tier is populated (Ollama Cloud, like chunking). cloud_strong
# is added when a heavy task first needs it — an unconfigured tier raises rather than
# silently misrouting. The Neo4j driver is created synchronously (it connects lazily
# on first query); the mention store opens its own connection per write so committed
# checkpoints make the batch resumable (OQ-2).
_extraction_provider = OllamaProvider(
    host=settings.ollama_cloud_host,
    model=settings.extraction_model,
    api_key=settings.ollama_cloud_api_key or None,
)
_extraction_providers: dict[ModelTier, list[LLMProvider]] = {"cloud_free": [_extraction_provider]}
_extraction_router = LLMRouter(
    providers=_extraction_providers,
    cost_store=app.state.cost_store,
    daily_budget_usd=settings.daily_budget_usd,
)
_neo4j_repo = Neo4jRepo(
    AsyncGraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
)
app.state.extraction_coordinator = ExtractionCoordinator(
    ExtractionAgent(_extraction_router),
    _neo4j_repo,
    PostgresMentionStore(),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(stories.router)
app.include_router(llm.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe used by the frontend smoke check and by CI."""
    return {"status": "ok"}
