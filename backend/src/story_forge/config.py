"""Application settings loaded from `backend/.env` via pydantic-settings.

The repo uses a split-env layout (spec §6.7): infra credentials live in
the repo-root `.env` (read only by docker-compose), and the backend reads
only what it actually needs from `backend/.env`. `extra="ignore"` makes us
tolerant of unrelated keys leaking in via process env without crashing.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Postgres ---
    database_url: str = Field(
        default="postgresql+psycopg://storyforge:replace-me@127.0.0.1:5432/storyforge",
        description="SQLAlchemy URL using psycopg 3 sync driver (used by Alembic).",
    )
    test_database_url: str = Field(
        default="postgresql+psycopg://storyforge:replace-me@127.0.0.1:5432/story_forge_test",
        description=(
            "URL of the throwaway integration-test database. The pytest session "
            "fixture creates this DB, runs `alembic upgrade head`, then drops it; "
            "it must name a DB distinct from `database_url` so dev data is never "
            "touched. Default password is a non-functional placeholder — the real "
            "value comes from backend/.env (TEST_DATABASE_URL) or CI env."
        ),
    )

    # --- Neo4j ---
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "replace-me"

    # --- Local LLM ---
    ollama_host: str = "http://127.0.0.1:11434"

    # --- Cloud LLM keys (all optional — populated in later milestones) ---
    ollama_cloud_host: str = Field(
        default="https://ollama.com",
        description="Ollama Cloud endpoint — the default chunking tier on a GPU-less host.",
    )
    ollama_cloud_api_key: str = ""

    # --- Chunking (ingest step 2, spec §6.5/§7) ---
    chunking_model: str = Field(
        default="gpt-oss:20b-cloud",
        description=(
            "Ollama model the ChunkingAgent calls (cloud_free default tier). The 20b "
            "variant sits on Ollama Cloud's Low Usage tier (lighter quota than 120b) "
            "and is plenty for chunking — a structural JSON task, not deep PL prose."
        ),
    )
    chunking_local_max_words: int = Field(
        default=4000,
        description=(
            "Word ceiling below which chunking may use the local_small tier — only "
            "meaningful when a GPU-backed local Ollama is configured; on a GPU-less "
            "host the agent uses cloud_free regardless (spec §6.5)."
        ),
    )
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    xai_api_key: str = ""
    openrouter_api_key: str = ""

    # --- Uploads ---
    upload_dir: Path = Field(
        default=Path("var/uploads"),
        description=(
            "Sandbox directory for original uploaded files (spec §6.7). Resolved "
            "relative to the process working directory; created on first upload "
            "with no-exec permissions. Stored outside the package, gitignored."
        ),
    )

    # --- Backend behaviour ---
    log_level: str = "INFO"
    # Both `localhost` and `127.0.0.1` for each dev port — Vite binds the dev
    # server to 127.0.0.1 by default, and the browser's Origin header reflects
    # the URL bar (not DNS resolution), so a contributor typing either form
    # must work. Same loopback socket, same trust boundary. Spec §6.7.
    backend_cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """`BACKEND_CORS_ORIGINS` is a comma-separated string; expand to a list."""
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]


settings = Settings()
