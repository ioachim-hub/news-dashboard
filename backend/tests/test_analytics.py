from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from news_dashboard.analytics import admin_analytics, record_events
from news_dashboard.db import connect, init_db


def _seed(db_path: Path) -> int:
    """Create one user, source, and article; return the article id."""
    init_db(db_path)
    with connect(db_path) as conn:
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


def test_record_events_filters_invalid_and_clamps(tmp_path: Path) -> None:
    db_path = tmp_path / "a.db"
    article_id = _seed(db_path)

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
        db_path=db_path,
    )
    assert stored == 5

    with connect(db_path) as conn:
        total = conn.execute(
            "SELECT COALESCE(SUM(duration_ms), 0) AS s FROM user_events"
            " WHERE event_type = 'heartbeat'"
        ).fetchone()["s"]
    # 10_000 + clamp(99_999_999) == 10_000 + 300_000
    assert total == 310_000


def test_admin_analytics_aggregates_behavior(tmp_path: Path) -> None:
    db_path = tmp_path / "b.db"
    article_id = _seed(db_path)
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
        db_path=db_path,
    )
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO user_article_state(user_id, article_id, state, done_at)"
            " VALUES (1, %s, 'done', %s)",
            (article_id, now - timedelta(hours=1)),
        )

    result = admin_analytics(days=30, db_path=db_path)

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


def test_admin_analytics_empty_db(tmp_path: Path) -> None:
    db_path = tmp_path / "c.db"
    init_db(db_path)
    result = admin_analytics(days=7, db_path=db_path)
    assert result["summary"]["mau"] == 0
    assert result["summary"]["stickiness"] == 0.0
    assert result["users"] == []
