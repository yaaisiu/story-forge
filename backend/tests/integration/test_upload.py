"""Integration tests for `POST /stories/upload` (spec §7, step 1).

These exercise the whole route against the throwaway test DB: validation,
sandbox file write (to a tmp dir), parsing, language detection, and persistence
of a `Project` (carrying the detected language) + a `Story` (carrying raw text).

The `get_connection` dependency is overridden to hand the route the same
transaction-isolated `db_conn` the test reads back from, so writes are visible
within the request and rolled back on teardown.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from docx import Document
from httpx import ASGITransport, AsyncClient

from story_forge.adapters.db import get_connection
from story_forge.adapters.postgres_repo import (
    get_project,
    get_story,
    list_stories_for_project,
)
from story_forge.config import settings
from story_forge.main import app

pytestmark = pytest.mark.integration

_EN_TEXT = (
    "John walked into the old mill and looked around. It was dark, quiet, and "
    "smelled of damp wood. Somewhere above him a bat flew past in the rafters."
)
_PL_TEXT = (
    "Janek wszedł do starego młyna i rozejrzał się dookoła. Było ciemno, cicho "
    "i pachniało wilgotnym drewnem. Gdzieś w górze przeleciał spłoszony nietoperz."
)


def _docx_bytes(text: str) -> bytes:
    buf = BytesIO()
    doc = Document()
    for block in text.split("\n\n"):
        doc.add_paragraph(block)
    doc.save(buf)
    return buf.getvalue()


_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest_asyncio.fixture
async def client(
    db_conn: psycopg.AsyncConnection,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    """An HTTP client whose upload route writes to a tmp sandbox and shares the
    test transaction, so persisted rows are visible to the test and rolled back."""
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")

    async def _override() -> AsyncIterator[psycopg.AsyncConnection]:
        yield db_conn

    app.dependency_overrides[get_connection] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def test_upload_txt_creates_project_and_story(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    resp = await client.post(
        "/stories/upload",
        files={"file": ("the-mill.txt", _EN_TEXT.encode("utf-8"), "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["language"] == "en"
    assert body["title"] == "the-mill"
    # Raw text echoed back so the frontend manual-mode editor has the source to
    # edit (spec §7 step 2 "user accepts/edits"). The browser doesn't easily
    # parse .docx itself, so the response is the cheapest place to surface it.
    assert body["raw_text"].startswith("John walked into the old mill")

    story = await get_story(db_conn, body["story_id"])
    project = await get_project(db_conn, body["project_id"])
    assert story is not None and project is not None
    assert story.raw_text.startswith("John walked into the old mill")
    assert story.project_id == project.id
    assert project.language == "en"
    assert project.name == "the-mill"


async def test_upload_docx_detects_polish(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    resp = await client.post(
        "/stories/upload",
        files={"file": ("opowiesc.docx", _docx_bytes(_PL_TEXT), _DOCX_MIME)},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["language"] == "pl"

    story = await get_story(db_conn, body["story_id"])
    assert story is not None
    assert "młyna" in story.raw_text


async def test_upload_writes_original_to_sandbox(
    client: AsyncClient, db_conn: psycopg.AsyncConnection, tmp_path: Path
) -> None:
    resp = await client.post(
        "/stories/upload",
        files={"file": ("story.txt", _EN_TEXT.encode("utf-8"), "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    saved = tmp_path / "uploads" / f"{resp.json()['story_id']}.txt"
    assert saved.exists()
    assert saved.read_bytes() == _EN_TEXT.encode("utf-8")
    # No execute bits — spec §6.7 "no execution permissions".
    assert saved.stat().st_mode & 0o111 == 0


async def test_rejects_unsupported_extension(client: AsyncClient) -> None:
    resp = await client.post(
        "/stories/upload",
        files={"file": ("malware.exe", b"MZ...", "application/octet-stream")},
    )
    assert resp.status_code == 415


async def test_rejects_mismatched_content_type(client: AsyncClient) -> None:
    resp = await client.post(
        "/stories/upload",
        files={"file": ("story.txt", _EN_TEXT.encode("utf-8"), "image/png")},
    )
    assert resp.status_code == 415


async def test_accepts_content_type_with_charset_parameter(client: AsyncClient) -> None:
    # Browsers send e.g. "text/plain; charset=utf-8"; the parameter must not 415 it.
    resp = await client.post(
        "/stories/upload",
        files={"file": ("story.txt", _EN_TEXT.encode("utf-8"), "text/plain; charset=utf-8")},
    )
    assert resp.status_code == 201, resp.text


async def test_rejects_oversize_file(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from story_forge.api import stories

    monkeypatch.setattr(stories, "MAX_UPLOAD_BYTES", 16)
    resp = await client.post(
        "/stories/upload",
        files={"file": ("big.txt", b"x" * 17, "text/plain")},
    )
    assert resp.status_code == 413


async def test_rejects_corrupt_docx(client: AsyncClient) -> None:
    resp = await client.post(
        "/stories/upload",
        files={"file": ("broken.docx", b"not a real docx", _DOCX_MIME)},
    )
    assert resp.status_code == 400


async def test_upload_into_existing_project_reuses_it(
    client: AsyncClient, db_conn: psycopg.AsyncConnection
) -> None:
    # First upload mints a new (English) project, exactly as today.
    first = await client.post(
        "/stories/upload",
        files={"file": ("a.txt", _EN_TEXT.encode("utf-8"), "text/plain")},
    )
    assert first.status_code == 201, first.text
    project_id = first.json()["project_id"]

    # A second upload targeting that project adds a story to it — even Polish text lands under
    # the project's existing language (multi-story narrows to one shared project, DM-MS-3).
    second = await client.post(
        "/stories/upload",
        params={"project_id": project_id},
        files={"file": ("b.txt", _PL_TEXT.encode("utf-8"), "text/plain")},
    )
    assert second.status_code == 201, second.text
    body = second.json()
    assert body["project_id"] == project_id  # same project, not a freshly minted one
    assert body["language"] == "en"  # the project's language governs, not the upload's
    assert body["story_id"] != first.json()["story_id"]

    stories = await list_stories_for_project(db_conn, UUID(project_id))
    assert len(stories) == 2


async def test_upload_with_dangling_project_id_404(client: AsyncClient) -> None:
    resp = await client.post(
        "/stories/upload",
        params={"project_id": str(uuid4())},
        files={"file": ("a.txt", _EN_TEXT.encode("utf-8"), "text/plain")},
    )
    assert resp.status_code == 404, resp.text
