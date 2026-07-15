"""Integration tests for the M4.S3a edit routes — `PATCH /stories/{id}/entities/{eid}`,
`POST /stories/{id}/relations`, `DELETE /stories/{id}/relations/{edge_id}`.

Like `test_entities_search`, these exercise the HTTP contract against the throwaway test DB (a
real story row, so the route resolves the §6.4 tenancy key) with a **stub** `EntityEditService`
injected via override — the service's real behaviour is covered by `test_entity_edit`. Here we
prove the route resolves story→project, maps each domain exception to its declared status, and
projects the response shape (incl. the `merged_into_existing` collision flag and the 204 on delete).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from neo4j.exceptions import ServiceUnavailable

from story_forge.adapters.db import get_connection
from story_forge.adapters.postgres_repo import insert_project, insert_story
from story_forge.agents.entity_edit import (
    DeleteSummary,
    EntityNotFound,
    MergeSummary,
    NothingToUndo,
    PredicateRenameSummary,
    RelationEdgeNotFound,
    RelationEditResult,
    SelfMergeError,
    TypeRelabelSummary,
    UndoConflict,
    UndoResult,
)
from story_forge.api.stories import get_entity_edit
from story_forge.domain.entity_edits import EntityEditInvalid, EntityEditPatch
from story_forge.domain.entity_merge import EntityMergeInvalid
from story_forge.domain.graph import GraphEntity
from story_forge.domain.models import Project, Story
from story_forge.main import app

pytestmark = pytest.mark.integration


class _StubEdit:
    """A configurable `EntityEditService` double: returns a canned value or raises a set error."""

    def __init__(
        self,
        *,
        entity: GraphEntity | None = None,
        relation: RelationEditResult | None = None,
        merge: MergeSummary | None = None,
        delete: DeleteSummary | None = None,
        undo: UndoResult | None = None,
        predicate_rename: PredicateRenameSummary | None = None,
        type_relabel: TypeRelabelSummary | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._entity = entity
        self._relation = relation
        self._merge = merge
        self._delete = delete
        self._undo = undo
        self._predicate_rename = predicate_rename
        self._type_relabel = type_relabel
        self._raises = raises
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def edit_entity(
        self, project_id: UUID, entity_id: UUID, patch: EntityEditPatch
    ) -> GraphEntity:
        self.calls.append(("edit_entity", (project_id, entity_id)))
        if self._raises is not None:
            raise self._raises
        assert self._entity is not None
        return self._entity

    async def add_relation(
        self, project_id: UUID, subject_id: UUID, predicate: str, object_id: UUID
    ) -> RelationEditResult:
        self.calls.append(("add_relation", (project_id, subject_id, predicate, object_id)))
        if self._raises is not None:
            raise self._raises
        assert self._relation is not None
        return self._relation

    async def remove_relation(self, project_id: UUID, edge_id: UUID) -> None:
        self.calls.append(("remove_relation", (project_id, edge_id)))
        if self._raises is not None:
            raise self._raises

    async def retarget_relation(
        self,
        project_id: UUID,
        edge_id: UUID,
        *,
        predicate: str | None = None,
        subject_id: UUID | None = None,
        object_id: UUID | None = None,
    ) -> RelationEditResult:
        self.calls.append(
            ("retarget_relation", (project_id, edge_id, predicate, subject_id, object_id))
        )
        if self._raises is not None:
            raise self._raises
        assert self._relation is not None
        return self._relation

    async def merge_entities(
        self,
        project_id: UUID,
        absorbed_id: UUID,
        target_id: UUID,
        resolved_properties: dict[str, object],
    ) -> MergeSummary:
        self.calls.append(("merge_entities", (project_id, absorbed_id, target_id)))
        if self._raises is not None:
            raise self._raises
        assert self._merge is not None
        return self._merge

    async def delete_entity(self, project_id: UUID, entity_id: UUID) -> DeleteSummary:
        self.calls.append(("delete_entity", (project_id, entity_id)))
        if self._raises is not None:
            raise self._raises
        assert self._delete is not None
        return self._delete

    async def undo_last(self, project_id: UUID, *, preview_only: bool = False) -> UndoResult:
        self.calls.append(("undo_last", (project_id, preview_only)))
        if self._raises is not None:
            raise self._raises
        assert self._undo is not None
        return self._undo

    async def rename_predicate(
        self, project_id: UUID, from_predicate: str, to_predicate: str
    ) -> PredicateRenameSummary:
        self.calls.append(("rename_predicate", (project_id, from_predicate, to_predicate)))
        if self._raises is not None:
            raise self._raises
        assert self._predicate_rename is not None
        return self._predicate_rename

    async def relabel_entity_type(
        self, project_id: UUID, from_type: str, to_type: str
    ) -> TypeRelabelSummary:
        self.calls.append(("relabel_entity_type", (project_id, from_type, to_type)))
        if self._raises is not None:
            raise self._raises
        assert self._type_relabel is not None
        return self._type_relabel


async def _make_story(conn: psycopg.AsyncConnection) -> Story:
    project = Project(name="t", language="pl")
    story = Story(project_id=project.id, title="t", raw_text="x")
    await insert_project(conn, project)
    await insert_story(conn, story)
    return story


@pytest_asyncio.fixture
async def make_client(db_conn: psycopg.AsyncConnection) -> AsyncIterator[object]:
    async def _override() -> AsyncIterator[psycopg.AsyncConnection]:
        yield db_conn

    app.dependency_overrides[get_connection] = _override
    clients: list[AsyncClient] = []

    def _factory(service: object) -> AsyncClient:
        app.dependency_overrides[get_entity_edit] = lambda: service
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clients.append(client)
        return client

    yield _factory
    for client in clients:
        await client.aclose()
    app.dependency_overrides.clear()


async def test_patch_entity_returns_edited_display_fields(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    edited = GraphEntity(
        type="Deity",
        canonical_name_pl="Mokosz",
        aliases=["the mother"],
        properties={"role": "priestess"},
        project_id=story.project_id,
    )
    service = _StubEdit(entity=edited)
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.patch(
        f"/stories/{story.id}/entities/{edited.id}",
        json={"type": "Deity", "properties": {"role": "priestess"}},
    )

    assert resp.status_code == 200, resp.text
    assert service.calls[0] == ("edit_entity", (story.project_id, edited.id))
    body = resp.json()
    assert body == {
        "entity_id": str(edited.id),
        "canonical_name": "Mokosz",  # project language pl
        "type": "Deity",
        "aliases": ["the mother"],
        "properties": {"role": "priestess"},
    }


async def test_patch_entity_invalid_edit_is_400(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(raises=EntityEditInvalid("entity type must be a non-empty string"))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.patch(f"/stories/{story.id}/entities/{uuid4()}", json={"type": "  "})
    assert resp.status_code == 400, resp.text


async def test_patch_entity_unknown_entity_is_404(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(raises=EntityNotFound("nope"))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.patch(f"/stories/{story.id}/entities/{uuid4()}", json={"type": "Deity"})
    assert resp.status_code == 404, resp.text


async def test_patch_entity_unknown_story_is_404(make_client: object) -> None:
    service = _StubEdit(entity=None)
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    resp = await client.patch(f"/stories/{uuid4()}/entities/{uuid4()}", json={"type": "Deity"})
    assert resp.status_code == 404, resp.text


async def test_post_relation_returns_edge_and_collision_flag(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    edge_id = uuid4()
    subject, object_ = uuid4(), uuid4()
    service = _StubEdit(relation=RelationEditResult(edge_id=edge_id, merged_into_existing=True))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(
        f"/stories/{story.id}/relations",
        json={"subject_id": str(subject), "predicate": "LOVES", "object_id": str(object_)},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"edge_id": str(edge_id), "merged_into_existing": True}
    assert service.calls[0] == ("add_relation", (story.project_id, subject, "LOVES", object_))


async def test_post_relation_strips_predicate_whitespace(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # A padded predicate is stripped at the boundary, so the deterministic edge id (and Neo4j
    # relationship type) don't fork on incidental whitespace.
    story = await _make_story(db_conn)
    subject, object_ = uuid4(), uuid4()
    service = _StubEdit(relation=RelationEditResult(edge_id=uuid4(), merged_into_existing=False))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(
        f"/stories/{story.id}/relations",
        json={"subject_id": str(subject), "predicate": "  LOVES  ", "object_id": str(object_)},
    )

    assert resp.status_code == 200, resp.text
    assert service.calls[0] == ("add_relation", (story.project_id, subject, "LOVES", object_))


async def test_post_relation_missing_endpoint_is_404(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(raises=EntityNotFound("gone"))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(
        f"/stories/{story.id}/relations",
        json={"subject_id": str(uuid4()), "predicate": "LOVES", "object_id": str(uuid4())},
    )
    assert resp.status_code == 404, resp.text


async def test_post_relation_blank_predicate_is_422(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # A blank predicate is a request-shape error (422) at the boundary, not a 500 from the
    # GraphRelation type validator deeper in. The service is never reached.
    story = await _make_story(db_conn)
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(
        f"/stories/{story.id}/relations",
        json={"subject_id": str(uuid4()), "predicate": "  ", "object_id": str(uuid4())},
    )
    assert resp.status_code == 422, resp.text
    assert service.calls == []  # rejected before dispatch


async def test_delete_relation_returns_204(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    edge_id = uuid4()
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.delete(f"/stories/{story.id}/relations/{edge_id}")

    assert resp.status_code == 204, resp.text
    assert service.calls[0] == ("remove_relation", (story.project_id, edge_id))


async def test_delete_unknown_relation_is_404(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(raises=RelationEdgeNotFound("nope"))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.delete(f"/stories/{story.id}/relations/{uuid4()}")
    assert resp.status_code == 404, resp.text


# --- retarget: PATCH /relations/{edge_id} (Graph-quality S5b-be) ------------


async def test_patch_relation_returns_the_new_edge_and_collision_flag(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    edge_id, new_edge_id = uuid4(), uuid4()
    service = _StubEdit(relation=RelationEditResult(edge_id=new_edge_id, merged_into_existing=True))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.patch(
        f"/stories/{story.id}/relations/{edge_id}", json={"predicate": "ON_SHIP"}
    )

    assert resp.status_code == 200, resp.text
    # the returned id is the NEW (post-re-key) edge id; the fold surfaces as merged_into_existing
    assert resp.json() == {"edge_id": str(new_edge_id), "merged_into_existing": True}
    assert service.calls[0] == (
        "retarget_relation",
        (story.project_id, edge_id, "ON_SHIP", None, None),
    )


async def test_patch_relation_strips_predicate_whitespace(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    edge_id = uuid4()
    service = _StubEdit(relation=RelationEditResult(edge_id=uuid4(), merged_into_existing=False))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.patch(
        f"/stories/{story.id}/relations/{edge_id}", json={"predicate": "  ON_SHIP  "}
    )

    assert resp.status_code == 200, resp.text
    assert service.calls[0][1][2] == "ON_SHIP"  # stripped before dispatch


async def test_patch_relation_re_targets_an_endpoint(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    edge_id, new_obj = uuid4(), uuid4()
    service = _StubEdit(relation=RelationEditResult(edge_id=uuid4(), merged_into_existing=False))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.patch(
        f"/stories/{story.id}/relations/{edge_id}", json={"object_id": str(new_obj)}
    )

    assert resp.status_code == 200, resp.text
    assert service.calls[0] == (
        "retarget_relation",
        (story.project_id, edge_id, None, None, new_obj),
    )


async def test_patch_relation_unknown_edge_is_404(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(raises=RelationEdgeNotFound("nope"))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.patch(
        f"/stories/{story.id}/relations/{uuid4()}", json={"predicate": "ON_SHIP"}
    )
    assert resp.status_code == 404, resp.text


async def test_patch_relation_missing_new_endpoint_is_404(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(raises=EntityNotFound("gone"))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.patch(
        f"/stories/{story.id}/relations/{uuid4()}", json={"object_id": str(uuid4())}
    )
    assert resp.status_code == 404, resp.text


async def test_patch_relation_empty_body_is_422(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    # No field supplied → nothing to change → a request-validation 422 at the boundary; the service
    # is never reached (the ≥1-field model validator, kept out of `responses=` per the 422-trap).
    story = await _make_story(db_conn)
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.patch(f"/stories/{story.id}/relations/{uuid4()}", json={})
    assert resp.status_code == 422, resp.text
    assert service.calls == []


async def test_patch_relation_unknown_story_is_404(make_client: object) -> None:
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    resp = await client.patch(f"/stories/{uuid4()}/relations/{uuid4()}", json={"predicate": "X"})
    assert resp.status_code == 404, resp.text


# --- merge (M4.S3b) --------------------------------------------------------


async def test_merge_returns_summary(make_client: object, db_conn: psycopg.AsyncConnection) -> None:
    story = await _make_story(db_conn)
    absorbed, survivor = uuid4(), uuid4()
    service = _StubEdit(
        merge=MergeSummary(
            survivor_entity_id=survivor,
            repointed_count=2,
            folded_count=1,
            self_loops_dropped=0,
            mentions_repointed=3,
        )
    )
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(
        f"/stories/{story.id}/entities/{absorbed}/merge",
        json={"target_entity_id": str(survivor), "resolved_properties": {"age": 41}},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "survivor_entity_id": str(survivor),
        "repointed_count": 2,
        "folded_count": 1,
        "self_loops_dropped": 0,
        "mentions_repointed": 3,
    }
    assert service.calls[0] == ("merge_entities", (story.project_id, absorbed, survivor))


async def test_merge_self_is_409(make_client: object, db_conn: psycopg.AsyncConnection) -> None:
    story = await _make_story(db_conn)
    eid = uuid4()
    service = _StubEdit(raises=SelfMergeError(str(eid)))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(
        f"/stories/{story.id}/entities/{eid}/merge",
        json={"target_entity_id": str(eid)},
    )
    assert resp.status_code == 409, resp.text


async def test_merge_unknown_entity_is_404(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(raises=EntityNotFound("gone"))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(
        f"/stories/{story.id}/entities/{uuid4()}/merge",
        json={"target_entity_id": str(uuid4())},
    )
    assert resp.status_code == 404, resp.text


async def test_merge_unresolved_conflict_is_400(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(raises=EntityMergeInvalid("unresolved property conflicts: ['age']"))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(
        f"/stories/{story.id}/entities/{uuid4()}/merge",
        json={"target_entity_id": str(uuid4())},
    )
    assert resp.status_code == 400, resp.text


async def test_merge_unknown_story_is_404(make_client: object) -> None:
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    resp = await client.post(
        f"/stories/{uuid4()}/entities/{uuid4()}/merge",
        json={"target_entity_id": str(uuid4())},
    )
    assert resp.status_code == 404, resp.text


# --- delete + undo (M4.S3b-be2) --------------------------------------------


async def test_delete_entity_is_204(make_client: object, db_conn: psycopg.AsyncConnection) -> None:
    story = await _make_story(db_conn)
    eid = uuid4()
    service = _StubEdit(
        delete=DeleteSummary(
            deleted_entity_id=eid, edges_removed=2, mentions_removed=1, description="deleted X"
        )
    )
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.delete(f"/stories/{story.id}/entities/{eid}")

    assert resp.status_code == 204, resp.text
    assert service.calls[0] == ("delete_entity", (story.project_id, eid))


async def test_delete_unknown_entity_is_404(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(raises=EntityNotFound("gone"))
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    resp = await client.delete(f"/stories/{story.id}/entities/{uuid4()}")
    assert resp.status_code == 404, resp.text


async def test_delete_unknown_story_is_404(make_client: object) -> None:
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    resp = await client.delete(f"/stories/{uuid4()}/entities/{uuid4()}")
    assert resp.status_code == 404, resp.text


async def test_undo_returns_what_was_reversed(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(
        undo=UndoResult(description="merged Broniek into Bronisław", op_kind="merge", applied=True)
    )
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(f"/stories/{story.id}/graph-edits/undo")

    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "description": "merged Broniek into Bronisław",
        "op_kind": "merge",
        "applied": True,
    }
    assert service.calls[0] == ("undo_last", (story.project_id, False))


async def test_undo_preview_passes_the_flag(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(undo=UndoResult(description="deleted X", op_kind="delete", applied=False))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(f"/stories/{story.id}/graph-edits/undo?preview=true")

    assert resp.status_code == 200, resp.text
    assert resp.json()["applied"] is False
    assert service.calls[0] == ("undo_last", (story.project_id, True))


async def test_undo_nothing_to_undo_is_404(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(raises=NothingToUndo(str(story.project_id)))
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    resp = await client.post(f"/stories/{story.id}/graph-edits/undo")
    assert resp.status_code == 404, resp.text


async def test_undo_drift_is_409(make_client: object, db_conn: psycopg.AsyncConnection) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(raises=UndoConflict("the entity was edited since"))
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    resp = await client.post(f"/stories/{story.id}/graph-edits/undo")
    assert resp.status_code == 409, resp.text


async def test_undo_unknown_story_is_404(make_client: object) -> None:
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    resp = await client.post(f"/stories/{uuid4()}/graph-edits/undo")
    assert resp.status_code == 404, resp.text


# --- name normalisation apply (S6a-2) --------------------------------------


async def test_rename_predicate_returns_the_counts(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(predicate_rename=PredicateRenameSummary(renamed_count=5, folded_count=2))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(
        f"/stories/{story.id}/label-vocabulary/rename",
        json={"surface": "predicate", "from_label": "PASSENGER_ON", "to_label": "ON_SHIP"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"surface": "predicate", "renamed_count": 5, "folded_count": 2}
    assert service.calls[0] == (
        "rename_predicate",
        (story.project_id, "PASSENGER_ON", "ON_SHIP"),
    )


async def test_relabel_type_returns_the_count_with_zero_folds(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(type_relabel=TypeRelabelSummary(relabelled_count=3))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(
        f"/stories/{story.id}/label-vocabulary/rename",
        json={"surface": "type", "from_label": "Person", "to_label": "PERSON"},
    )

    assert resp.status_code == 200, resp.text
    # a type relabel never merges nodes, so folded_count is always 0
    assert resp.json() == {"surface": "type", "renamed_count": 3, "folded_count": 0}
    assert service.calls[0] == ("relabel_entity_type", (story.project_id, "Person", "PERSON"))


async def test_rename_strips_label_whitespace(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(predicate_rename=PredicateRenameSummary(renamed_count=1, folded_count=0))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(
        f"/stories/{story.id}/label-vocabulary/rename",
        json={"surface": "predicate", "from_label": "  PASSENGER_ON ", "to_label": " ON_SHIP "},
    )

    assert resp.status_code == 200, resp.text
    assert service.calls[0] == ("rename_predicate", (story.project_id, "PASSENGER_ON", "ON_SHIP"))


async def test_rename_blank_label_is_422(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(
        f"/stories/{story.id}/label-vocabulary/rename",
        json={"surface": "type", "from_label": "Person", "to_label": "   "},
    )

    assert resp.status_code == 422, resp.text
    assert service.calls == []  # rejected before reaching the service


async def test_rename_unknown_story_is_404(make_client: object) -> None:
    service = _StubEdit()
    client: AsyncClient = make_client(service)  # type: ignore[operator]
    resp = await client.post(
        f"/stories/{uuid4()}/label-vocabulary/rename",
        json={"surface": "predicate", "from_label": "A", "to_label": "B"},
    )
    assert resp.status_code == 404, resp.text


async def test_rename_store_outage_is_503(
    make_client: object, db_conn: psycopg.AsyncConnection
) -> None:
    story = await _make_story(db_conn)
    service = _StubEdit(raises=ServiceUnavailable("neo4j down"))
    client: AsyncClient = make_client(service)  # type: ignore[operator]

    resp = await client.post(
        f"/stories/{story.id}/label-vocabulary/rename",
        json={"surface": "predicate", "from_label": "A", "to_label": "B"},
    )

    assert resp.status_code == 503, resp.text
