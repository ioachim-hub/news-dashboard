"""PostgreSQL-backed briefings storage and read API.

Runtime SQL uses psycopg %s parameter style. No SQLite fallback.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .db import connect, row_to_dict

# Columns returned on briefing list items (no content blob, no articles).
_LIST_COLS = (
    "id",
    "created_at",
    "scope",
    "since_at",
    "until_at",
    "status",
    "title",
    "summary",
    "model",
    "error",
)

_CITED_ARTICLES_SQL = """
    SELECT
        a.id,
        a.title,
        a.url,
        a.canonical_url,
        a.source_name,
        a.category,
        a.kind,
        a.published_at,
        a.summary,
        a.importance_score,
        ba.section_index,
        ba.citation_index
    FROM briefing_articles ba
    JOIN articles a ON a.id = ba.article_id
    WHERE ba.briefing_id = %s
    ORDER BY ba.section_index NULLS LAST, ba.citation_index NULLS LAST, a.id
"""


def _fetch_cited_articles(conn: Any, briefing_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(_CITED_ARTICLES_SQL, (briefing_id,)).fetchall()
    return [row_to_dict(row) for row in rows]


def _coerce_content(value: Any) -> Any:
    """Normalise content: psycopg returns jsonb as dict already; SQLite TEXT needs decoding."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def get_latest_briefing(
    db_path: Path | None = None,
    database_url: str | None = None,
) -> dict[str, Any] | None:
    """Return the most recent briefing with cited articles, or None if none exist."""
    with connect(db_path, database_url) as conn:
        row = conn.execute(
            """
            SELECT id, created_at, scope, since_at, until_at, status,
                   title, summary, content, model, error
            FROM briefings
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (1,),
        ).fetchone()
        if row is None:
            return None
        briefing = row_to_dict(row)
        briefing["content"] = _coerce_content(briefing.get("content"))
        briefing["articles"] = _fetch_cited_articles(conn, briefing["id"])
        return briefing


def list_briefings(
    limit: int = 50,
    offset: int = 0,
    db_path: Path | None = None,
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    """Return briefing history (no content blob, no articles)."""
    with connect(db_path, database_url) as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, scope, since_at, until_at, status,
                   title, summary, model, error
            FROM briefings
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        ).fetchall()
        return [row_to_dict(r) for r in rows]


def get_briefing(
    briefing_id: int,
    db_path: Path | None = None,
    database_url: str | None = None,
) -> dict[str, Any] | None:
    """Return one briefing with full content and cited article metadata."""
    with connect(db_path, database_url) as conn:
        row = conn.execute(
            """
            SELECT id, created_at, scope, since_at, until_at, status,
                   title, summary, content, model, error
            FROM briefings
            WHERE id = %s
            """,
            (briefing_id,),
        ).fetchone()
        if row is None:
            return None
        briefing = row_to_dict(row)
        briefing["content"] = _coerce_content(briefing.get("content"))
        briefing["articles"] = _fetch_cited_articles(conn, briefing["id"])
        return briefing
