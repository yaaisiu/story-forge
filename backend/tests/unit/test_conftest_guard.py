"""Unit tests for the test-DB safety guard in conftest.

The guard stands between a misconfigured `TEST_DATABASE_URL` and a
`DROP DATABASE ... WITH (FORCE)`; these tests pin the two refusal paths and the
happy path. Pure — no Postgres needed.
"""

from __future__ import annotations

import pytest
from sqlalchemy.engine import make_url

from story_forge.config import settings
from tests.conftest import _assert_disposable_test_db


def test_rejects_the_app_database() -> None:
    app_db = make_url(settings.database_url).database
    with pytest.raises(RuntimeError, match="app database"):
        _assert_disposable_test_db(app_db)


def test_rejects_a_name_without_test() -> None:
    with pytest.raises(RuntimeError, match="must contain 'test'"):
        _assert_disposable_test_db("production_db")


def test_rejects_empty_or_non_string() -> None:
    with pytest.raises(RuntimeError, match="no database name"):
        _assert_disposable_test_db(None)


def test_accepts_a_disposable_test_db() -> None:
    # Should not raise.
    _assert_disposable_test_db("story_forge_test")
