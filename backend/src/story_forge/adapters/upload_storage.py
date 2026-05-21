"""Sandboxed storage for original uploaded files (spec §6.7).

Uploads are written to a dedicated directory, named by the owning story's UUID
(never the user-supplied filename, so a crafted name can't traverse paths), with
no execute permissions. The parsed text lives in Postgres; this keeps the raw
original for re-processing or audit without trusting it as code.
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID


def save_upload(upload_dir: Path, story_id: UUID, suffix: str, data: bytes) -> Path:
    """Write `data` to `upload_dir/<story_id><suffix>`; return the path.

    The directory is locked to 0o700 and the file written 0o600 — owner
    read/write only, no execute bit for anyone. The chmod is explicit because
    `mkdir(mode=…)` is masked by umask and ignored entirely when the directory
    already exists, so it cannot be relied on to enforce least privilege.
    """
    upload_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(upload_dir, 0o700)
    dest = upload_dir / f"{story_id}{suffix}"
    dest.write_bytes(data)
    os.chmod(dest, 0o600)
    return dest
