"""Smoke test: GET /health returns {'status': 'ok'}.

Uses httpx.ASGITransport so we drive the FastAPI app directly without binding
a real socket — fast, deterministic, no port races in CI.
"""

from __future__ import annotations

import httpx

from story_forge.main import app


async def test_health_returns_ok() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
