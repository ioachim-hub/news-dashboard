"""Tests for the ENABLE_API_DOCS gate on the interactive API docs."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from news_dashboard.main import app


def _client() -> TestClient:
    app.dependency_overrides.clear()
    return TestClient(app, follow_redirects=False)


@pytest.mark.smoke
@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_not_served_when_disabled(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    monkeypatch.delenv("ENABLE_API_DOCS", raising=False)
    resp = _client().get(path)
    assert resp.status_code == 404


@pytest.mark.smoke
@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_served_when_enabled(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    monkeypatch.setenv("ENABLE_API_DOCS", "true")
    resp = _client().get(path)
    assert resp.status_code == 200


@pytest.mark.smoke
@pytest.mark.parametrize("flag_value", ["0", "false", "no", "off", ""])
def test_docs_disabled_flag_values(monkeypatch: pytest.MonkeyPatch, flag_value: str) -> None:
    monkeypatch.setenv("ENABLE_API_DOCS", flag_value)
    resp = _client().get("/docs")
    assert resp.status_code == 404
