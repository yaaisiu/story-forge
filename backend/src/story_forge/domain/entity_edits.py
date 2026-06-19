"""Pure entity-edit validation + field-merge (M4.S3a, the first graph *write* slice).

Given a committed `GraphEntity` and an `EntityEditPatch`, produce the validated next-state
or raise `EntityEditInvalid`. Pure — no store, no I/O — so the boundary rules (INV-4 open
`properties`, a non-blank canonical name + type) are unit-tested without a database. The
`EntityEditService` (`agents/entity_edit.py`) calls this, writes the graph, then records the
before→after evidence (DM-S3a-2) built from `diff_entity`.

`properties` stays an **open** JSON object with **free keys** (INV-4 — never a fixed enum), and
when set it **replaces** the whole map (the side panel sends the full edited object). An unset
patch field (`None`) means *unchanged*; a blank name string clears that one name (the entity must
keep at least one).
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from story_forge.domain.graph import GraphEntity

_EDITABLE_FIELDS = ("canonical_name_pl", "canonical_name_en", "type", "aliases", "properties")


class EntityEditInvalid(ValueError):
    """A patch that would leave the entity semantically invalid (→400): a fully-blank canonical
    name or a blank type. Distinct from FastAPI's request-shape 422 (a non-object `properties` or
    wrong-typed field is rejected at the pydantic boundary, before this runs)."""


class EntityEditPatch(BaseModel):
    """A partial edit of a committed entity (M4.S3a). Every field optional; an unset field
    (`None`) leaves it unchanged. `properties`, when set, replaces the whole map and stays open
    per INV-4 (pydantic guarantees it is a JSON object; values keep their type — DM-S3a-5)."""

    canonical_name_pl: str | None = None
    canonical_name_en: str | None = None
    type: str | None = None
    aliases: list[str] | None = None
    properties: dict[str, object] | None = None


@dataclass(frozen=True)
class FieldChange:
    """One changed field, before→after — the unit the evidence record is built from."""

    field: str
    before: object
    after: object


def _clean_name(value: str | None) -> str | None:
    """Strip a name; a blank string becomes `None` (a cleared name), so we never store ``""``."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def apply_entity_edit(entity: GraphEntity, patch: EntityEditPatch) -> GraphEntity:
    """Merge `patch` onto `entity` → the validated next-state, else raise `EntityEditInvalid`.

    Pure: no store, no side effects. Enforces the boundary rules a non-blank type + at least one
    canonical name; `properties` is replaced wholesale and left open (INV-4).
    """
    next_type = patch.type if patch.type is not None else entity.type
    if not next_type.strip():
        raise EntityEditInvalid("entity type must be a non-empty string")

    next_pl = _clean_name(
        patch.canonical_name_pl if patch.canonical_name_pl is not None else entity.canonical_name_pl
    )
    next_en = _clean_name(
        patch.canonical_name_en if patch.canonical_name_en is not None else entity.canonical_name_en
    )
    if not (next_pl or next_en):
        raise EntityEditInvalid("an entity must keep at least one canonical name")

    return entity.model_copy(
        update={
            "type": next_type.strip(),
            "canonical_name_pl": next_pl,
            "canonical_name_en": next_en,
            "aliases": list(patch.aliases) if patch.aliases is not None else entity.aliases,
            "properties": dict(patch.properties)
            if patch.properties is not None
            else entity.properties,
        }
    )


def diff_entity(before: GraphEntity, after: GraphEntity) -> list[FieldChange]:
    """The changed editable fields, before→after — the substrate for the before→after edit
    evidence (DM-S3a-2, INV-3 undo). An unchanged field is omitted; a no-op edit yields ``[]``."""
    return [
        FieldChange(field, getattr(before, field), getattr(after, field))
        for field in _EDITABLE_FIELDS
        if getattr(before, field) != getattr(after, field)
    ]
