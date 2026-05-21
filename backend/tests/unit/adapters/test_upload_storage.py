"""Unit tests for the sandbox storage adapter (`adapters/upload_storage.py`).

Pure filesystem behaviour against tmp_path: least-privilege permissions on both
the sandbox directory and the stored file (spec §6.7 "no execution permissions").
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from story_forge.adapters.upload_storage import save_upload


def test_saves_named_by_uuid_with_owner_only_file(tmp_path: Path) -> None:
    sid = uuid4()
    dest = save_upload(tmp_path / "uploads", sid, ".txt", b"hello")
    assert dest.name == f"{sid}.txt"
    assert dest.read_bytes() == b"hello"
    assert dest.stat().st_mode & 0o777 == 0o600  # owner rw, no exec, no group/other


def test_sandbox_dir_is_owner_only(tmp_path: Path) -> None:
    save_upload(tmp_path / "uploads", uuid4(), ".txt", b"x")
    assert (tmp_path / "uploads").stat().st_mode & 0o777 == 0o700


def test_tightens_a_preexisting_loose_dir(tmp_path: Path) -> None:
    # A dir that already exists with loose perms must be locked down, not left as-is.
    loose = tmp_path / "uploads"
    loose.mkdir(mode=0o755)
    loose.chmod(0o755)  # mkdir mode is umask-masked; force the loose state explicitly
    save_upload(loose, uuid4(), ".txt", b"x")
    assert loose.stat().st_mode & 0o777 == 0o700
