"""Unit tests for connect() transient-connection retry behaviour.

These tests mock psycopg.connect so they run without Docker. The invariant:
connect() should wait out a not-yet-ready PostgreSQL (connection refused) by
retrying OperationalErrors with backoff, while non-connection errors and
exhausted retries still surface.
"""

from __future__ import annotations

from typing import Any

import psycopg
import pytest

_CONNECTION_REFUSED = "connection refused"
_SYNTAX_ERROR = "syntax error"


class _FakeConn:
    def execute(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None


def test_connect_retries_transient_operational_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A connection refused is retried until PostgreSQL becomes reachable."""
    from news_dashboard import db

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("DB_CONNECT_RETRY_DELAY_SECONDS", "0")
    monkeypatch.setenv("DB_CONNECT_MAX_ATTEMPTS", "5")

    attempts = {"n": 0}

    def fake_connect(dsn: str, row_factory: Any = None) -> _FakeConn:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise psycopg.OperationalError(_CONNECTION_REFUSED)
        return _FakeConn()

    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("news_dashboard.db.psycopg.connect", fake_connect)
    monkeypatch.setattr("news_dashboard.db.time.sleep", fake_sleep)

    with db.connect() as conn:
        assert isinstance(conn, _FakeConn)

    assert attempts["n"] == 3
    assert sleeps == [0.0, 0.0]


def test_connect_gives_up_after_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once attempts are exhausted the original OperationalError is re-raised."""
    from news_dashboard import db

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("DB_CONNECT_RETRY_DELAY_SECONDS", "0")
    monkeypatch.setenv("DB_CONNECT_MAX_ATTEMPTS", "3")

    attempts = {"n": 0}

    def fake_connect(dsn: str, row_factory: Any = None) -> _FakeConn:
        attempts["n"] += 1
        raise psycopg.OperationalError(_CONNECTION_REFUSED)

    def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr("news_dashboard.db.psycopg.connect", fake_connect)
    monkeypatch.setattr("news_dashboard.db.time.sleep", fake_sleep)

    with pytest.raises(psycopg.OperationalError, match=_CONNECTION_REFUSED), db.connect():
        pass

    assert attempts["n"] == 3


def test_connect_does_not_retry_non_connection_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Programming/other errors must surface immediately without retrying."""
    from news_dashboard import db

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("DB_CONNECT_RETRY_DELAY_SECONDS", "0")
    monkeypatch.setenv("DB_CONNECT_MAX_ATTEMPTS", "5")

    attempts = {"n": 0}

    def fake_connect(dsn: str, row_factory: Any = None) -> _FakeConn:
        attempts["n"] += 1
        raise psycopg.ProgrammingError(_SYNTAX_ERROR)

    def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr("news_dashboard.db.psycopg.connect", fake_connect)
    monkeypatch.setattr("news_dashboard.db.time.sleep", fake_sleep)

    with pytest.raises(psycopg.ProgrammingError, match=_SYNTAX_ERROR), db.connect():
        pass

    assert attempts["n"] == 1
