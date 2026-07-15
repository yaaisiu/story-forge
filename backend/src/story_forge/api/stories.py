"""Story ingest routes (spec §7, step 1: upload → validate → detect → persist).

Thin HTTP layer: validate the upload, delegate parsing/detection to `domain/`,
sandbox the original via the storage adapter, and persist a `Project` (carrying
the detected language) plus a `Story` (carrying the raw text) through the repo.
Each upload creates its own project for now — project selection arrives with the
frontend, and a `Story` needs a `project_id` to exist.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from neo4j.exceptions import ServiceUnavailable
from psycopg import AsyncConnection, OperationalError
from pydantic import BaseModel, field_validator, model_validator

from story_forge.adapters.accepted_entity_reader import AcceptedEntityReader
from story_forge.adapters.db import get_connection
from story_forge.adapters.label_vocabulary_reader import LabelVocabularyReader
from story_forge.adapters.llm.base import ProviderResponseError
from story_forge.adapters.neo4j_repo import Neo4jRepo
from story_forge.adapters.postgres_candidate_store import PostgresCandidateStore
from story_forge.adapters.postgres_duplicate_dismissal_store import (
    PostgresDuplicateDismissalStore,
)
from story_forge.adapters.postgres_label_dismissal_store import PostgresLabelDismissalStore
from story_forge.adapters.postgres_relation_store import PostgresRelationStore
from story_forge.adapters.postgres_repo import (
    get_project,
    get_story,
    get_story_for_update,
    get_story_paragraph,
    insert_chapter,
    insert_paragraph,
    insert_project,
    insert_scene,
    insert_story,
    list_chapters,
    list_entity_ids_for_story,
    list_entity_mentions_for_story,
    list_mention_suppressions_for_story,
    list_paragraph_ids_for_story,
    list_paragraph_texts_by_ids,
    list_recent_mention_texts_for_entities,
    list_story_paragraphs,
    update_story_raw_text,
)
from story_forge.adapters.upload_storage import save_upload
from story_forge.agents.candidate_review import (
    CandidateNotFound,
    CandidateReviewService,
    StaleMergeTarget,
)
from story_forge.agents.candidate_staging import canonical_for_language
from story_forge.agents.chunking_agent import ChunkingError
from story_forge.agents.chunking_coordinator import (
    ChunkingCoordinator,
    ChunkingTooLongError,
)
from story_forge.agents.entity_edit import (
    EntityEditService,
    EntityNotFound,
    MentionNotFound,
    NothingToUndo,
    RelationEdgeNotFound,
    SelfMergeError,
    UndoConflict,
)
from story_forge.agents.extraction_agent import ExtractionError
from story_forge.agents.extraction_coordinator import ExtractionCoordinator
from story_forge.agents.matching_agent import ExistingEntity, search_entities
from story_forge.agents.relation_review import (
    RelationEndpointsUnresolved,
    RelationNotFound,
    RelationReviewService,
)
from story_forge.api.responses import ErrorResponse
from story_forge.config import settings
from story_forge.domain.candidates import (
    AcceptedSnapshot,
    CandidateProposal,
    RelationStatus,
    StagedCandidate,
)
from story_forge.domain.chunking import outline_to_tree
from story_forge.domain.duplicate_clusters import (
    dismissal_pair_id,
    suggest_duplicate_pairs,
)
from story_forge.domain.edge_evidence import EdgeEvidence, build_edge_evidence
from story_forge.domain.entity_edits import EntityEditInvalid, EntityEditPatch
from story_forge.domain.entity_merge import EntityMergeInvalid
from story_forge.domain.graph import GraphEntity
from story_forge.domain.highlights import (
    HighlightTarget,
    ManualSpan,
    SpanInvalid,
    Suppression,
    reconcile_highlights,
    validate_manual_span,
)
from story_forge.domain.label_synonyms import (
    LabelSynonymSuggestion,
    label_dismissal_id,
    suggest_label_synonyms,
)
from story_forge.domain.language import detect_language
from story_forge.domain.models import Paragraph, Project, Story
from story_forge.domain.neighbourhood import EgoGraph, build_ego_graph
from story_forge.domain.parsing import ParseError, parse_document
from story_forge.domain.story_scope import filter_graph_to_story

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
    """What the upload route returns once a story is persisted.

    ``raw_text`` is echoed back so the frontend's manual-mode editor (spec §7
    step 2) has the parsed source to edit. The browser doesn't reliably parse
    .docx itself, so the upload response is the cheapest place to surface it;
    avoids a follow-up GET /stories/{id} round-trip that doesn't exist yet.
    """

    project_id: UUID
    story_id: UUID
    title: str
    language: str
    paragraph_count: int
    raw_text: str


@router.post(
    "/upload",
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Uploaded file is empty or unparseable."},
        404: {"model": ErrorResponse, "description": "Target project_id does not exist."},
        413: {"model": ErrorResponse, "description": "File exceeds the maximum upload size."},
        415: {
            "model": ErrorResponse,
            "description": "Unsupported file extension or content type mismatch.",
        },
    },
)
async def upload_story(
    file: UploadFile,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    project_id: UUID | None = None,
) -> StoryUploadResponse:
    """Ingest an uploaded document as a new story (spec §7 step 1, multi-story DM-MS-3).

    Accepts `.txt`/`.md`/`.docx` (the `_ALLOWED_TYPES` allowlist), validating the declared
    `content_type` against the extension — a positively-wrong type is rejected (415), but a
    generic/absent one passes to the parser, which is the real content check. Oversized files
    (over `MAX_UPLOAD_BYTES`) 413, empty or unparseable bytes 400. `parse_document` extracts the
    text and `detect_language` tags it.

    `project_id` selects between two modes: omitted ⇒ mint a fresh project named after the file,
    carrying the detected language; given ⇒ add the story to that existing project, failing closed
    with 404 if it doesn't exist so a story is never created under a ghost project. The original
    bytes are sandboxed to disk *before* the DB write, so a storage failure aborts the row rather
    than leaving a story with no backing file. Echoes `raw_text` back for the manual-mode editor.
    """
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
    # No project_id ⇒ mint a fresh project (today's behaviour). A project_id ⇒ add the story to
    # that existing project (multi-story, DM-MS-3); fail-closed with 404 if it doesn't exist, so a
    # story is never created under a ghost project (referential integrity at the boundary).
    if project_id is None:
        project = Project(name=title, language=language)
    else:
        existing = await get_project(conn, project_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="project not found")
        project = existing
    story = Story(project_id=project.id, title=title, raw_text=parsed.raw_text)

    # Sandbox the original before the DB write so a storage failure aborts the row.
    save_upload(settings.upload_dir, story.id, suffix, data)
    if project_id is None:
        await insert_project(conn, project)
    await insert_story(conn, story)

    return StoryUploadResponse(
        project_id=project.id,
        story_id=story.id,
        title=title,
        language=project.language,
        paragraph_count=len(parsed.paragraphs),
        raw_text=parsed.raw_text,
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


class StructureRequestBody(BaseModel):
    """Optional body for ``POST /stories/{id}/structure``.

    When ``raw_text`` is provided, the route parses the outline from this payload
    instead of the story's stored copy AND persists it back to ``stories.raw_text``
    in the same transaction. This is how the frontend manual-mode editor
    (spec §7 step 2 "user accepts/edits") commits its source-marker edits without
    a separate PATCH route. When ``raw_text`` is omitted or null, the route reads
    the stored copy and does not modify it — backwards-compatible.
    """

    raw_text: str | None = None


@router.post(
    "/{story_id}/structure",
    status_code=201,
    responses={
        404: {"model": ErrorResponse, "description": "Story not found."},
        409: {
            "model": ErrorResponse,
            "description": "Story already has a structure (re-structure is refused).",
        },
        502: {
            "model": ErrorResponse,
            "description": (
                "Chunking agent failed — LLM unreachable or unusable output after retries."
            ),
        },
    },
)
async def structure_story(
    story_id: UUID,
    mode: ChunkingMode,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    coordinator: Annotated[ChunkingCoordinator, Depends(get_chunking_coordinator)],
    body: StructureRequestBody | None = None,
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

    # If the caller supplied a raw_text override, parse the outline from it; the
    # original story.raw_text is overwritten further down (post-lock, so the
    # write window stays small). Without an override, current behavior.
    override = body.raw_text if body is not None else None
    raw_text = override if override is not None else story.raw_text

    try:
        outline = await coordinator.build_outline(raw_text=raw_text, language=language, mode=mode)
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

    # Persist the source-marker edits in the same transaction as the tree, so a
    # later read sees the edited raw_text alongside the chapters/scenes it parsed.
    if override is not None:
        await update_story_raw_text(conn, story_id, override)

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


def get_extraction_coordinator(request: Request) -> ExtractionCoordinator:
    """The app-lifetime coordinator wired in `main.py` (router-backed agent + stores)."""
    coordinator: ExtractionCoordinator = request.app.state.extraction_coordinator
    return coordinator


class ExtractResponse(BaseModel):
    """Progress of an extraction run over a story's paragraphs (spec §9 M3).

    Under intercept-before-write extraction *stages* candidates (it does not write the graph),
    so the count is `candidates_staged`, not entities/relations written. `paused` is the
    completion signal — true when the run stopped at the budget/quota pause-and-ask (HTTP 202,
    partial progress), false when it finished (HTTP 200). `paragraphs_done` counts paragraphs
    already staged (the resume checkpoint), so a re-POST resumes from the first not-done one.
    """

    story_id: UUID
    paragraphs_total: int
    paragraphs_done: int
    candidates_staged: int
    paused: bool
    pause_reason: str | None


@router.post(
    "/{story_id}/extract",
    status_code=200,
    responses={
        202: {
            "model": ExtractResponse,
            "description": "Budget/quota pause hit mid-batch; partial progress, re-POST to resume.",
        },
        404: {"model": ErrorResponse, "description": "Story not found."},
        502: {
            "model": ErrorResponse,
            "description": "Extraction failed — LLM unreachable or unusable output after retries.",
        },
        503: {
            "model": ErrorResponse,
            "description": "A data store (Postgres/Neo4j) is unavailable.",
        },
    },
)
async def extract_story(
    story_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    coordinator: Annotated[ExtractionCoordinator, Depends(get_extraction_coordinator)],
    response: Response,
) -> ExtractResponse:
    """Extract + stage a story's candidates through the §3.3 cascade (spec §9 M3).

    Walks every persisted paragraph, runs the ExtractionAgent, then the cascade, and *stages*
    each candidate with its proposal (NEW vs MERGE) — writing **nothing** to the graph
    (intercept-before-write, INV-9). The graph is written only when a human accepts at the
    review queue (`POST …/candidates/{id}/accept`, INV-1). The batch is resumable: if the
    router pauses on budget/quota, the run stops with `paused=true` (HTTP 202) and a re-POST
    continues from the first un-staged paragraph. Budget/quota are therefore *not* HTTP errors
    here by design (OQ-2); a hard agent failure maps to 502, a store outage to 503.
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    project = await get_project(conn, story.project_id)
    language = project.language if project is not None else "en"
    paragraphs = await list_story_paragraphs(conn, story_id)

    try:
        result = await coordinator.ingest_story(
            paragraphs=paragraphs,
            project_id=story.project_id,
            story_id=story_id,
            language=language,
        )
    except (OperationalError, ServiceUnavailable) as exc:
        # A store-connectivity blip mid-cascade (Postgres staging read/write or the Neo4j
        # accepted-graph read) must fail-closed as 503 — never degrade to a silent NEW.
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc
    except (ExtractionError, ProviderResponseError, httpx.HTTPError) as exc:
        # The LLM path is unusable: agent give-up after retries / no prompt for the
        # language (ExtractionError); a malformed-200 envelope that exhausted failover
        # (ProviderResponseError); or the router re-raising its terminal transport
        # error after failover (httpx.HTTPError — a provider outage, 5xx, or bad/missing
        # Ollama Cloud credentials surfacing as 401). All map to the documented 502.
        # (Budget/quota are caught by the coordinator → 202-paused, never reach here.)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if result.paused:
        response.status_code = 202
    return ExtractResponse(
        story_id=story_id,
        paragraphs_total=result.paragraphs_total,
        paragraphs_done=result.paragraphs_done,
        candidates_staged=result.candidates_staged,
        paused=result.paused,
        pause_reason=result.pause_reason,
    )


