"""ExtractionCoordinator — the resumable batch driver for graph ingest (M2.S4 → M3.S4a).

Spec §7 steps 4–6 + §9 M3. Drives a whole story's paragraphs through the `ExtractionAgent`
and then, under **intercept-before-write** (DM6, ADR 0004), *stages* each extracted candidate
with the §3.3 cascade's proposal instead of writing the graph. Nothing here touches Neo4j —
the graph is written only when a human accepts at the review queue (INV-1 / INV-9). This is the
M2.S4 write-on-extract path refactored: the cascade + staging replace the old
candidate→graph mapping and its Neo4j/mention writes.

Two design points carried from M2.S4, both still load-bearing:

- **The *driver* owns pause-and-ask (OQ-2), not the agent.** The router's `BudgetExceededError`
  / `QuotaExhaustedError` propagate untouched through the extraction agent *and* the cascade's
  Stage-3 judge (spending more is the user's call). This driver catches them and returns a
  `paused` result *before persisting the in-flight paragraph*, so a re-run resumes cleanly.

- **Resume granularity is the paragraph, checkpointed by `paragraph_processed` (OQ-1).** A
  paragraph is "done" once its candidates (and a marker row, even for zero-candidate paragraphs)
  are committed — staged atomically by the store. Under intercept-before-write a re-run that
  re-stages is *safe* (nothing is in the graph yet), but the marker still makes it idempotent and
  stops a zero-candidate paragraph being reprocessed forever (the M2 wart this fixes).

The coordinator depends on Protocols (not concrete adapters), matching the repo's seams and
keeping the resume/pause logic unit-testable against fakes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from story_forge.adapters.llm.base import BudgetExceededError, QuotaExhaustedError
from story_forge.agents.candidate_staging import StagedParagraph
from story_forge.agents.extraction_agent import ExtractionProposal
from story_forge.domain.candidates import AcceptedSnapshot, StagedCandidate
from story_forge.domain.models import Paragraph


class Extractor(Protocol):
    """The per-paragraph extraction the driver needs (an `ExtractionAgent`)."""

    async def propose_extraction(
        self, *, paragraph_text: str, language: str
    ) -> ExtractionProposal: ...


class Stager(Protocol):
    """The per-paragraph §3.3 cascade the driver needs (a `CandidateStager`)."""

    async def stage(
        self,
        *,
        proposal: ExtractionProposal,
        paragraph: Paragraph,
        project_id: UUID,
        story_id: UUID,
        language: str,
        snapshot: AcceptedSnapshot,
    ) -> StagedParagraph: ...


class AcceptedReader(Protocol):
    """Reads the already-accepted graph the cascade matches against (read once per run)."""

    async def load_accepted(self, project_id: UUID) -> AcceptedSnapshot: ...


class CandidateStore(Protocol):
    """Staging persistence + the resume checkpoint the driver needs (Postgres-backed)."""

    async def persist(
        self,
        *,
        paragraph_id: UUID,
        story_id: UUID,
        candidates: list[StagedCandidate],
        relations: list[dict[str, object]],
    ) -> None: ...
    async def paragraphs_processed(self, paragraph_ids: list[UUID]) -> set[UUID]: ...


@dataclass(frozen=True)
class IngestResult:
    """Outcome of an `ingest_story` run.

    `paused` is the authoritative completion signal. `paragraphs_done` counts processed
    (staged-and-checkpointed) paragraphs — including zero-candidate ones, which now carry a
    marker — so a re-POST resumes from the first not-yet-processed paragraph.
    """

    paragraphs_total: int
    paragraphs_done: int  # processed (checkpointed) paragraphs — the resume marker
    candidates_staged: int  # this run only
    paused: bool
    pause_reason: str | None


class ExtractionCoordinator:
    """Runs extraction + the §3.3 cascade over a story's paragraphs and stages them, resumably."""

    def __init__(
        self,
        extractor: Extractor,
        stager: Stager,
        store: CandidateStore,
        reader: AcceptedReader,
    ) -> None:
        self._extractor = extractor
        self._stager = stager
        self._store = store
        self._reader = reader

    async def ingest_story(
        self,
        *,
        paragraphs: list[Paragraph],
        project_id: UUID,
        story_id: UUID,
        language: str,
    ) -> IngestResult:
        """Extract + cascade + stage every not-yet-processed paragraph; pause on budget/quota."""
        processed = await self._store.paragraphs_processed([p.id for p in paragraphs])
        todo = [p for p in paragraphs if p.id not in processed]
        candidates_staged = 0

        # Read the accepted graph once per run (C4 store-chatty mitigation): within a run
        # nothing is accepted, so the snapshot does not drift. Skip the read when idle.
        snapshot = await self._reader.load_accepted(project_id) if todo else AcceptedSnapshot()

        for paragraph in todo:
            try:
                proposal = await self._extractor.propose_extraction(
                    paragraph_text=paragraph.content, language=language
                )
                staged = await self._stager.stage(
                    proposal=proposal,
                    paragraph=paragraph,
                    project_id=project_id,
                    story_id=story_id,
                    language=language,
                    snapshot=snapshot,
                )
            except (BudgetExceededError, QuotaExhaustedError) as exc:
                # The router paused-and-asked mid-batch (extraction *or* the Stage-3 judge).
                # Stop cleanly *before persisting this paragraph*, so there is no half-staged
                # paragraph: everything already committed stays, this one re-stages on re-run.
                return IngestResult(
                    paragraphs_total=len(paragraphs),
                    paragraphs_done=len(processed),
                    candidates_staged=candidates_staged,
                    paused=True,
                    pause_reason=str(exc),
                )

            # Stage the paragraph's candidates + its resume marker atomically. The marker is
            # written even for a zero-candidate paragraph, so resume skips it next time.
            await self._store.persist(
                paragraph_id=paragraph.id,
                story_id=story_id,
                candidates=staged.candidates,
                relations=staged.relations,
            )
            processed.add(paragraph.id)
            candidates_staged += len(staged.candidates)

        return IngestResult(
            paragraphs_total=len(paragraphs),
            paragraphs_done=len(processed),
            candidates_staged=candidates_staged,
            paused=False,
            pause_reason=None,
        )
