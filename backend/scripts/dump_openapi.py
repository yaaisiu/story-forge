"""Dump the FastAPI app's OpenAPI schema to a file.

Used by the frontend's typed-client codegen (`frontend/src/lib/api/schema.d.ts`
is generated from this output by `openapi-typescript`). Kept as a one-shot script
rather than a runtime endpoint so the frontend build stays hermetic — the client
is regenerated only when a human runs the two-step ritual:

    # 1) from repo root: refresh frontend/openapi.json
    uv --project backend run python backend/scripts/dump_openapi.py \\
        frontend/openapi.json
    # 2) from frontend/: regenerate the typed client
    npm run generate:api

The committed `frontend/openapi.json` is the source of truth a PR diff makes
visible — any backend schema change shows up as a diff there before it lands.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from story_forge.main import app


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: dump_openapi.py <output_path>", file=sys.stderr)
        return 2
    out = Path(argv[1])
    out.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