def get_neo4j_repo(request: Request) -> Neo4jRepo:
    """The app-lifetime Neo4j repo wired in `main.py` (shared across requests)."""
    repo: Neo4jRepo = request.app.state.neo4j_repo
    return repo


class GraphNode(BaseModel):
    """One entity node for the §3.4 viewer — the display subset of `GraphEntity`.

    Persistence-only fields (`properties`, `embedding`, `project_id`)
    are omitted: the read-only M2 viewer colours by `type`, labels by canonical
    name/aliases, and links each node to its first occurrence paragraph.
    """

    id: UUID
    type: str
    canonical_name_pl: str | None
    canonical_name_en: str | None
    aliases: list[str]
    first_seen_paragraph_id: UUID | None


class GraphEdge(BaseModel):
    """One typed, directed relation for the viewer (edge label = `type`, §3.4)."""

    id: UUID
    type: str
    subject_id: UUID
    object_id: UUID
    confidence: float


class GraphResponse(BaseModel):
    """The story's knowledge graph as nodes + edges for the viewer."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


# A top-N cap on the manual-handpick search payload (M3.S4d). Not a §3.3 matching
# threshold (those live in config.py / DM1) — a presentation bound: one solo author over
# one project's entities never needs pagination, and ranking puts the best matches first.
ENTITY_SEARCH_LIMIT = 20


class EntitySearchResult(BaseModel):
    """One accepted entity matched by the handpick search — the picker's row (M3.S4d).

    Mirrors the review card's existing top-3 *alternative* shape (`entity_id` +
    `canonical_name` + `score`) so a picked search result feeds the same merge-accept path,
    plus `type` (to disambiguate same-named entities) and `aliases` (so the card can show
    *why* it matched). `canonical_name` is the project-language-resolved name the matcher
    ranks on, so the human's search reads the same name the machine matched.
    """

    entity_id: UUID
    canonical_name: str
    type: str
    score: float
    aliases: list[str]


class EntitySearchResponse(BaseModel):
    """The handpick search hits, ranked best-first (spec §3.3 *Manual handpick*)."""

    entities: list[EntitySearchResult]


@router.get(
    "/{story_id}/graph",
    responses={404: {"model": ErrorResponse, "description": "Story not found."}},
)
async def get_story_graph(
    story_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    repo: Annotated[Neo4jRepo, Depends(get_neo4j_repo)],
    scope: Literal["story", "project"] = "story",
) -> GraphResponse:
    """The story's entity graph for the read-only viewer + §3.4 scope toggle (multi-story, DM-MS-2).

    The graph is keyed by *project* (entities carry `project_id`, the §6.4 multi-tenancy seam) and
    shared across the project's stories. `scope=project` returns the whole project graph (every
    accepted entity + relation). `scope=story` (the default) narrows it to *this* story: the
    entities with an accepted mention rolling up to the story, and the relations among them asserted
    within it (DM-MS-1 derived membership; the filter is pure — `domain/story_scope`). For a
    single-story project the two scopes coincide, so the default is a no-op for existing projects.
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")

    entities = await repo.list_entities(story.project_id)
    relations = await repo.get_relations(story.project_id)
    if scope == "story":
        member_entity_ids = await list_entity_ids_for_story(conn, story_id)
        story_paragraph_ids = await list_paragraph_ids_for_story(conn, story_id)
        entities, relations = filter_graph_to_story(
            entities, relations, member_entity_ids, story_paragraph_ids
        )
    return GraphResponse(
        nodes=[
            GraphNode(
                id=e.id,
                type=e.type,
                canonical_name_pl=e.canonical_name_pl,
                canonical_name_en=e.canonical_name_en,
                aliases=e.aliases,
                first_seen_paragraph_id=e.first_seen_paragraph_id,
            )
            for e in entities
        ],
        edges=[
            GraphEdge(
                id=r.id,
                type=r.type,
                subject_id=r.subject_id,
                object_id=r.object_id,
                confidence=r.confidence,
            )
            for r in relations
        ],
    )


@router.get(
    "/{story_id}/entities",
    responses={404: {"model": ErrorResponse, "description": "Story not found."}},
)
async def search_entities_route(
    story_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    repo: Annotated[Neo4jRepo, Depends(get_neo4j_repo)],
    q: str = "",
) -> EntitySearchResponse:
    """Search the project's accepted entities for the Stage-4 *manual handpick* (spec §3.3).

    The reviewer can search **all** accepted entities in the project and pick any one as the
    merge target — the safety net for a true duplicate the deterministic cascade missed (a
    nickname embeddings don't catch, a name scoring just under threshold). Scope is the
    story's **project** (the §6.4 tenancy key); cross-project search is out of PoC scope.

    The query `q` is ranked **in Python** with the same RapidFuzz signal the matcher uses
    (`search_entities` over `canonical_name` + aliases) — so the human's search ≈ the
    machine's match — and so `q` **never reaches Cypher**: the only graph query
    (`list_entities`) is parameterised by `project_id` alone. Blank `q` → no results.
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    project = await get_project(conn, story.project_id)
    language = project.language if project is not None else "pl"

    entities = await repo.list_entities(story.project_id)
    by_id = {str(e.id): e for e in entities}
    existing = [
        ExistingEntity(
            id=str(e.id), canonical_name=canonical_for_language(e, language), aliases=e.aliases
        )
        for e in entities
    ]
    ranked = search_entities(q, existing, limit=ENTITY_SEARCH_LIMIT)
    return EntitySearchResponse(
        entities=[
            EntitySearchResult(
                entity_id=UUID(str(row["entity_id"])),
                canonical_name=str(row["canonical_name"]),
                type=by_id[str(row["entity_id"])].type,
                score=float(row["score"]),  # type: ignore[arg-type]
                aliases=by_id[str(row["entity_id"])].aliases,
            )
            for row in ranked
        ]
    )


# --- Reader (§3.5): story text with inline entity highlights ----------------


class ReaderHighlight(BaseModel):
    """One resolved highlight range `[start, end)` within a paragraph (spec §3.5).

    `source` + `mention_id` (M4.S3c, DM-S3c-6) give each highlight occurrence identity so a
    right-click correction can address it unambiguously: a `"search"` hit is derived (no row to
    edit — corrections write a suppression); a `"manual"` hit carries the `entity_mentions` id that
    a change-boundaries edits or a suppression hides."""

    start: int
    end: int
    entity_id: UUID
    type: str
    source: Literal["search", "manual"] = "search"
    mention_id: UUID | None = None


class ReaderParagraph(BaseModel):
    """A paragraph, in document order, with its resolved highlight ranges over `text`."""

    id: UUID
    text: str
    highlights: list[ReaderHighlight]


class ReaderEntity(BaseModel):
    """Tooltip data for an entity that appears in the reader (DM-IH-8: name + type + aliases)."""

    entity_id: UUID
    canonical_name: str
    type: str
    aliases: list[str]


class ReaderResponse(BaseModel):
    """The story's text with inline highlights + a catalog of the entities that appeared."""

    paragraphs: list[ReaderParagraph]
    entities: list[ReaderEntity]


def _entity_surface_forms(entity: GraphEntity) -> list[str]:
    """Every surface form to search for: both canonical names + all aliases, de-duped."""
    forms = [name for name in (entity.canonical_name_pl, entity.canonical_name_en) if name]
    forms.extend(entity.aliases)
    return list(dict.fromkeys(forms))


