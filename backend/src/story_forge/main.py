"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from neo4j import AsyncGraphDatabase

from story_forge.adapters.accepted_entity_reader import AcceptedEntityReader
from story_forge.adapters.label_vocabulary_reader import LabelVocabularyReader
from story_forge.adapters.llm.base import LLMProvider, ModelTier
from story_forge.adapters.llm.ollama import OllamaProvider
from story_forge.adapters.llm.postgres_cost_store import PostgresCostStore
from story_forge.adapters.llm.router import LLMRouter
from story_forge.adapters.neo4j_repo import Neo4jRepo
from story_forge.adapters.postgres_candidate_store import PostgresCandidateStore
from story_forge.adapters.postgres_duplicate_dismissal_store import (
    PostgresDuplicateDismissalStore,
)
from story_forge.adapters.postgres_edit_store import PostgresEditStore
from story_forge.adapters.postgres_label_dismissal_store import PostgresLabelDismissalStore
from story_forge.adapters.postgres_mention_store import PostgresMentionStore
from story_forge.adapters.postgres_relation_store import PostgresRelationStore
from story_forge.agents.candidate_rematch import ReMatchService
from story_forge.agents.candidate_review import CandidateReviewService
from story_forge.agents.candidate_staging import CandidateStager
from story_forge.agents.chunking_agent import ChunkingAgent
from story_forge.agents.chunking_coordinator import ChunkingCoordinator
from story_forge.agents.embedding_agent import EmbeddingAgent
from story_forge.agents.entity_edit import EntityEditService
from story_forge.agents.extraction_agent import ExtractionAgent
from story_forge.agents.extraction_coordinator import ExtractionCoordinator
from story_forge.agents.judge_agent import JudgeAgent
from story_forge.agents.matching_agent import MatchingAgent
from story_forge.agents.relation_review import RelationReviewService
from story_forge.api import llm, projects, stories
from story_forge.config import settings


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Close the Neo4j driver on shutdown.

    The driver is created eagerly at import (it connects lazily on first query) and lived for
    the whole process with no close, leaking its connection pool on reload/shutdown. The cascade
    now reads Neo4j per ingest run, so a clean close matters; Postgres stores open their own
    short-lived connections per call and need no teardown here.
    """
    yield
    await _neo4j_repo.close()


app = FastAPI(
    title="Story Forge",
    version="0.0.0",
    description="Agent-orchestrated narrative analysis with a Neo4j knowledge graph.",
    lifespan=_lifespan,
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

# Extraction + cascade wiring (M3.S4a, spec §7 steps 4–7 / §9 M3). The router is shared by
# extraction *and* the Stage-3 judge — both "medium" weight → cloud_free (§6.5), the only
# populated tier (Ollama Cloud, like chunking); cloud_strong is added when a heavy task first
# needs it (an unconfigured tier raises rather than misrouting). Under intercept-before-write
# the coordinator no longer writes the graph: it stages candidates with the cascade's proposal
# (Embedding → Matching → Judge) into Postgres; Neo4j is written only by the human-accept path
# (the `CandidateReviewService`), which is INV-1's enforcer. The Neo4j driver connects lazily
# and is closed on the FastAPI lifespan; the candidate store opens its own connection per
# paragraph so committed staging makes the batch resumable (OQ-2).
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
_candidate_store = PostgresCandidateStore()
# Shared across the read path (the §3.4 graph viewer) and the accept path (the review service).
app.state.neo4j_repo = _neo4j_repo
app.state.candidate_store = _candidate_store
# Duplicate-suggestion surface (graph-quality S4a): a read-only accepted-graph snapshot reader
# for the self-join, and the staging-side dismissed-pair store (INV-9 holds — never a graph write).
app.state.accepted_reader = AcceptedEntityReader(_neo4j_repo)
app.state.duplicate_dismissal_store = PostgresDuplicateDismissalStore()
# Name-normalisation surface (graph-quality S6a): a reader that assembles the two label
# vocabularies (predicate names + entity-type labels, with counts + label-string embeddings) for
# the synonym self-join, and the staging-side dismissed-label-pair store (INV-9 holds — never a
# graph write). The concrete `EmbeddingAgent` meets the reader here at the composition root; the
# reader itself types against the `LabelEncoder` Protocol.
app.state.label_vocabulary_reader = LabelVocabularyReader(_neo4j_repo, EmbeddingAgent())
app.state.label_dismissal_store = PostgresLabelDismissalStore()
app.state.extraction_coordinator = ExtractionCoordinator(
    ExtractionAgent(_extraction_router),
    CandidateStager(EmbeddingAgent(), MatchingAgent(), JudgeAgent(_extraction_router)),
    _candidate_store,
    AcceptedEntityReader(_neo4j_repo),
)
# On-accept intra-batch dedup (M3.S4c): re-match reuses the deterministic matcher over the
# still-pending candidates after each accept. Stateless (thresholds from config), staging-only.
_rematch = ReMatchService(MatchingAgent(), _candidate_store)
app.state.candidate_review = CandidateReviewService(
    _neo4j_repo, _candidate_store, PostgresMentionStore(), rematch=_rematch
)
# Relation-write (M3.S4e): the human-gated edge writer (§3.3's 5th action). Resolves a staged
# relation's surface endpoints to committed entity ids (via the candidate store) and writes the
# edge idempotently to Neo4j — the only edge-writing path (INV-1/INV-9), the sibling of the
# candidate-accept node writer. The same store backs the edge-evidence read (graph-quality S3):
# `written` rows survive commit and carry each edge's source paragraph(s) + quote(s), so it is
# also exposed on `app.state` for the read-only evidence endpoint.
_relation_store = PostgresRelationStore()
app.state.relation_store = _relation_store
app.state.relation_review = RelationReviewService(_neo4j_repo, _relation_store, _candidate_store)
# Manual correction (M4.S3a/S3b): the human edit-handler for committed graph state — edits an
# accepted entity's fields, adds/removes relations, and merges entity B into survivor A (re-pointing
# its edges + mentions), recording a before→after / grouped edit-evidence trail (INV-3, DM-S3a-2 /
# DM-S3b-1). A third human-reached graph writer (the INV-9 rewording, ADR 0006); not an automated
# stage. The mention store re-points B's `entity_mentions` onto A on merge.
app.state.entity_edit = EntityEditService(_neo4j_repo, PostgresEditStore(), PostgresMentionStore())

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(stories.router)
app.include_router(projects.router)
app.include_router(llm.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe used by the frontend smoke check and by CI."""
    return {"status": "ok"}
