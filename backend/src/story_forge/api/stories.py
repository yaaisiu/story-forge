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

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from neo4j.exceptions import ServiceUnavailable
from psycopg import AsyncConnection, OperationalError
from pydantic import BaseModel, field_validator

from story_forge.adapters.db import get_connection
from story_forge.adapters.llm.base import ProviderResponseError
from story_forge.adapters.neo4j_repo import Neo4jRepo
from story_forge.adapters.postgres_candidate_store import PostgresCandidateStore
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
    list_entity_mentions_for_story,
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
    RelationEdgeNotFound,
    SelfMergeError,
)
from story_forge.agents.extraction_agent import ExtractionError
from story_forge.agents.extraction_coordinator import ExtractionCoordinator
from story_forge.agents.matching_agent import ExistingEntity, search_entities
from story_forge.agents.relation_review import (
    RelationEndpointsUnresolved,
    RelationNotFound,
    RelationReviewService,
)
from story_forge.config import settings
from story_forge.domain.candidates import CandidateProposal, RelationStatus, StagedCandidate
from story_forge.domain.chunking import outline_to_tree
from story_forge.domain.entity_edits import EntityEditInvalid, EntityEditPatch
from story_forge.domain.entity_merge import EntityMergeInvalid
from story_forge.domain.graph import GraphEntity
from story_forge.domain.highlights import HighlightTarget, resolve_highlights
from story_forge.domain.language import detect_language
from story_forge.domain.models import Project, Story
from story_forge.domain.neighbourhood import EgoGraph, build_ego_graph
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


class ErrorResponse(BaseModel):
    """Shape FastAPI's ``HTTPException`` produces — declared so the OpenAPI
    schema names every non-2xx response the routes can return, instead of just
    success + the auto-added 422 validation error. Without this, the generated
    TypeScript client (`frontend/src/lib/api/schema.d.ts`) can't model expected
    outcomes like 404 / 409 / 502 — leaving frontend error handling untyped.
    """

    detail: str


@router.post(
    "/upload",
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Uploaded file is empty or unparseable."},
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

    Persistence-only fields (`properties`, `embedding`, `project_id`, `world_id`)
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
) -> GraphResponse:
    """The story's entity graph for the read-only viewer (spec §3.4).

    The graph is keyed by *project* (entities carry `project_id`, the §6.4
    multi-tenancy seam), so the route resolves the story to its project and returns
    that project's nodes/edges. No dedupe through M2 (INV-8) — the viewer renders
    whatever was written, duplicates and all, which is exactly the problem M3 solves.
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")

    entities = await repo.list_entities(story.project_id)
    relations = await repo.get_relations(story.project_id)
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
    story's **project** (the §6.4 tenancy key); cross-project / "whole world" search is
    deferred with the §3.4 graph.

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
    """One resolved highlight range `[start, end)` within a paragraph (spec §3.5)."""

    start: int
    end: int
    entity_id: UUID
    type: str


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
    mentioned entities are resolved to character ranges by render-time search over their surface
    forms (`resolve_highlights`); an entity whose forms don't occur is omitted (fail-closed), and
    only entities that actually appear are advertised in the tooltip catalog.
    """
    story = await get_story(conn, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    project = await get_project(conn, story.project_id)
    language = project.language if project is not None else "pl"

    paragraphs = await list_story_paragraphs(conn, story_id)
    mentions = await list_entity_mentions_for_story(conn, story_id)
    entities = await repo.list_entities(story.project_id)

    target_by_id = {
        e.id: HighlightTarget(entity_id=e.id, type=e.type, names=_entity_surface_forms(e))
        for e in entities
    }
    mentioned_by_paragraph: dict[UUID, set[UUID]] = {}
    for mention in mentions:
        mentioned_by_paragraph.setdefault(mention.paragraph_id, set()).add(mention.entity_id)

    reader_paragraphs: list[ReaderParagraph] = []
    appeared: set[UUID] = set()
    for paragraph in paragraphs:
        targets = [
            target_by_id[entity_id]
            for entity_id in mentioned_by_paragraph.get(paragraph.id, set())
            if entity_id in target_by_id
        ]
        resolved = resolve_highlights(paragraph.content, targets)
        appeared.update(h.entity_id for h in resolved)
        reader_paragraphs.append(
            ReaderParagraph(
                id=paragraph.id,
                text=paragraph.content,
                highlights=[
                    ReaderHighlight(start=h.start, end=h.end, entity_id=h.entity_id, type=h.type)
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
    is allowed — a manual one is intentional. Re-predicate is a remove + add, client-side."""

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


# --- Review queue (Stage 4): list pending / accept / reject -----------------


def get_candidate_store(request: Request) -> PostgresCandidateStore:
    """The app-lifetime candidate staging store wired in `main.py`."""
    store: PostgresCandidateStore = request.app.state.candidate_store
    return store


def get_candidate_review(request: Request) -> CandidateReviewService:
    """The app-lifetime accept/reject service wired in `main.py` (the only graph writer)."""
    service: CandidateReviewService = request.app.state.candidate_review
    return service


class CandidateView(BaseModel):
    """One staged candidate for the §3.3 Stage-4 review queue (the render set S4b consumes).

    Carries the quote/context (±200 chars), the cascade's NEW-vs-MERGE proposal + the stage it
    reached, the judge's reasoning (if Stage 3 ran), and the top-3 alternative entities the
    reviewer can retarget to. Persistence-only fields (the vector, project/story ids) are omitted.
    """

    id: UUID
    paragraph_id: UUID
    candidate_name: str
    type: str
    context: str
    proposal: CandidateProposal
    target_entity_id: UUID | None
    stage_reached: int
    confidence: float | None
    reasoning: str | None
    alternatives: list[dict[str, object]]


class CandidatesResponse(BaseModel):
    """A story's pending review queue."""

    candidates: list[CandidateView]


def _to_view(candidate: StagedCandidate) -> CandidateView:
    return CandidateView(
        id=candidate.id,
        paragraph_id=candidate.paragraph_id,
        candidate_name=candidate.candidate_name,
        type=candidate.type,
        context=candidate.context,
        proposal=candidate.proposal,
        target_entity_id=candidate.target_entity_id,
        stage_reached=candidate.stage_reached,
        confidence=candidate.confidence,
        reasoning=candidate.reasoning,
        alternatives=candidate.alternatives,
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
) -> CandidatesResponse:
    """The pending review queue for a story (spec §3.3 Stage 4) — candidates awaiting a human."""
    if await get_story(conn, story_id) is None:
        raise HTTPException(status_code=404, detail="story not found")
    try:
        pending = await store.list_pending(story_id)
    except OperationalError as exc:
        raise HTTPException(status_code=503, detail="the staging store is unavailable") from exc
    return CandidatesResponse(candidates=[_to_view(c) for c in pending])


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