@router.get(
    "/{story_id}/reader",
    responses={404: {"model": ErrorResponse, "description": "Story not found."}},
)
async def get_story_reader(
    story_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    repo: Annotated[Neo4jRepo, Depends(get_neo4j_repo)],
) -> ReaderResponse:
    """The story text with accepted entities highlighted inline (spec §3.5, M4.S1).

    A read-only projection of the accepted graph onto the prose. Paragraphs + their mentions
    are *story*-scoped; the entity catalog is read *project*-scoped (the §6.4 tenancy key, the
    same seam as `/graph` and `/entities`) — correct while one story = one project, and the
    natural first home of the §3.4 per-story filter when multi-story lands. Each paragraph's
    highlights are **reconciled** (M4.S3c, DM-S3c-1 B) from three sources: render-time search over
    extraction mentions' surface forms, author-asserted **stored manual spans** (real offsets that
    overlay + win), minus **suppressions** (rejected highlights). An entity whose forms don't occur
    and was never manually tagged is omitted (fail-closed); only entities that actually appear are
    advertised in the tooltip catalog.
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    project = await get_project(conn, story.project_id)
    language = project.language if project is not None else "pl"

    paragraphs = await list_story_paragraphs(conn, story_id)
    mentions = await list_entity_mentions_for_story(conn, story_id)
    suppressions = await list_mention_suppressions_for_story(conn, story_id)
    entities = await repo.list_entities(story.project_id)

    type_by_entity = {e.id: e.type for e in entities}
    target_by_id = {
        e.id: HighlightTarget(entity_id=e.id, type=e.type, names=_entity_surface_forms(e))
        for e in entities
    }
    # Split mentions by source: extraction mentions feed render-time *search* (their offsets are
    # NULL — DM-IH-1); manual mentions are *stored spans* the resolver overlays verbatim (DM-S3c-1).
    searched_by_paragraph: dict[UUID, set[UUID]] = {}
    manual_by_paragraph: dict[UUID, list[ManualSpan]] = {}
    for mention in mentions:
        if (
            mention.source == "manual"
            and mention.span_start is not None
            and mention.span_end is not None
        ):
            if mention.entity_id not in type_by_entity:
                continue  # a manual tag whose entity was since deleted — skip (dangling, inert)
            manual_by_paragraph.setdefault(mention.paragraph_id, []).append(
                ManualSpan(
                    mention_id=mention.id,
                    entity_id=mention.entity_id,
                    type=type_by_entity[mention.entity_id],
                    span_start=mention.span_start,
                    span_end=mention.span_end,
                )
            )
        else:
            searched_by_paragraph.setdefault(mention.paragraph_id, set()).add(mention.entity_id)
    suppressions_by_paragraph: dict[UUID, list[Suppression]] = {}
    for supp in suppressions:
        suppressions_by_paragraph.setdefault(supp.paragraph_id, []).append(
            Suppression(
                span_start=supp.span_start, span_end=supp.span_end, entity_id=supp.entity_id
            )
        )

    reader_paragraphs: list[ReaderParagraph] = []
    appeared: set[UUID] = set()
    for paragraph in paragraphs:
        targets = [
            target_by_id[entity_id]
            for entity_id in searched_by_paragraph.get(paragraph.id, set())
            if entity_id in target_by_id
        ]
        resolved = reconcile_highlights(
            paragraph.content,
            targets,
            manual_by_paragraph.get(paragraph.id, []),
            suppressions_by_paragraph.get(paragraph.id, []),
        )
        appeared.update(h.entity_id for h in resolved)
        reader_paragraphs.append(
            ReaderParagraph(
                id=paragraph.id,
                text=paragraph.content,
                highlights=[
                    ReaderHighlight(
                        start=h.start,
                        end=h.end,
                        entity_id=h.entity_id,
                        type=h.type,
                        source=h.source,
                        mention_id=h.mention_id,
                    )
                    for h in resolved
                ],
            )
        )

    catalog = [
        ReaderEntity(
            entity_id=e.id,
            canonical_name=canonical_for_language(e, language),
            type=e.type,
            aliases=e.aliases,
        )
        for e in entities
        if e.id in appeared
    ]
    return ReaderResponse(paragraphs=reader_paragraphs, entities=catalog)


# --- Entity side panel (§3.4/§3.5): details + properties + local graph -------


class EntityDetailResponse(BaseModel):
    """One accepted entity's detail bundle for the reader side panel (spec §3.4/§3.5, M4.S2a).

    The two things the reader page doesn't already hold: the entity's free-form `properties`
    (surfaced by no other endpoint) and its 1-hop `ego_graph` (the "local graph around that
    entity", §3.5). Name/type/aliases are included so the panel is self-contained. Occurrences
    are derived frontend-side from the reader's already-rendered highlights (DM-SP-3), so they
    are not repeated here. Read-only — editing properties/relations is the next M4 slice.
    """

    entity_id: UUID
    canonical_name: str
    # The project's working language ("pl"/"en"). The editable side panel (M4.S3a-fe) shows a
    # single name field and writes it to the matching `canonical_name_{pl,en}` slot — one language
    # per project at PoC (two languages in one project is out of scope; spec §10 q8, owner).
    language: str
    type: str
    aliases: list[str]
    properties: dict[str, object]
    ego_graph: EgoGraph


@router.get(
    "/{story_id}/entities/{entity_id}",
    responses={404: {"model": ErrorResponse, "description": "Story or entity not found."}},
)
async def get_entity_detail(
    story_id: UUID,
    entity_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    repo: Annotated[Neo4jRepo, Depends(get_neo4j_repo)],
) -> EntityDetailResponse:
    """An accepted entity's details + properties + 1-hop local graph (spec §3.4/§3.5, M4.S2a).

    The read behind the reader side panel (DM-SP-1a — a focused per-entity endpoint): resolve the
    story → its project (the §6.4 tenancy key, the same seam as `/graph` and `/reader`), confirm
    the entity belongs to that project (else 404 — never leak another project's node), then return
    its display fields + `properties` + the `build_ego_graph` projection of its
    `get_neighbourhood` (DM-SP-2: strict 1-hop, entity-incident edges, self-loops dropped). A
    read-only projection — INV-1/INV-9 untouched, no LLM call.
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    entity = await repo.get_entity(entity_id)
    if entity is None or entity.project_id != story.project_id:
        raise HTTPException(status_code=404, detail="entity not found")

    project = await get_project(conn, story.project_id)
    language = project.language if project is not None else "pl"
    incident = await repo.get_neighbourhood(entity_id)
    return EntityDetailResponse(
        entity_id=entity.id,
        canonical_name=canonical_for_language(entity, language),
        language=language,
        type=entity.type,
        aliases=entity.aliases,
        properties=entity.properties,
        ego_graph=build_ego_graph(entity_id, incident),
    )


# --- Edit the side panel (§3.4/§3.5 manual correction): the first M4 write slice ---


def get_entity_edit(request: Request) -> EntityEditService:
    """The app-lifetime entity/relation edit handler wired in `main.py` (a human-reached graph
    writer alongside accept + decide — the INV-9 rewording, ADR 0006)."""
    service: EntityEditService = request.app.state.entity_edit
    return service


class EntityEditResponse(BaseModel):
    """The edited entity's display fields after a successful PATCH (M4.S3a). The side panel
    invalidates + refetches the full detail bundle (ego-graph, occurrences) via the GET endpoint
    (DM-S3a-4), so this slim shape carries only what the edit changed."""

    entity_id: UUID
    canonical_name: str
    type: str
    aliases: list[str]
    properties: dict[str, object]


class AddRelationRequest(BaseModel):
    """Add a relation between two accepted entities (DM-S3a-3). A self-loop (subject == object)
    is allowed — a manual one is intentional. To *edit* an existing edge's predicate or endpoints,
    use the atomic `PATCH …/relations/{edge_id}` (Graph-quality S5b-be) — not a client-side
    remove + add, which would drop the edge's `edge_uid` handle (ADR 0011)."""

    subject_id: UUID
    predicate: str
    object_id: UUID

    @field_validator("predicate")
    @classmethod
    def _predicate_non_empty(cls, value: str) -> str:
        # Reject a blank predicate at the request boundary (a clean 422, vs an uncaught
        # ValidationError from `GraphRelation` → 500), and **strip** it so the deterministic
        # `relation_edge_id` and the Neo4j relationship type don't fork on incidental whitespace
        # ("  LOVES  " vs "LOVES") — matching how `apply_entity_edit` strips an entity's `type`.
        stripped = value.strip()
        if not stripped:
            raise ValueError("predicate must be a non-empty string")
        return stripped


class RelationEditResponse(BaseModel):
    """Outcome of adding a relation: the edge id + whether the add folded onto an edge that
    already existed (the duplicate/re-predicate collision the UI warns on, DM-S3a-3)."""

    edge_id: UUID
    merged_into_existing: bool


class RetargetRelationRequest(BaseModel):
    """Edit-predicate and/or re-target a committed edge in one atomic op (Graph-quality S5b-be,
    DM-S5-2). Every field is optional — an omitted field keeps the edge's current value — but at
    least one must be supplied. The re-key preserves the §4 surrogate handle (DM-S5-3, INV-10)."""

    predicate: str | None = None
    subject_id: UUID | None = None
    object_id: UUID | None = None

    @field_validator("predicate")
    @classmethod
    def _predicate_non_empty(cls, value: str | None) -> str | None:
        # If a predicate is supplied, reject blank + strip incidental whitespace so the
        # deterministic `relation_edge_id` / Neo4j rel-type don't fork (as in `AddRelationRequest`).
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("predicate must be a non-empty string")
        return stripped

    @model_validator(mode="after")
    def _at_least_one_change(self) -> RetargetRelationRequest:
        # An empty body is a request-validation error (422 `HTTPValidationError`) — there is no
        # edge change to make. Not declared in `responses=` (the 422-trap): it is FastAPI's auto
        # validation shape, which a domain 422 would clobber.
        if self.predicate is None and self.subject_id is None and self.object_id is None:
            raise ValueError("supply at least one of predicate, subject_id, object_id")
        return self


@router.patch(
    "/{story_id}/entities/{entity_id}",
    responses={
        400: {"model": ErrorResponse, "description": "The edit is invalid (blank name or type)."},
        404: {"model": ErrorResponse, "description": "Story or entity not found."},
        503: {"model": ErrorResponse, "description": "A data store is unavailable."},
    },
)
async def edit_entity_route(
    story_id: UUID,
    entity_id: UUID,
    body: EntityEditPatch,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    edit: Annotated[EntityEditService, Depends(get_entity_edit)],
) -> EntityEditResponse:
    """Edit an accepted entity's name/aliases/type/`properties` (spec §3.4, DM-S3a-1).

    A human-reached graph write (INV-9 as reworded — ADR 0006): re-reads under the project's
    tenancy key, validates + merges the patch, writes the node, and records a before→after
    edit-evidence row (INV-3, DM-S3a-2). A blank name/type is rejected (400). `properties` stays
    open (INV-4). A corrected name/alias re-highlights in the reader for free (render-time search,
    DM-S3a-4); the panel invalidates + refetches the detail bundle.
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        updated = await edit.edit_entity(story.project_id, entity_id, body)
    except EntityNotFound as exc:
        raise HTTPException(status_code=404, detail="entity not found") from exc
    except EntityEditInvalid as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (OperationalError, ServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc

    project = await get_project(conn, story.project_id)
    language = project.language if project is not None else "pl"
    return EntityEditResponse(
        entity_id=updated.id,
        canonical_name=canonical_for_language(updated, language),
        type=updated.type,
        aliases=updated.aliases,
        properties=updated.properties,
    )


@router.post(
    "/{story_id}/relations",
    responses={
        404: {"model": ErrorResponse, "description": "Story or an endpoint entity not found."},
        503: {"model": ErrorResponse, "description": "A data store is unavailable."},
    },
)
async def add_relation_route(
    story_id: UUID,
    body: AddRelationRequest,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    edit: Annotated[EntityEditService, Depends(get_entity_edit)],
) -> RelationEditResponse:
    """Add a relation between two accepted entities (spec §3.4, DM-S3a-3, direct edge-writer).

    Both endpoints must already be accepted in this project (else 404). A duplicate add MERGEs
    onto the existing edge and is reported via `merged_into_existing` rather than erroring; a
    manual self-loop is allowed. Records a before→after edit-evidence row (INV-3, DM-S3a-2).
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        result = await edit.add_relation(
            story.project_id, body.subject_id, body.predicate, body.object_id
        )
    except EntityNotFound as exc:
        raise HTTPException(status_code=404, detail="an endpoint entity not found") from exc
    except (OperationalError, ServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc
    return RelationEditResponse(
        edge_id=result.edge_id, merged_into_existing=result.merged_into_existing
    )


@router.delete(
    "/{story_id}/relations/{edge_id}",
    status_code=204,
    responses={
        404: {"model": ErrorResponse, "description": "Story or relation edge not found."},
        503: {"model": ErrorResponse, "description": "A data store is unavailable."},
    },
)
async def remove_relation_route(
    story_id: UUID,
    edge_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    edit: Annotated[EntityEditService, Depends(get_entity_edit)],
) -> Response:
    """Remove a relation edge (spec §3.4, DM-S3a-3). 404s if the edge isn't in this project (a
    stale double-remove); records the before-image for undo (INV-3, DM-S3a-2)."""
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        await edit.remove_relation(story.project_id, edge_id)
    except RelationEdgeNotFound as exc:
        raise HTTPException(status_code=404, detail="relation not found") from exc
    except (OperationalError, ServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc
    return Response(status_code=204)


@router.patch(
    "/{story_id}/relations/{edge_id}",
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Story, the edge, or a new endpoint not found.",
        },
        503: {"model": ErrorResponse, "description": "A data store is unavailable."},
    },
)
async def retarget_relation_route(
    story_id: UUID,
    edge_id: UUID,
    body: RetargetRelationRequest,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    edit: Annotated[EntityEditService, Depends(get_entity_edit)],
) -> RelationEditResponse:
    """Edit-predicate and/or re-target a committed edge atomically (spec §3.4, Graph-quality
    S5b-be, DM-S5-2/3). The content-addressed edge id re-keys on any triple change, so this is a
    server-side delete-old + create-new recorded as one grouped reversible operation, **preserving
    the §4 surrogate handle** across the re-key (INV-10) — not the client-side remove+add, which
    would split the edit and drop the handle.

    404s a stale edge (`RelationEdgeNotFound`) or a re-target onto a missing endpoint
    (`EntityNotFound`). A re-key that collides with an edge already between the new pair **folds**
    (`merged_into_existing=True`); the returned `edge_id` is the **new** (post-re-key) id. A no-op
    (nothing changed) returns the unchanged id. An empty body is a 422 request-validation error.
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        result = await edit.retarget_relation(
            story.project_id,
            edge_id,
            predicate=body.predicate,
            subject_id=body.subject_id,
            object_id=body.object_id,
        )
    except RelationEdgeNotFound as exc:
        raise HTTPException(status_code=404, detail="relation not found") from exc
    except EntityNotFound as exc:
        raise HTTPException(status_code=404, detail="an endpoint entity not found") from exc
    except (OperationalError, ServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc
    return RelationEditResponse(
        edge_id=result.edge_id, merged_into_existing=result.merged_into_existing
    )


class MergeRequest(BaseModel):
    """Merge entity B (the path `entity_id`, absorbed) into survivor A (`target_entity_id`),
    M4.S3b (DM-S3b-2/8). `resolved_properties` carries the author's chosen value for every
    property key the two entities set differently — by-hand conflict resolution; a missing one is
    rejected (400). Non-conflicting keys union automatically, so they need not be listed."""

    target_entity_id: UUID
    resolved_properties: dict[str, object] = {}


class MergeSummaryResponse(BaseModel):
    """Outcome of a merge: the survivor's id + the counts the side panel reports — how many edges
    were re-pointed, how many MERGE-folded (multiplicity lost, surfaced not silent, DM-S3b-3), how
    many self-loops were dropped, and how many mentions moved onto the survivor."""

    survivor_entity_id: UUID
    repointed_count: int
    folded_count: int
    self_loops_dropped: int
    mentions_repointed: int


@router.post(
    "/{story_id}/entities/{entity_id}/merge",
    responses={
        400: {"model": ErrorResponse, "description": "A property conflict was left unresolved."},
        404: {
            "model": ErrorResponse,
            "description": "Story, the absorbed entity, or the merge target not found.",
        },
        409: {"model": ErrorResponse, "description": "Self-merge (absorbed == target)."},
        503: {"model": ErrorResponse, "description": "A data store is unavailable."},
    },
)
async def merge_entity_route(
    story_id: UUID,
    entity_id: UUID,
    body: MergeRequest,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    edit: Annotated[EntityEditService, Depends(get_entity_edit)],
) -> MergeSummaryResponse:
    """Merge entity B (`entity_id`, absorbed) into survivor A (`target_entity_id`) — spec §3.4,
    DM-S3b-1/2/3/4.

    A human-reached graph write (INV-9 as reworded — ADR 0006/0007): folds B's aliases/properties
    into A (author-resolved conflicts), re-points every edge and mention incident to B onto A, then
    deletes B — recording the whole fan-out as one **grouped, reversible** operation (INV-3,
    DM-S3b-1) so undo can reverse it. Both entities must be accepted in this project (else 404); a
    self-merge is rejected (409); an unresolved property conflict is rejected (400). The side panel
    invalidates + refetches the reader/graph/detail bundle (DM-S3a-4).
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        summary = await edit.merge_entities(
            story.project_id, entity_id, body.target_entity_id, body.resolved_properties
        )
    except SelfMergeError as exc:
        raise HTTPException(status_code=409, detail="cannot merge an entity into itself") from exc
    except EntityNotFound as exc:
        raise HTTPException(status_code=404, detail="entity not found") from exc
    except EntityMergeInvalid as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (OperationalError, ServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc
    return MergeSummaryResponse(
        survivor_entity_id=summary.survivor_entity_id,
        repointed_count=summary.repointed_count,
        folded_count=summary.folded_count,
        self_loops_dropped=summary.self_loops_dropped,
        mentions_repointed=summary.mentions_repointed,
    )


@router.delete(
    "/{story_id}/entities/{entity_id}",
    status_code=204,
    responses={
        404: {"model": ErrorResponse, "description": "Story or entity not found."},
        503: {"model": ErrorResponse, "description": "A data store is unavailable."},
    },
)
async def delete_entity_route(
    story_id: UUID,
    entity_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    edit: Annotated[EntityEditService, Depends(get_entity_edit)],
) -> Response:
    """Delete an accepted entity, its relations, and its text occurrences (spec §3.4, M4.S3b-be2,
    DM-S3b-5).

    A human-reached graph write (INV-9 as reworded — ADR 0006/0007): a real `DETACH DELETE` plus a
    full-snapshot before-image (node fields + incident edges + mentions) recorded as one grouped,
    **reversible** operation (INV-3) so undo can restore it. 404s if the entity isn't accepted in
    this project. The side panel invalidates + refetches the reader/graph bundle (DM-S3a-4).
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        await edit.delete_entity(story.project_id, entity_id)
    except EntityNotFound as exc:
        raise HTTPException(status_code=404, detail="entity not found") from exc
    except (OperationalError, ServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc
    return Response(status_code=204)


class UndoResponse(BaseModel):
    """What the undo affordance shows (DM-S3b-1, see-what-I-undo). On a real undo `applied` is True
    and `description` names what was reversed ("merged Broniek into Bronisław"); with `preview=true`
    `applied` is False and it reports what *would* be reversed without touching the graph."""

    description: str
    op_kind: str
    applied: bool


@router.post(
    "/{story_id}/graph-edits/undo",
    responses={
        404: {"model": ErrorResponse, "description": "Story not found, or nothing left to undo."},
        409: {"model": ErrorResponse, "description": "The graph drifted since; undo refused."},
        503: {"model": ErrorResponse, "description": "A data store is unavailable."},
    },
)
async def undo_last_route(
    story_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    edit: Annotated[EntityEditService, Depends(get_entity_edit)],
    preview: bool = False,
) -> UndoResponse:
    """Reverse the newest not-yet-undone graph operation in this story's project — the general undo
    executor (spec §10 q2 / §11 / §4.3, M4.S3b-be2, DM-S3b-1).

    Pops the top of the per-project undo stack and replays each change's inverse in reverse order
    (INV-3), then marks the operation `undone`. With `?preview=true` it returns *what would be
    reversed* without acting, so the UI can confirm first (DM-S3b-1, see-what-I-undo). 404 when the
    stack is empty; 409 when the graph drifted since the operation (a lost update in reverse —
    undoing would clobber a newer edit, so it refuses rather than overwrite).
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        result = await edit.undo_last(story.project_id, preview_only=preview)
    except NothingToUndo as exc:
        raise HTTPException(status_code=404, detail="nothing to undo") from exc
    except UndoConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OperationalError, ServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc
    return UndoResponse(
        description=result.description, op_kind=result.op_kind, applied=result.applied
    )


# --- Manual correction in the reader (spec §3.5, M4.S3c) ---------------------
#
# The reader's write surface: tag a span as an entity (existing or new), hide/re-assign a highlight
# ("not an entity"/"not this entity"), or change a highlight's boundaries. All are reversible via
# the story-scoped Undo (`/graph-edits/undo`). Spans are validated against the paragraph's text here
# (fail-closed → 400); the paragraph itself is story-scoped (tenancy → 404). 422 is left to Pydantic
# for request-shape errors (the §AGENTS.md 422 trap) — domain "bad span" is remapped to 400.


class NewEntityTag(BaseModel):
    """Create a brand-new accepted entity of type X from a tag (DM-S3c-2). `type` is open-world
    (INV-4) — a free string, never an enum."""

    name: str
    type: str


class TagRequest(BaseModel):
    """Tag a `[span_start, span_end)` occurrence as an entity (spec §3.5). Exactly one of
    `entity_id` (attach to an existing accepted entity) or `new_entity` (create one) — both or
    neither is a 422 request-shape error."""

    span_start: int
    span_end: int
    entity_id: UUID | None = None
    new_entity: NewEntityTag | None = None

    @model_validator(mode="after")
    def _exactly_one_target(self) -> TagRequest:
        if (self.entity_id is None) == (self.new_entity is None):
            raise ValueError("provide exactly one of entity_id or new_entity")
        return self


class TagResponse(BaseModel):
    """The created mention's id + the entity it points at (newly minted, for `new_entity`)."""

    mention_id: UUID
    entity_id: UUID


class SuppressRequest(BaseModel):
    """Hide or re-assign a highlighted occurrence (spec §3.5). `entity_id` None = "not an entity"
    (clear all claimants at the span); set = "not this entity" (clear that one). `retag_to` makes
    it an atomic re-assign — suppress the wrong entity + tag the right one as one op; it requires
    `entity_id` (the entity being corrected)."""

    span_start: int
    span_end: int
    entity_id: UUID | None = None
    retag_to: UUID | None = None

    @model_validator(mode="after")
    def _retag_needs_from(self) -> SuppressRequest:
        if self.retag_to is not None and self.entity_id is None:
            raise ValueError("retag_to requires entity_id (the entity being re-assigned from)")
        return self


class SuppressResponse(BaseModel):
    """The suppression id; `mention_id` is set only on an atomic re-assign (the re-tagged entity's
    new manual mention)."""

    suppression_id: UUID
    mention_id: UUID | None = None


class BoundaryRequest(BaseModel):
    """Change a highlight's boundaries (spec §3.5, DM-S3c-4). `mention_id` None = an auto search hit
    to **materialize** (needs `entity_id` + the old offsets to suppress the original position);
    set = an existing manual span to edit in place."""

    entity_id: UUID
    mention_id: UUID | None = None
    old_start: int
    old_end: int
    new_start: int
    new_end: int


class BoundaryResponse(BaseModel):
    """The new (materialized) or edited manual mention's id."""

    mention_id: UUID


async def _require_story_paragraph(
    conn: AsyncConnection, story_id: UUID, paragraph_id: UUID
) -> tuple[Story, Paragraph]:
    """Load the story + a paragraph proven to belong to it — the manual-correction tenancy guard.
    404s a missing story, or a paragraph from another story (`get_story_paragraph` scopes)."""
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    paragraph = await get_story_paragraph(conn, story_id, paragraph_id)
    if paragraph is None:
        raise HTTPException(status_code=404, detail="paragraph not found in this story")
    return story, paragraph


async def _project_language(conn: AsyncConnection, project_id: UUID) -> str:
    project = await get_project(conn, project_id)
    return project.language if project is not None else "pl"


@router.post(
    "/{story_id}/paragraphs/{paragraph_id}/tags",
    responses={
        400: {"model": ErrorResponse, "description": "The span or new-entity input is invalid."},
        404: {"model": ErrorResponse, "description": "Story, paragraph, or entity not found."},
        503: {"model": ErrorResponse, "description": "A data store is unavailable."},
    },
)
async def tag_occurrence_route(
    story_id: UUID,
    paragraph_id: UUID,
    body: TagRequest,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    edit: Annotated[EntityEditService, Depends(get_entity_edit)],
) -> TagResponse:
    """Tag a text span as an entity — existing (`entity_id`) or brand-new (`new_entity`); spec §3.5,
    DM-S3c-2. A human-reached write (INV-9 as reworded, ADR 0006): persists a stored manual mention
    with real offsets that overlays + wins over search, reversible via Undo. The span must be a
    valid range within the paragraph (else 400). The reader invalidates + refetches (DM-S3a-4)."""
    story, paragraph = await _require_story_paragraph(conn, story_id, paragraph_id)
    try:
        validate_manual_span(paragraph.content, body.span_start, body.span_end)
        if body.new_entity is not None:
            language = await _project_language(conn, story.project_id)
            entity_id, mention_id = await edit.tag_new_entity(
                story.project_id,
                paragraph_id,
                body.new_entity.name,
                body.new_entity.type,
                language,
                body.span_start,
                body.span_end,
            )
        else:
            assert body.entity_id is not None  # the validator guarantees exactly one target
            entity_id = body.entity_id
            mention_id = await edit.tag_existing(
                story.project_id, paragraph_id, entity_id, body.span_start, body.span_end
            )
    except SpanInvalid as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EntityEditInvalid as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EntityNotFound as exc:
        raise HTTPException(status_code=404, detail="entity not found") from exc
    except (OperationalError, ServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc
    return TagResponse(mention_id=mention_id, entity_id=entity_id)


@router.post(
    "/{story_id}/paragraphs/{paragraph_id}/suppressions",
    responses={
        400: {"model": ErrorResponse, "description": "The span is invalid."},
        404: {"model": ErrorResponse, "description": "Story, paragraph, or entity not found."},
        503: {"model": ErrorResponse, "description": "A data store is unavailable."},
    },
)
async def suppress_occurrence_route(
    story_id: UUID,
    paragraph_id: UUID,
    body: SuppressRequest,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    edit: Annotated[EntityEditService, Depends(get_entity_edit)],
) -> SuppressResponse:
    """Hide ("not an entity") or re-assign ("not this entity") a highlighted occurrence (spec §3.5,
    DM-S3c-3). Writes a suppression the reader subtracts; with `retag_to` it is an atomic re-assign
    (suppress + tag, one reversible op). Reversible via Undo; the reader invalidates + refetches."""
    story, paragraph = await _require_story_paragraph(conn, story_id, paragraph_id)
    try:
        validate_manual_span(paragraph.content, body.span_start, body.span_end)
        if body.retag_to is not None:
            assert body.entity_id is not None  # the validator guarantees this
            suppression_id, mention_id = await edit.retag_occurrence(
                story.project_id,
                paragraph_id,
                body.span_start,
                body.span_end,
                body.entity_id,
                body.retag_to,
            )
            return SuppressResponse(suppression_id=suppression_id, mention_id=mention_id)
        suppression_id = await edit.suppress_occurrence(
            story.project_id, paragraph_id, body.span_start, body.span_end, body.entity_id
        )
    except SpanInvalid as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EntityNotFound as exc:
        raise HTTPException(status_code=404, detail="entity not found") from exc
    except (OperationalError, ServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc
    return SuppressResponse(suppression_id=suppression_id, mention_id=None)


@router.post(
    "/{story_id}/paragraphs/{paragraph_id}/boundaries",
    responses={
        400: {"model": ErrorResponse, "description": "The new span is invalid."},
        404: {
            "model": ErrorResponse,
            "description": "Story, paragraph, entity, or mention absent.",
        },
        503: {"model": ErrorResponse, "description": "A data store is unavailable."},
    },
)
async def change_boundaries_route(
    story_id: UUID,
    paragraph_id: UUID,
    body: BoundaryRequest,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    edit: Annotated[EntityEditService, Depends(get_entity_edit)],
) -> BoundaryResponse:
    """Change a highlight's boundaries (spec §3.5, DM-S3c-4). On a manual span (`mention_id`) the
    offsets are edited in place; on an auto search hit (`mention_id` None) the occurrence is
    materialized at the new offsets and the original position suppressed, as one reversible op. The
    new span must be valid within the paragraph (else 400)."""
    story, paragraph = await _require_story_paragraph(conn, story_id, paragraph_id)
    try:
        validate_manual_span(paragraph.content, body.new_start, body.new_end)
        mention_id = await edit.change_boundaries(
            story.project_id,
            paragraph_id,
            body.entity_id,
            body.mention_id,
            body.old_start,
            body.old_end,
            body.new_start,
            body.new_end,
        )
    except SpanInvalid as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (EntityNotFound, MentionNotFound) as exc:
        raise HTTPException(status_code=404, detail="entity or mention not found") from exc
    except (OperationalError, ServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc
    return BoundaryResponse(mention_id=mention_id)


# --- Review queue (Stage 4): list pending / accept / reject -----------------


def get_candidate_store(request: Request) -> PostgresCandidateStore:
    """The app-lifetime candidate staging store wired in `main.py`."""
    store: PostgresCandidateStore = request.app.state.candidate_store
    return store


def get_candidate_review(request: Request) -> CandidateReviewService:
    """The app-lifetime accept/reject service wired in `main.py` (the only graph writer)."""
    service: CandidateReviewService = request.app.state.candidate_review
    return service


class AlternativeView(BaseModel):
    """One alternative merge target the reviewer can retarget to, enriched for verification (S3).

    The stored alternative carries only `entity_id` + `canonical_name` + `score` (a RapidFuzz name
    rank). S3 (DM-EE-3) adds the identity context that makes a merge *verifiable* — the target's
    `type`, its `aliases`, and a sample `context_quote` (one mention paragraph) — so two same-named
    entities can be told apart before merging. The enrichment fields are nullable: an alternative
    whose entity is absent from the graph read (or that has no surfaced mention) still renders.
    """

    entity_id: UUID
    canonical_name: str
    score: float
    type: str | None
    aliases: list[str]
    context_quote: str | None


class CandidateView(BaseModel):
    """One staged candidate for the §3.3 Stage-4 review queue (the render set S4b consumes).

    Carries the quote/context (±200 chars), the cascade's NEW-vs-MERGE proposal + the stage it
    reached, the judge's reasoning (if Stage 3 ran), and the top-3 alternative entities the
    reviewer can retarget to. `target_canonical_name` resolves the merge proposal's target name
    (S3/DM-EE-3, so a non-top-3 target no longer reads as "an existing entity"). Persistence-only
    fields (the vector, project/story ids) are omitted.
    """

    id: UUID
    paragraph_id: UUID
    candidate_name: str
    type: str
    context: str
    proposal: CandidateProposal
    target_entity_id: UUID | None
    target_canonical_name: str | None
    stage_reached: int
    confidence: float | None
    reasoning: str | None
    alternatives: list[AlternativeView]


class CandidatesResponse(BaseModel):
    """A story's pending review queue."""

    candidates: list[CandidateView]


def enrich_candidate_view(
    candidate: StagedCandidate,
    entities_by_id: Mapping[str, GraphEntity],
    quotes_by_id: Mapping[str, list[str]],
    *,
    language: str,
) -> CandidateView:
    """Project a staged candidate to its review-queue view, enriched with merge context (DM-EE-3).

    Pure (S3/DM-EE-3): the caller resolves the accepted-entity lookup (id → `GraphEntity`) and the
    sample-quote lookup (id → mention texts) once, batched; this maps them onto the view. Resolves
    `target_canonical_name` from the merge target, and each alternative's `type`/`aliases`/sample
    `context_quote`. An id absent from a lookup falls back to `None`/`[]` — never a raised error.
    """
    target_name: str | None = None
    if candidate.target_entity_id is not None:
        target = entities_by_id.get(str(candidate.target_entity_id))
        if target is not None:
            target_name = canonical_for_language(target, language) or None
    alternatives: list[AlternativeView] = []
    for alt in candidate.alternatives:
        if "entity_id" not in alt:
            continue  # an alternative carries an entity_id by construction; skip a malformed one
        entity_id = str(alt["entity_id"])
        entity = entities_by_id.get(entity_id)
        quotes = quotes_by_id.get(entity_id) or []
        alternatives.append(
            AlternativeView(
                entity_id=UUID(entity_id),
                canonical_name=str(alt.get("canonical_name", "")),
                score=float(alt.get("score", 0.0)),  # type: ignore[arg-type]
                type=entity.type if entity is not None else None,
                aliases=list(entity.aliases) if entity is not None else [],
                context_quote=quotes[0] if quotes else None,
            )
        )
    return CandidateView(
        id=candidate.id,
        paragraph_id=candidate.paragraph_id,
        candidate_name=candidate.candidate_name,
        type=candidate.type,
        context=candidate.context,
        proposal=candidate.proposal,
        target_entity_id=candidate.target_entity_id,
        target_canonical_name=target_name,
        stage_reached=candidate.stage_reached,
        confidence=candidate.confidence,
        reasoning=candidate.reasoning,
        alternatives=alternatives,
    )


@router.get(
    "/{story_id}/candidates",
    responses={
        404: {"model": ErrorResponse, "description": "Story not found."},
        503: {"model": ErrorResponse, "description": "The staging store is unavailable."},
    },
)
async def list_candidates(
    story_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    store: Annotated[PostgresCandidateStore, Depends(get_candidate_store)],
    repo: Annotated[Neo4jRepo, Depends(get_neo4j_repo)],
) -> CandidatesResponse:
    """The pending review queue for a story (spec §3.3 Stage 4) — candidates awaiting a human.

    Each candidate's view carries the merge-verification context S3 (DM-EE-3) adds: the target's
    resolved name and each alternative's type/aliases/sample quote. The accepted-entity read and
    the sample-quote read are batched once for the whole queue (not per candidate) to avoid an N+1.
    The queue's core data is Postgres, so a Postgres outage is a declared 503; the enrichment is
    **best-effort** verification context, so a graph-DB outage (or a transient enrichment-read
    failure) degrades to an *unenriched* queue rather than blocking the human's review.
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        project = await get_project(conn, story.project_id)
        pending = await store.list_pending(story_id)
    except OperationalError as exc:
        raise HTTPException(status_code=503, detail="the staging store is unavailable") from exc
    language = project.language if project is not None else "en"
    if not pending:
        return CandidatesResponse(candidates=[])
    entities_by_id: dict[str, GraphEntity] = {}
    quotes_by_id: dict[str, list[str]] = {}
    try:
        entities_by_id = {str(e.id): e for e in await repo.list_entities(story.project_id)}
        alt_ids = {
            UUID(str(alt["entity_id"]))
            for c in pending
            for alt in c.alternatives
            if "entity_id" in alt
        }
        quotes_by_uuid = await list_recent_mention_texts_for_entities(
            conn, list(alt_ids), limit_per_entity=1
        )
        quotes_by_id = {str(k): v for k, v in quotes_by_uuid.items()}
    except (OperationalError, ServiceUnavailable):
        entities_by_id, quotes_by_id = {}, {}  # degrade to an unenriched queue
    return CandidatesResponse(
        candidates=[
            enrich_candidate_view(c, entities_by_id, quotes_by_id, language=language)
            for c in pending
        ]
    )


# --- Duplicate-suggestion surface (graph-quality S4a) -----------------------


def get_accepted_reader(request: Request) -> AcceptedEntityReader:
    """The app-lifetime accepted-graph snapshot reader wired in `main.py`."""
    reader: AcceptedEntityReader = request.app.state.accepted_reader
    return reader


def get_duplicate_dismissal_store(request: Request) -> PostgresDuplicateDismissalStore:
    """The app-lifetime dismissed-duplicate-pair store wired in `main.py` (DM-CD-3)."""
    store: PostgresDuplicateDismissalStore = request.app.state.duplicate_dismissal_store
    return store


class DuplicateEntityView(BaseModel):
    """One side of a suggested duplicate pair, enriched for verification (S3/DM-EE-3 context).

    Carries the identity context the author needs to judge a merge: the display name, the
    `type` (shown, never a filter — INV-4), the `aliases`, and one sample mention `context_quote`
    (None when the entity has no surfaced mention).
    """

    entity_id: UUID
    canonical_name: str
    type: str
    aliases: list[str]
    context_quote: str | None


class DuplicateSuggestionView(BaseModel):
    """One suggested duplicate pair for review: the two entities + why they were surfaced.

    `cosine_score` is None when neither entity had a usable mention vector (name-only). The
    author reviews the pair and either commits the merge (the existing merge endpoint, S4b) or
    dismisses it (`POST …/duplicate-suggestions/dismiss`). Suggests only — writes no graph.
    """

    entity_a: DuplicateEntityView
    entity_b: DuplicateEntityView
    name_score: float
    cosine_score: float | None
    combined_score: float


class DuplicateSuggestionsResponse(BaseModel):
    """A project's ranked likely-duplicate pairs (dismissed pairs already suppressed)."""

    suggestions: list[DuplicateSuggestionView]


class DismissDuplicateRequest(BaseModel):
    """The pair the author marked (or un-marked) as 'not a duplicate' — unordered."""

    entity_id_a: UUID
    entity_id_b: UUID


def _duplicate_entity_view(
    entity: GraphEntity, snapshot: AcceptedSnapshot, *, language: str
) -> DuplicateEntityView:
    """Project an accepted entity to its suggestion-row view, enriched from the snapshot (pure)."""
    quotes = snapshot.recent_mentions.get(entity.id, [])
    return DuplicateEntityView(
        entity_id=entity.id,
        canonical_name=canonical_for_language(entity, language) or "",
        type=entity.type,
        aliases=list(entity.aliases),
        context_quote=quotes[0] if quotes else None,
    )


@router.get(
    "/{story_id}/duplicate-suggestions",
    responses={
        404: {"model": ErrorResponse, "description": "Story not found."},
        503: {"model": ErrorResponse, "description": "A data store is unavailable."},
    },
)
async def list_duplicate_suggestions(
    story_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    reader: Annotated[AcceptedEntityReader, Depends(get_accepted_reader)],
    store: Annotated[PostgresDuplicateDismissalStore, Depends(get_duplicate_dismissal_store)],
) -> DuplicateSuggestionsResponse:
    """Likely-duplicate entity pairs over a story's accepted graph (graph-quality S4).

    Re-points the §3.3 matcher inward: assembles the `AcceptedSnapshot` once, runs the pure
    self-join (name + embedding, floored at `duplicate_suggest_floor` / the Stage-2 cosine bar),
    drops any pair the author has dismissed, and enriches each side with S3 (DM-EE-3) verification
    context. Ranked strongest-first. **Suggests only — writes no graph** (INV-1/INV-9); the human
    commits each merge through the existing merge endpoint. Snapshot + dismissal reads are one
    project-scoped batch; a store outage is a declared 503.
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        project = await get_project(conn, story.project_id)
        # The accepted-graph snapshot (Neo4j + Postgres) and the dismissal set (Postgres) are
        # independent reads over separate connections — fetch them concurrently.
        snapshot, dismissed = await asyncio.gather(
            reader.load_accepted(story.project_id),
            store.list_pair_ids(story.project_id),
        )
    except (OperationalError, ServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc
    language = project.language if project is not None else "pl"
    entities_by_id = {e.id: e for e in snapshot.entities}
    # The self-join is a pure, CPU-bound O(n²) pass; run it off the event loop so a large
    # accepted graph can't block other requests. (The O(n²) scaling itself is the named
    # blocking/LSH revisit-lever for a future multi-thousand-node graph — ADR 0010, Layer 9.)
    pairs = await asyncio.to_thread(
        suggest_duplicate_pairs,
        snapshot,
        name_floor=settings.duplicate_suggest_floor,
        cosine_floor=settings.match_stage2_cosine_merge,
    )
    suggestions: list[DuplicateSuggestionView] = []
    for pair in pairs:
        if dismissal_pair_id(story.project_id, pair.entity_id_lo, pair.entity_id_hi) in dismissed:
            continue
        entity_a = entities_by_id.get(pair.entity_id_lo)
        entity_b = entities_by_id.get(pair.entity_id_hi)
        if entity_a is None or entity_b is None:
            continue  # defensive — the snapshot is self-consistent by construction
        suggestions.append(
            DuplicateSuggestionView(
                entity_a=_duplicate_entity_view(entity_a, snapshot, language=language),
                entity_b=_duplicate_entity_view(entity_b, snapshot, language=language),
                name_score=pair.name_score,
                cosine_score=pair.cosine_score,
                combined_score=pair.combined_score,
            )
        )
    return DuplicateSuggestionsResponse(suggestions=suggestions)


@router.post(
    "/{story_id}/duplicate-suggestions/dismiss",
    status_code=204,
    responses={
        404: {"model": ErrorResponse, "description": "Story not found."},
        503: {"model": ErrorResponse, "description": "The dismissal store is unavailable."},
    },
)
async def dismiss_duplicate_suggestion(
    story_id: UUID,
    body: DismissDuplicateRequest,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    store: Annotated[PostgresDuplicateDismissalStore, Depends(get_duplicate_dismissal_store)],
) -> None:
    """Record a 'not a duplicate' so the pair is not re-suggested (DM-CD-3). Idempotent."""
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        await store.insert(story.project_id, body.entity_id_a, body.entity_id_b)
    except OperationalError as exc:
        raise HTTPException(status_code=503, detail="the dismissal store is unavailable") from exc


@router.delete(
    "/{story_id}/duplicate-suggestions/dismiss",
    status_code=204,
    responses={
        404: {"model": ErrorResponse, "description": "Story not found."},
        503: {"model": ErrorResponse, "description": "The dismissal store is unavailable."},
    },
)
async def undismiss_duplicate_suggestion(
    story_id: UUID,
    body: DismissDuplicateRequest,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    store: Annotated[PostgresDuplicateDismissalStore, Depends(get_duplicate_dismissal_store)],
) -> None:
    """Un-dismiss a pair so it can be suggested again (reversibility, DM-CD-3).

    Silent no-op if the pair was not dismissed.
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        await store.delete(story.project_id, body.entity_id_a, body.entity_id_b)
    except OperationalError as exc:
        raise HTTPException(status_code=503, detail="the dismissal store is unavailable") from exc


# --- Name-normalisation surface (graph-quality S6a) -------------------------

LabelSurface = Literal["predicate", "type"]


def get_label_vocabulary_reader(request: Request) -> LabelVocabularyReader:
    """The app-lifetime label-vocabulary reader wired in `main.py` (S6a)."""
    reader: LabelVocabularyReader = request.app.state.label_vocabulary_reader
    return reader


def get_label_dismissal_store(request: Request) -> PostgresLabelDismissalStore:
    """The app-lifetime dismissed-label-pair store wired in `main.py` (DM-NN-3)."""
    store: PostgresLabelDismissalStore = request.app.state.label_dismissal_store
    return store


class LabelSynonymView(BaseModel):
    """One suggested synonymous label pair within a surface: the two labels + why + counts.

    `label_lo`/`label_hi` are the pair in canonical order; `count_lo`/`count_hi` are their edge
    (predicate) or node (type) counts in that same order, so the author can normalise toward the
    dominant form. `cosine_score` is None when neither label carried a usable embedding
    (name-only). Suggests only — the human renames graph-wide (S6a-2) or dismisses.
    """

    label_lo: str
    label_hi: str
    count_lo: int
    count_hi: int
    name_score: float
    cosine_score: float | None
    combined_score: float


class LabelVocabularyResponse(BaseModel):
    """A story's ranked synonym suggestions over both vocabularies (dismissed pairs suppressed).

    The two surfaces are returned separately because a predicate is never a synonym of a type
    (they are stored differently and renamed by different apply paths — DM-NN-1).
    """

    predicate_suggestions: list[LabelSynonymView]
    type_suggestions: list[LabelSynonymView]


class DismissLabelRequest(BaseModel):
    """The label pair marked (or un-marked) as 'not synonyms' — unordered, on a surface."""

    surface: LabelSurface
    label_a: str
    label_b: str


class RenameLabelRequest(BaseModel):
    """A graph-wide rename of one label on a surface: `from_label` → `to_label` (S6a-2, NN-4/5)."""

    surface: LabelSurface
    from_label: str
    to_label: str

    @field_validator("from_label")
    @classmethod
    def _from_label_present(cls, value: str) -> str:
        # `from_label` must match the stored label **verbatim** — a stored predicate/type can carry
        # surrounding whitespace (the S6a-1 read half normalises only for *comparison*, not the
        # stored form), so stripping it here would make the rename silently miss exactly the messy
        # label it targets. Reject a blank, but preserve the value as-typed.
        if not value.strip():
            raise ValueError("label must be a non-empty string")
        return value

    @field_validator("to_label")
    @classmethod
    def _to_label_non_empty(cls, value: str) -> str:
        # The new canonical form: strip it so the author can't bake stray whitespace into it.
        stripped = value.strip()
        if not stripped:
            raise ValueError("label must be a non-empty string")
        return stripped


class RenameSummaryResponse(BaseModel):
    """The outcome the normalise-names list shows after a rename (S6a-2). `folded_count` is the
    number of edges a predicate rename collapsed onto a pre-existing target (the reported
    side-effect, never the goal) — always 0 for a type relabel, which never merges nodes."""

    surface: LabelSurface
    renamed_count: int
    folded_count: int


def _label_synonym_views(
    pairs: list[LabelSynonymSuggestion],
    dismissed: set[UUID],
    *,
    project_id: UUID,
    surface: LabelSurface,
) -> list[LabelSynonymView]:
    """Project the ranked pairs to views, dropping any the author has dismissed on this surface."""
    views: list[LabelSynonymView] = []
    for pair in pairs:
        if label_dismissal_id(project_id, surface, pair.label_lo, pair.label_hi) in dismissed:
            continue
        views.append(
            LabelSynonymView(
                label_lo=pair.label_lo,
                label_hi=pair.label_hi,
                count_lo=pair.count_lo,
                count_hi=pair.count_hi,
                name_score=pair.name_score,
                cosine_score=pair.cosine_score,
                combined_score=pair.combined_score,
            )
        )
    return views


@router.get(
    "/{story_id}/label-vocabulary",
    responses={
        404: {"model": ErrorResponse, "description": "Story not found."},
        503: {"model": ErrorResponse, "description": "A data store is unavailable."},
    },
)
async def list_label_synonyms(
    story_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    reader: Annotated[LabelVocabularyReader, Depends(get_label_vocabulary_reader)],
    store: Annotated[PostgresLabelDismissalStore, Depends(get_label_dismissal_store)],
) -> LabelVocabularyResponse:
    """Synonym suggestions over a story's predicate + entity-type vocabularies (graph-quality S6).

    Assembles both distinct-label vocabularies (with counts + label-string embeddings), runs the
    pure self-join per surface (normalised name + embedding, floored at
    `name_normalise_suggest_floor` / the Stage-2 cosine bar), and drops any pair the author has
    dismissed. Ranked strongest-first per surface. **Suggests only — writes no graph** (INV-1/
    INV-4); the human renames graph-wide (S6a-2) or dismisses. Vocabulary + dismissal reads are
    one project-scoped batch; a store outage is a declared 503.
    """
    try:
        story = await get_story(conn, story_id)
        if story is None:
            raise HTTPException(status_code=404, detail="story not found")
        # The vocabularies (Neo4j + local encode) and the dismissal set (Postgres) are independent
        # reads over separate connections — fetch them concurrently.
        (predicate_entries, type_entries), dismissed = await asyncio.gather(
            reader.load_vocabulary(story.project_id),
            store.list_pair_ids(story.project_id),
        )
    except (OperationalError, ServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc
    # Each self-join is a pure, CPU-bound pass over a small vocabulary (tens of labels); run them
    # off the event loop for consistency with the S4 self-join. No blocking/LSH lever is needed at
    # this scale — the vocabulary is tens of labels (proposal Layer 9).
    floors = {
        "name_floor": settings.name_normalise_suggest_floor,
        "cosine_floor": settings.match_stage2_cosine_merge,
    }
    predicate_pairs, type_pairs = await asyncio.gather(
        asyncio.to_thread(suggest_label_synonyms, predicate_entries, **floors),
        asyncio.to_thread(suggest_label_synonyms, type_entries, **floors),
    )
    return LabelVocabularyResponse(
        predicate_suggestions=_label_synonym_views(
            predicate_pairs, dismissed, project_id=story.project_id, surface="predicate"
        ),
        type_suggestions=_label_synonym_views(
            type_pairs, dismissed, project_id=story.project_id, surface="type"
        ),
    )


@router.post(
    "/{story_id}/label-vocabulary/dismiss",
    status_code=204,
    responses={
        404: {"model": ErrorResponse, "description": "Story not found."},
        503: {"model": ErrorResponse, "description": "The dismissal store is unavailable."},
    },
)
async def dismiss_label_synonym(
    story_id: UUID,
    body: DismissLabelRequest,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    store: Annotated[PostgresLabelDismissalStore, Depends(get_label_dismissal_store)],
) -> None:
    """Record a 'not synonyms' so the label pair is not re-suggested (DM-NN-3). Idempotent."""
    try:
        story = await get_story(conn, story_id)
        if story is None:
            raise HTTPException(status_code=404, detail="story not found")
        await store.insert(story.project_id, body.surface, body.label_a, body.label_b)
    except OperationalError as exc:
        raise HTTPException(status_code=503, detail="the dismissal store is unavailable") from exc


@router.delete(
    "/{story_id}/label-vocabulary/dismiss",
    status_code=204,
    responses={
        404: {"model": ErrorResponse, "description": "Story not found."},
        503: {"model": ErrorResponse, "description": "The dismissal store is unavailable."},
    },
)
async def undismiss_label_synonym(
    story_id: UUID,
    body: DismissLabelRequest,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    store: Annotated[PostgresLabelDismissalStore, Depends(get_label_dismissal_store)],
) -> None:
    """Un-dismiss a label pair so it can be suggested again (reversibility, DM-NN-3).

    Silent no-op if the pair was not dismissed.
    """
    try:
        story = await get_story(conn, story_id)
        if story is None:
            raise HTTPException(status_code=404, detail="story not found")
        await store.delete(story.project_id, body.surface, body.label_a, body.label_b)
    except OperationalError as exc:
        raise HTTPException(status_code=503, detail="the dismissal store is unavailable") from exc


@router.post(
    "/{story_id}/label-vocabulary/rename",
    responses={
        404: {"model": ErrorResponse, "description": "Story not found."},
        503: {"model": ErrorResponse, "description": "A data store is unavailable."},
    },
)
async def rename_label(
    story_id: UUID,
    body: RenameLabelRequest,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    edit: Annotated[EntityEditService, Depends(get_entity_edit)],
) -> RenameSummaryResponse:
    """Rename a label graph-wide on its surface (S6a-2, DM-NN-4/5) — human-gated (INV-1/INV-9),
    reversible via the graph-edit undo log (INV-3).

    A **predicate** rename re-keys every bearing edge in one grouped op (preserving each `edge_uid`,
    INV-10; folding identical triples, reported via `folded_count`); a **type** rename is a bulk
    `SET n.type` relabel that never merges nodes (`folded_count` always 0). A label nothing bears
    renames nothing (0/0). `get_story` runs inside the declared-503 guard so a store outage on the
    lookup maps to 503, not a bare 500 (the S82 edit-route pattern the read routes already follow).
    """
    try:
        story = await get_story(conn, story_id)
        if story is None:
            raise HTTPException(status_code=404, detail="story not found")
        if body.surface == "predicate":
            renamed = await edit.rename_predicate(story.project_id, body.from_label, body.to_label)
            summary = RenameSummaryResponse(
                surface="predicate",
                renamed_count=renamed.renamed_count,
                folded_count=renamed.folded_count,
            )
        else:
            relabelled = await edit.relabel_entity_type(
                story.project_id, body.from_label, body.to_label
            )
            summary = RenameSummaryResponse(
                surface="type", renamed_count=relabelled.relabelled_count, folded_count=0
            )
    except (OperationalError, ServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc
    return summary


class AcceptRequest(BaseModel):
    """The reviewer's decision (spec §3.3 Stage 4). All optional — defaults to the proposal.

    `action` overrides the cascade's proposal (accept-as-merge / accept-as-create);
    `target_entity_id` retargets a merge (change-target); `custom_type` sets a type on create.
    """

    action: Literal["create", "merge"] | None = None
    target_entity_id: UUID | None = None
    custom_type: str | None = None


class ReviewResponse(BaseModel):
    """Outcome of an accept/reject: the committed entity (if any) + the terminal status."""

    candidate_id: UUID
    status: Literal["created", "merged", "rejected"]
    entity_id: UUID | None
    already_decided: bool


@router.post(
    "/{story_id}/candidates/{candidate_id}/accept",
    responses={
        404: {"model": ErrorResponse, "description": "Story or candidate not found."},
        409: {"model": ErrorResponse, "description": "Merge target no longer exists (stale)."},
        503: {"model": ErrorResponse, "description": "A data store is unavailable."},
    },
)
async def accept_candidate(
    story_id: UUID,
    candidate_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    review: Annotated[CandidateReviewService, Depends(get_candidate_review)],
    body: AcceptRequest | None = None,
) -> ReviewResponse:
    """Commit a staged candidate to the graph — create a new entity or merge (spec §7 step 7).

    This is the **only** graph-writing path (INV-1): the machine proposed, the human commits.
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    project = await get_project(conn, story.project_id)
    language = project.language if project is not None else "en"
    request = body or AcceptRequest()
    try:
        result = await review.accept(
            candidate_id,
            language=language,
            action=request.action,
            target_entity_id=request.target_entity_id,
            custom_type=request.custom_type,
        )
    except CandidateNotFound as exc:
        raise HTTPException(status_code=404, detail="candidate not found") from exc
    except StaleMergeTarget as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OperationalError, ServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc
    return ReviewResponse(
        candidate_id=result.candidate_id,
        status=result.status,  # terminal after accept
        entity_id=result.entity_id,
        already_decided=result.already_decided,
    )


@router.post(
    "/{story_id}/candidates/{candidate_id}/reject",
    responses={
        404: {"model": ErrorResponse, "description": "Story or candidate not found."},
        503: {"model": ErrorResponse, "description": "The staging store is unavailable."},
    },
)
async def reject_candidate(
    story_id: UUID,
    candidate_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    review: Annotated[CandidateReviewService, Depends(get_candidate_review)],
) -> ReviewResponse:
    """Reject a staged candidate — nothing enters the graph; the rejection is recorded.

    The rejection is stored as evidence so a future matcher can consult it and not re-pester
    the author (DM-rej); that consult is not built in S4a.
    """
    if await get_story(conn, story_id) is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        result = await review.reject(candidate_id)
    except CandidateNotFound as exc:
        raise HTTPException(status_code=404, detail="candidate not found") from exc
    except OperationalError as exc:
        raise HTTPException(status_code=503, detail="the staging store is unavailable") from exc
    return ReviewResponse(
        candidate_id=result.candidate_id,
        status=result.status,  # terminal after reject
        entity_id=result.entity_id,
        already_decided=result.already_decided,
    )


# --- Decide relations (Stage 4, the 5th human action): list committable / decide ---


def get_relation_review(request: Request) -> RelationReviewService:
    """The app-lifetime relation-decide service wired in `main.py` (the only edge writer)."""
    service: RelationReviewService = request.app.state.relation_review
    return service


def get_relation_store(request: Request) -> PostgresRelationStore:
    """The app-lifetime `staged_relations` store wired in `main.py` (the edge-evidence read, S3)."""
    store: PostgresRelationStore = request.app.state.relation_store
    return store


@router.get(
    "/{story_id}/relations/{edge_id}/evidence",
    responses={
        404: {"model": ErrorResponse, "description": "Story not found."},
        503: {"model": ErrorResponse, "description": "The staging store is unavailable."},
    },
)
async def get_edge_evidence(
    story_id: UUID,
    edge_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    store: Annotated[PostgresRelationStore, Depends(get_relation_store)],
) -> EdgeEvidence:
    """The recorded source(s) behind one committed graph edge (graph-quality §3 S3, DM-EE-1/2).

    A read/verify surface (writes nothing): fetch every `written` `staged_relations` row for this
    content-addressed `edge_id` (the complete one-to-many provenance) and resolve each row's
    paragraph text. A zero-row edge is a valid case — a manually-added edge stages no relation — and
    returns an empty `source_provenance` (the client renders "added manually"), not a 404.
    """
    if await get_story(conn, story_id) is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        rows = await store.get_written_by_edge_id(story_id, edge_id)
        # One batched fetch for the source paragraphs (avoid an N+1 over the one-to-many set).
        paragraph_texts = await list_paragraph_texts_by_ids(
            conn, [row.paragraph_id for row in rows]
        )
    except OperationalError as exc:
        raise HTTPException(status_code=503, detail="the staging store is unavailable") from exc
    return build_edge_evidence(rows, paragraph_texts)


class RelationView(BaseModel):
    """One committable relation for the §3.3 5th human action ("decide on relations").

    Carries the surface triple + the cascade's confidence and the entity ids both endpoints
    currently resolve to (committed entities in the same paragraph). The UI (S4f) renders the
    surface strings and can resolve names from the resolved ids; persistence-only fields are
    omitted.
    """

    id: UUID
    paragraph_id: UUID
    subject: str
    predicate: str
    object: str
    confidence: float | None
    subject_entity_id: UUID
    object_entity_id: UUID


class RelationsResponse(BaseModel):
    """A story's committable relations (both endpoints resolved) — the decide queue."""

    relations: list[RelationView]


class DecideRelationRequest(BaseModel):
    """The reviewer's relation decision: commit the edge, or reject the relation."""

    action: Literal["commit", "reject"]


class RelationDecisionResponse(BaseModel):
    """Outcome of a relation decision: the terminal status + the committed edge id (if any)."""

    relation_id: UUID
    status: RelationStatus
    edge_id: UUID | None
    already_decided: bool


@router.get(
    "/{story_id}/relations",
    responses={
        404: {"model": ErrorResponse, "description": "Story not found."},
        503: {"model": ErrorResponse, "description": "The staging store is unavailable."},
    },
)
async def list_relations(
    story_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    review: Annotated[RelationReviewService, Depends(get_relation_review)],
) -> RelationsResponse:
    """The committable relations for a story (spec §3.3's 5th Stage-4 action).

    A relation is committable once **both** surface endpoints resolve to entities the human has
    already accepted in that paragraph; relations with a held/unaccepted endpoint or a self-loop
    are excluded. The edge is written only on an explicit `decide` (INV-1/INV-9 — the human gate).
    """
    if await get_story(conn, story_id) is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        committable = await review.list_committable(story_id)
    except OperationalError as exc:
        raise HTTPException(status_code=503, detail="the staging store is unavailable") from exc
    return RelationsResponse(
        relations=[
            RelationView(
                id=c.relation.id,
                paragraph_id=c.relation.paragraph_id,
                subject=c.relation.subject,
                predicate=c.relation.predicate,
                object=c.relation.object,
                confidence=c.relation.confidence,
                subject_entity_id=c.subject_entity_id,
                object_entity_id=c.object_entity_id,
            )
            for c in committable
        ]
    )


@router.post(
    "/{story_id}/relations/{relation_id}/decide",
    responses={
        404: {"model": ErrorResponse, "description": "Story or relation not found."},
        409: {
            "model": ErrorResponse,
            "description": "An endpoint no longer resolves (stale/held).",
        },
        503: {"model": ErrorResponse, "description": "A data store is unavailable."},
    },
)
async def decide_relation(
    story_id: UUID,
    relation_id: UUID,
    body: DecideRelationRequest,
    conn: Annotated[AsyncConnection, Depends(get_connection)],
    review: Annotated[RelationReviewService, Depends(get_relation_review)],
) -> RelationDecisionResponse:
    """Commit (write the edge) or reject a staged relation under the human gate (spec §3.3).

    The **only** edge-writing path (INV-1/INV-9). Commit re-resolves both endpoints (TOCTOU)
    and writes the edge idempotently; an endpoint that no longer resolves, or a self-loop,
    yields 409 with nothing written.
    """
    if await get_story(conn, story_id) is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        result = await review.decide(relation_id, action=body.action)
    except RelationNotFound as exc:
        raise HTTPException(status_code=404, detail="relation not found") from exc
    except RelationEndpointsUnresolved as exc:
        raise HTTPException(
            status_code=409, detail="a relation endpoint no longer resolves (stale/held)"
        ) from exc
    except (OperationalError, ServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail="a data store is unavailable") from exc
    return RelationDecisionResponse(
        relation_id=result.relation_id,
        status=result.status,
        edge_id=result.edge_id,
        already_decided=result.already_decided,
    )
