from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from news_dashboard.analytics import (
    MAX_EVENTS_PER_BATCH,
    admin_analytics,
    prune_old_events,
    record_events,
)
from news_dashboard.db import connect, init_db
from news_dashboard.main import app


@pytest.fixture
def client(pg_clean: str, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", pg_clean)
    init_db(database_url=pg_clean)
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client


def _seed(database_url: str) -> int:
    """Create one user, source, and article; return the article id."""
    init_db(database_url=database_url)
    with connect(database_url=database_url) as conn:
        conn.execute(
            "INSERT INTO users(id, username, password_hash, is_admin)"
            " VALUES (1, 'reader', 'x', FALSE)"
        )
        conn.execute(
            "INSERT INTO sources(slug, name, url, category, kind)"
            " VALUES ('s1', 'Source One', 'https://s1.example', 'tech', 'rss')"
        )
        conn.execute(
            """
            INSERT INTO articles(id, url, canonical_url, title, source_slug,
                                 source_name, category, kind)
            VALUES (10, 'https://s1.example/a', 'https://s1.example/a', 'Hello',
                    's1', 'Source One', 'tech', 'rss')
            """
        )
    return 10


def test_events_endpoint_rejects_oversized_batch(client: TestClient) -> None:
    response = client.post(
        "/api/events",
        json={"events": [{"type": "heartbeat", "duration_ms": 1}] * (MAX_EVENTS_PER_BATCH + 1)},
    )

    assert response.status_code == 422


def test_record_events_filters_invalid_and_clamps(pg_clean: str) -> None:
    article_id = _seed(pg_clean)

    stored = record_events(
        1,
        [
            {"type": "heartbeat", "duration_ms": 10_000},
            {"type": "heartbeat", "duration_ms": 99_999_999},  # clamped
            {"type": "route", "route": "/today"},
            {"type": "article_close", "article_id": article_id, "duration_ms": 4_000},
            {"type": "feature", "feature": "ask"},
            {"type": "bogus", "route": "/x"},  # dropped
        ],
        database_url=pg_clean,
    )
    assert stored == 5

    with connect(database_url=pg_clean) as conn:
        total = conn.execute(
            "SELECT COALESCE(SUM(duration_ms), 0) AS s FROM user_events"
            " WHERE event_type = 'heartbeat'"
        ).fetchone()["s"]
    # 10_000 + clamp(99_999_999) == 10_000 + 300_000
    assert total == 310_000


def test_record_events_defensively_caps_direct_batches(pg_clean: str) -> None:
    _seed(pg_clean)

    stored = record_events(
        1,
        [{"type": "route", "route": f"/item/{index}"} for index in range(MAX_EVENTS_PER_BATCH + 1)],
        database_url=pg_clean,
    )

    assert stored == MAX_EVENTS_PER_BATCH
    with connect(database_url=pg_clean) as conn:
        total = conn.execute("SELECT COUNT(*) AS count FROM user_events").fetchone()["count"]
    assert total == MAX_EVENTS_PER_BATCH


def test_prune_old_events_deletes_only_expired_rows(pg_clean: str) -> None:
    _seed(pg_clean)
    now = datetime.now(timezone.utc)
    record_events(
        1,
        [
            {"type": "route", "route": "/old"},
            {"type": "route", "route": "/recent"},
        ],
        database_url=pg_clean,
    )
    with connect(database_url=pg_clean) as conn:
        conn.execute(
            """
            UPDATE user_events
            SET created_at = CASE route
                WHEN '/old' THEN %s
                ELSE %s
            END
            """,
            (now - timedelta(days=181), now - timedelta(days=10)),
        )

    deleted = prune_old_events(database_url=pg_clean)

    assert deleted == 1
    with connect(database_url=pg_clean) as conn:
        routes = [
            row["route"]
            for row in conn.execute("SELECT route FROM user_events ORDER BY route").fetchall()
        ]
    assert routes == ["/recent"]


def test_admin_analytics_aggregates_behavior(pg_clean: str) -> None:
    article_id = _seed(pg_clean)
    now = datetime.now(timezone.utc)

    record_events(
        1,
        [
            {"type": "heartbeat", "duration_ms": 60_000},
            {"type": "route", "route": "/today"},
            {"type": "route", "route": "/today"},
            {"type": "feature", "feature": "ask"},
            {"type": "article_close", "article_id": article_id, "duration_ms": 30_000},
        ],
        database_url=pg_clean,
    )
    with connect(database_url=pg_clean) as conn:
        conn.execute(
            "INSERT INTO user_article_state(user_id, article_id, state, done_at)"
            " VALUES (1, %s, 'done', %s)",
            (article_id, now - timedelta(hours=1)),
        )

    result = admin_analytics(days=30, database_url=pg_clean)

    assert result["summary"]["mau"] == 1
    assert result["summary"]["total_minutes"] == 1.0
    assert result["summary"]["total_reads"] == 1
    assert result["summary"]["total_sessions"] == 1

    routes = {r["route"]: r["views"] for r in result["route_popularity"]}
    assert routes["/today"] == 2

    features = {f["feature"]: f["count"] for f in result["feature_usage"]}
    assert features["ask"] == 1

    dwell = {d["article_id"]: d["avg_dwell_seconds"] for d in result["article_dwell"]}
    assert dwell[article_id] == 30.0

    categories = {c["category"]: c["reads"] for c in result["category_consumption"]}
    assert categories["tech"] == 1


def test_admin_analytics_empty_db(pg_clean: str) -> None:
    init_db(database_url=pg_clean)
    result = admin_analytics(days=7, database_url=pg_clean)
    assert result["summary"]["mau"] == 0
    assert result["summary"]["stickiness"] == 0.0
    assert result["users"] == []
