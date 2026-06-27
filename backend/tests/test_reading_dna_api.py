from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from news_dashboard.auth import require_auth
from news_dashboard.db import connect, init_db
from news_dashboard.main import app

pytestmark = pytest.mark.postgres


def _setup_db(monkeypatch: Any, pg_url: str) -> str:
    monkeypatch.setenv("DATABASE_URL", pg_url)
    init_db(database_url=pg_url)
    return pg_url


def _make_user(db_path: str, username: str) -> int:
    with connect(db_path) as conn:
        row = conn.execute(
            "INSERT INTO users(username, password_hash) VALUES (%s, %s) RETURNING id",
            (username, "test-hash"),
        ).fetchone()
    assert row is not None
    return int(row["id"])


def _insert_article(db_path: str, slug: str, category: str) -> int:
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO sources(slug, name, url, category, kind, priority, enabled)
            VALUES (%s, %s, %s, %s, 'rss_feed', 50, TRUE)
            ON CONFLICT(slug) DO NOTHING
            """,
            (slug, slug.title(), f"https://example.com/{slug}.xml", category),
        )
        row = conn.execute(
            """
            INSERT INTO articles(
              url, canonical_url, title, source_slug, source_name,
              category, kind, state, discovered_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'rss_feed', 'today', %s)
            RETURNING id
            """,
            (
                f"https://example.com/{slug}/article",
                f"https://example.com/{slug}/article",
                f"{category.title()} Article",
                slug,
                slug.title(),
                category,
                "2026-06-21T10:00:00+00:00",
            ),
        ).fetchone()
    assert row is not None
    return int(row["id"])


def _client_for(user_id: int) -> TestClient:
    app.dependency_overrides[require_auth] = lambda: {
        "id": user_id,
        "username": "alice",
        "email": None,
        "is_admin": False,
    }
    return TestClient(app, raise_server_exceptions=True)


def test_reading_dna_endpoint_aggregates_current_user_activity(
    monkeypatch: Any,
    pg_clean: str,
) -> None:
    db_path = _setup_db(monkeypatch, pg_clean)
    user_id = _make_user(db_path, "alice")
    article_id = _insert_article(db_path, "science-weekly", "science")
    now = datetime.now(timezone.utc)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO user_article_state(user_id, article_id, state, done_at)
            VALUES (%s, %s, 'done', %s)
            """,
            (user_id, article_id, now),
        )
        conn.execute(
            """
            INSERT INTO user_events(user_id, event_type, article_id, duration_ms, created_at)
            VALUES
              (%s, 'heartbeat', NULL, 120000, %s),
              (%s, 'article_close', %s, 30000, %s)
            """,
            (user_id, now, user_id, article_id, now),
        )

    try:
        with _client_for(user_id) as client:
            response = client.get("/api/users/me/reading-dna")
    finally:
        app.dependency_overrides.pop(require_auth, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["categories"][0]["category"] == "science"
    assert payload["categories"][0]["done"] == 1
    assert payload["sources"][0]["source"] == "Science-Weekly"
    assert payload["monthly_time"][0]["minutes"] == 2.0
    assert payload["average_dwell_seconds"] == 30.0


def test_recommendation_preferences_round_trip(monkeypatch: Any, pg_clean: str) -> None:
    db_path = _setup_db(monkeypatch, pg_clean)
    user_id = _make_user(db_path, "alice")

    try:
        with _client_for(user_id) as client:
            update = client.patch(
                "/api/users/me/recommendation-preferences",
                json={"category_weights": {"Science": 1.5}, "novelty_weight": 1.8},
            )
            readback = client.get("/api/users/me/recommendation-preferences")
    finally:
        app.dependency_overrides.pop(require_auth, None)

    assert update.status_code == 200
    assert update.json()["category_weights"] == {"science": 1.5}
    assert update.json()["novelty_weight"] == 1.8
    assert update.json()["recomputed"] == 0
    assert readback.status_code == 200
    assert readback.json()["category_weights"] == {"science": 1.5}
