"""ExtractionCoordinator — the resumable batch driver for graph ingest (M2.S4).

Spec §7 step 4 + §9 M2. Drives a whole story's paragraphs through the
`ExtractionAgent` and persists each paragraph's proposal as graph nodes/edges +
cross-store mentions. Two design points the milestone forced:

- **OQ-2 — the *driver* owns the pause-and-ask, not the agent.** The single-paragraph
  agent propagates the router's `BudgetExceededError` / `QuotaExhaustedError`
  untouched (spending more is the user's call). This driver *catches* them and returns
  a `paused` result instead of failing, so the caller can top up and re-run. Because
  each paragraph's mentions are committed as they are written (the mention store uses
  its own connection), a re-run resumes from the first paragraph without a mention —
  the durable "last-done" checkpoint (see OQ-1 / idempotency).

- **OQ-1 — write order is Neo4j then Postgres.** Per paragraph: entities → Neo4j,
  then their mentions → Postgres, then relations → Neo4j. Neo4j owns identity, so an
  orphaned node (crash between the two stores) is more benign than a mention pointing
  at a node that was never created. We accept that eventual inconsistency at PoC scale.

Resume granularity is the paragraph: "done" means the paragraph already has ≥1
mention. A paragraph that legitimately extracted **zero** entities writes no mention,
so a re-run will process it again — a wasted (cheap) LLM call, but never a duplicate
node, which is what matters under the no-dedupe contract (INV-8). The coordinator
depends on Protocols (not concrete adapters), matching the repo's `LLMProvider` /
`CostStore` / `OutlineProposer` seams and keeping the resume logic unit-testable
against fakes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from story_forge.adapters.llm.base import BudgetExceededError, QuotaExhaustedError
from story_forge.agents.extraction_agent import ExtractionProposal
from story_forge.agents.extraction_graph import proposal_to_graph
from story_forge.domain.graph import GraphEntity, GraphRelation
from story_forge.domain.models import EntityMention, Paragraph


class Extractor(Protocol):
    """The per-paragraph extraction the driver needs (an `ExtractionAgent`)."""

    async def propose_extraction(
        self, *, paragraph_text: str, language: str
    ) -> ExtractionProposal: ...


class GraphWriter(Protocol):
    """The graph writes the driver needs (a `Neo4jRepo`)."""

    async def create_entity(self, entity: GraphEntity) -> None: ...
    async def create_relation(self, relation: GraphRelation) -> None: ...


class MentionStore(Protocol):
    """The mention persistence + resume checkpoint the driver needs (Postgres-backed)."""

    async def add_mention(self, mention: EntityMention) -> None: ...
    async def paragraphs_with_mentions(self, paragraph_ids: list[UUID]) -> set[UUID]: ...


@dataclass(frozen=True)
class IngestResult:
    """Outcome of an `ingest_story` run.

    `paused` is the authoritative completion signal — NOT `paragraphs_done ==
    paragraphs_total`, because a zero-entity paragraph never becomes "done" (it has
    no mention). The caller returns a partial-progress 202 when `paused` is true and a
    200 otherwise.
    """

    paragraphs_total: int
    paragraphs_done: int  # paragraphs carrying ≥1 mention (the resumable checkpoint)
    entities_written: int  # this run only
    relations_written: int  # this run only
    paused: bool
    pause_reason: str | None


class ExtractionCoordinator:
    """Runs extraction over a story's paragraphs and persists the graph, resumably."""

    def __init__(self, extractor: Extractor, graph: GraphWriter, mentions: MentionStore) -> None:
        self._extractor = extractor
        self._graph = graph
        self._mentions = mentions

    async def ingest_story(
        self,
        *,
        paragraphs: list[Paragraph],
        project_id: UUID,
        language: str,
    ) -> IngestResult:
        """Extract + persist every not-yet-done paragraph; pause on budget/quota."""
        done = await self._mentions.paragraphs_with_mentions([p.id for p in paragraphs])
        entities_written = 0
        relations_written = 0

        for paragraph in paragraphs:
            if paragraph.id in done:
                continue  # already has a mention — skip to avoid duplicate nodes
            try:
                proposal = await self._extractor.propose_extraction(
                    paragraph_text=paragraph.content, language=language
                )
            except (BudgetExceededError, QuotaExhaustedError) as exc:
                # The router paused-and-asked mid-batch. Stop cleanly *before* writing
                # this paragraph (the exception fires during the LLM call, before any
                # write), so there is no partial paragraph. Everything up to here is
                # committed; a re-run resumes from this paragraph.
                return IngestResult(
                    paragraphs_total=len(paragraphs),
                    paragraphs_done=len(done),
                    entities_written=entities_written,
                    relations_written=relations_written,
                    paused=True,
                    pause_reason=str(exc),
                )

            graph = proposal_to_graph(
                proposal,
                project_id=project_id,
                paragraph_id=paragraph.id,
                language=language,
            )
            # OQ-1 order: entities (Neo4j) → mentions (Postgres) → relations (Neo4j).
            for entity in graph.entities:
                await self._graph.create_entity(entity)
            for mention in graph.mentions:
                await self._mentions.add_mention(mention)
            for relation in graph.relations:
                await self._graph.create_relation(relation)

            if graph.mentions:
                done.add(paragraph.id)
            entities_written += len(graph.entities)
            relations_written += len(graph.relations)

        return IngestResult(
            paragraphs_total=len(paragraphs),
            paragraphs_done=len(done),
            entities_written=entities_written,
            relations_written=relations_written,
            paused=False,
            pause_reason=None,
        )
