"""ExtractionAgent — one paragraph → proposed entity & relation candidates.

Step 4 of the ingest pipeline (spec §7, Appendix C.2). The second agent built and
the **first wired to the `LLMRouter`**: it calls `router.complete(...)` rather than
a concrete provider, so tier selection, failover, the budget cap, and the cost
ledger live in the router (spec §6.5/§6.6). The agent owns only the *prompt-retry*
axis — render prompt → call router → parse + validate → retry on schema failure —
mirroring `ChunkingAgent`. The two axes are deliberately separate: the router fails
over *providers* on transport/envelope failure; the agent retries the *prompt* on
schema failure (the accepted M2.S3 proposal, §4).

The output is a *proposal* (spec §3.2): an `ExtractionProposal` of candidates as
named in this one paragraph. A candidate carries no `id`, no resolved bilingual
`canonical_name`, and no embedding — those are assigned downstream (M2.S4 write /
M3 match + human review). Conflating a candidate with a graph entity is the central
modelling trap, so the surface form is `candidate_name`, never `canonical_name`.

Granularity is **per-paragraph** (proposal D4), but the agent is fragment-agnostic:
it extracts from whatever text it is handed, so a per-scene dispatch later is a
caller change, not an agent change. Batching + the pause-and-ask catcher are M2.S4
(proposal D5); here the router's `BudgetExceededError` / `QuotaExhaustedError`
*propagate* untouched — spending more is the user's call, never the agent's retry.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field, field_validator

from story_forge.adapters.llm.base import Router
from story_forge.agents.validation import validate_with_retry
from story_forge.prompts import PromptNotFound, render_messages


class EntityCandidate(BaseModel):
    """An entity as named in one paragraph — a *proposal*, not a graph entity.

    `candidate_name` is the surface form (spec Appendix C.2); the resolved bilingual
    `canonical_name` (§3.2) is assigned at M3 merge, never here. `type` is a free
    string (open-world ontology, INV-4): the prompt's examples constrain but do not
    restrict it, so a never-before-seen type validates. `evidence_quote` is nullable
    because the agent drops it when it cannot be grounded in the paragraph (G5).
    """

    candidate_name: str
    type: str
    match_hint: str | None = None
    match_confidence: float = Field(ge=0.0, le=1.0)
    properties: dict[str, object] = Field(default_factory=dict)
    evidence_quote: str | None = None

    @field_validator("candidate_name")
    @classmethod
    def _name_non_empty(cls, value: str) -> str:
        # A candidate with no surface form is unusable downstream — reject it so it
        # triggers a prompt retry rather than passing through as a nameless node.
        if not value.strip():
            raise ValueError("candidate_name must be a non-empty surface form")
        return value


class RelationCandidate(BaseModel):
    """A typed, directed link proposed from one paragraph (spec §3.2, C.2).

    `subject`/`object` are surface forms or known-entity ids; the link may be
    *dangling* (an endpoint that is neither a candidate here nor a known entity) —
    accepted, since the open world plus M3 human review resolve dangling endpoints.
    """

    subject: str
    predicate: str
    object: str
    evidence_quote: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("subject", "predicate", "object")
    @classmethod
    def _endpoint_non_empty(cls, value: str) -> str:
        # A blank endpoint or predicate is unusable downstream (the graph writer
        # would get a relation with no resolvable endpoint or type), so reject it to
        # trigger a prompt retry. Distinct from an intentionally *dangling* relation,
        # whose endpoint is a real surface form that M3 resolves — that still needs a
        # non-empty name; only its resolution is deferred.
        if not value.strip():
            raise ValueError("relation subject/predicate/object must be non-empty")
        return value


class ExtractionProposal(BaseModel):
    """The agent's output: candidates from one paragraph, reviewed downstream.

    Both lists may be empty — a transition paragraph legitimately has no entities,
    and empty is a *success*, never an error (so the agent must not retry it).
    """

    entities: list[EntityCandidate] = Field(default_factory=list)
    relations: list[RelationCandidate] = Field(default_factory=list)


class ExtractionError(RuntimeError):
    """Raised when no valid proposal could be produced (bad language or bad output)."""


# The output schema is constant for the class — build it once, not per paragraph
# (extraction runs per paragraph, so this would otherwise rebuild thousands of times).
_SCHEMA = ExtractionProposal.model_json_schema()


def _normalise_ws(text: str) -> str:
    """Collapse runs of whitespace to single spaces, for the substring soft-flag."""
    return " ".join(text.split())


def _ground_evidence_quotes(
    proposal: ExtractionProposal, paragraph_text: str
) -> ExtractionProposal:
    """Drop any `evidence_quote` that is not grounded in the paragraph (G5 soft-flag).

    A quote that is not a whitespace-normalised substring of the source paragraph is
    provenance we cannot trust, so we drop *the quote* — but keep the candidate, as
    the model legitimately paraphrases or truncates elsewhere and we will not punish
    that as fabrication.

    Grounding needs `paragraph_text`, which isn't in the JSON. A Pydantic
    `model_validator(mode="after")` reading it from validation `context=` could attach
    the rule to the model itself; we keep it an explicit post-validation pass instead
    — the only producer is this agent, so a plain pass is simpler than threading
    validation context through every construction site (revisit if a second producer
    of `ExtractionProposal` appears).
    """
    haystack = _normalise_ws(paragraph_text)

    def grounded(quote: str | None) -> str | None:
        normalised = _normalise_ws(quote) if quote else ""
        # An empty/blank quote carries no provenance, so treat it as "no quote"
        # (None) rather than letting "" pass as a substring of everything.
        if not normalised:
            return None
        return quote if normalised in haystack else None

    for entity in proposal.entities:
        entity.evidence_quote = grounded(entity.evidence_quote)
    for relation in proposal.relations:
        relation.evidence_quote = grounded(relation.evidence_quote)
    return proposal


class ExtractionAgent:
    """Turns one paragraph into proposed entity/relation candidates via the router."""

    def __init__(self, router: Router, *, max_retries: int = 2) -> None:
        self._router = router
        self._max_retries = max_retries

    async def propose_extraction(
        self,
        *,
        paragraph_text: str,
        language: str,
        known_entities: list[dict[str, object]] | None = None,
        custom_types: list[str] | None = None,
        neighbors: list[str] | None = None,
    ) -> ExtractionProposal:
        """Propose candidates for one paragraph, retrying on malformed/invalid output.

        `known_entities` + `custom_types` are de-duplication *hints* for the prompt
        (INV-8: a hint, never a merge); the real Neo4j read that populates them is
        M2.S4 wiring, so the first end-to-end passes empty lists. PreNER-hint
        injection (proposal D3) is deferred until a real eval exists — the parameter
        is added then, with a concrete type, rather than shipped dead now.
        """
        try:
            messages = render_messages(
                "extraction",
                language,
                paragraph_text=paragraph_text,
                existing_entities_json=json.dumps(known_entities or [], ensure_ascii=False),
                custom_entity_types=json.dumps(custom_types or [], ensure_ascii=False),
                neighbor_paragraphs="\n\n".join(neighbors or []),
            )
        except PromptNotFound as exc:
            raise ExtractionError(f"no extraction prompt for language {language!r}") from exc

        # The shared loop retries parse/schema failures only — a sampling model can
        # return valid JSON on a second pass. The router owns transport/envelope failover
        # and the budget cap, so its `BudgetExceededError` / `QuotaExhaustedError` (and any
        # re-raised transport error) fall straight through to the caller, never retried.
        proposal = await validate_with_retry(
            ExtractionProposal,
            lambda: self._router.complete(
                messages, weight="medium", task_type="extraction", json_schema=_SCHEMA
            ),
            max_retries=self._max_retries,
            error=ExtractionError,
            label="extraction",
        )
        return _ground_evidence_quotes(proposal, paragraph_text)
