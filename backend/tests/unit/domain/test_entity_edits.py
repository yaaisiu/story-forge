"""Unit tests for the pure entity-edit validation + field-merge (`domain/entity_edits.py`).

Pure functions: a committed `GraphEntity` + an `EntityEditPatch` in, the validated next-state
(or a typed `EntityEditInvalid`) out, and a before→after `FieldChange` list. No store, no I/O —
the altitude the project unit-tests hardest, and the first failing test of M4.S3a-be. The boundary
rules under test: a non-blank type + at least one canonical name (else 400-mapped reject), an
**open** `properties` map with **free keys** and **typed values** preserved (INV-4 / DM-S3a-5), and
a partial patch that merges (an unset field is unchanged; a no-op yields no changes).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from story_forge.domain.entity_edits import (
    EntityEditInvalid,
    EntityEditPatch,
    apply_entity_edit,
    diff_entity,
)
from story_forge.domain.graph import GraphEntity


def _entity(**overrides: object) -> GraphEntity:
    base: dict[str, object] = {
        "type": "Character",
        "canonical_name_pl": "Janek",
        "canonical_name_en": "Johnny",
        "aliases": ["młynarczyk"],
        "properties": {"age": 23, "role": "priestess"},
        "project_id": uuid4(),
    }
    base.update(overrides)
    return GraphEntity(**base)  # type: ignore[arg-type]


def test_partial_patch_merges_only_set_fields() -> None:
    entity = _entity()
    result = apply_entity_edit(entity, EntityEditPatch(type="Deity"))
    assert result.type == "Deity"
    # untouched fields carry over verbatim
    assert result.canonical_name_pl == "Janek"
    assert result.aliases == ["młynarczyk"]
    assert result.properties == {"age": 23, "role": "priestess"}
    # identity-bearing fields are preserved
    assert result.id == entity.id
    assert result.project_id == entity.project_id


def test_no_op_patch_returns_equivalent_entity_and_empty_diff() -> None:
    entity = _entity()
    result = apply_entity_edit(entity, EntityEditPatch())
    assert diff_entity(entity, result) == []


def test_blank_type_is_rejected() -> None:
    with pytest.raises(EntityEditInvalid):
        apply_entity_edit(_entity(), EntityEditPatch(type="   "))


def test_clearing_both_canonical_names_is_rejected() -> None:
    entity = _entity()
    with pytest.raises(EntityEditInvalid):
        apply_entity_edit(entity, EntityEditPatch(canonical_name_pl="", canonical_name_en="  "))


def test_one_canonical_name_may_be_cleared_to_none_if_the_other_remains() -> None:
    entity = _entity()
    result = apply_entity_edit(entity, EntityEditPatch(canonical_name_en=""))
    assert result.canonical_name_en is None
    assert result.canonical_name_pl == "Janek"


def test_properties_keys_are_free_and_values_keep_their_json_type() -> None:
    entity = _entity()
    new_props: dict[str, object] = {
        "married": True,  # bool preserved, not "True"
        "children": 3,  # int preserved, not "3"
        "home": {"village": "Oakhaven"},  # nested object preserved
        "any-free-key": "ok",  # INV-4: no fixed key schema
    }
    result = apply_entity_edit(entity, EntityEditPatch(properties=new_props))
    assert result.properties == new_props
    assert result.properties["married"] is True
    assert result.properties["children"] == 3


def test_non_object_properties_rejected_at_the_request_boundary() -> None:
    # A non-object `properties` is a request-shape error caught by pydantic (→422),
    # not a domain `EntityEditInvalid` — the boundary owns object-ness, the domain owns
    # the semantic rules (non-blank name/type).
    with pytest.raises(ValueError):
        EntityEditPatch(properties=["not", "an", "object"])  # type: ignore[arg-type]


def test_diff_reports_each_changed_field_before_and_after() -> None:
    entity = _entity()
    result = apply_entity_edit(entity, EntityEditPatch(type="Deity", aliases=["the miller"]))
    changes = {c.field: (c.before, c.after) for c in diff_entity(entity, result)}
    assert changes["type"] == ("Character", "Deity")
    assert changes["aliases"] == (["młynarczyk"], ["the miller"])
    # unchanged fields are not reported
    assert "canonical_name_pl" not in changes
    assert "properties" not in changes
