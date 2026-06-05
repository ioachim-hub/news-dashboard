from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser

from .db import connect, init_db, insert_article_sql, row_to_dict
from .sources import DEFAULT_SOURCES, SourceDefinition

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "fbclid", "gclid"}
KEYWORD_TAGS = {
    "python": ["python", "typing", "mypy", "pyright", "ruff", "uv", "pypi", "scipy", "sklearn", "pytorch", "tensorflow"],
    "agents": ["agent", "agents", "langgraph", "langchain", "tool use", "workflow"],
    "llm": ["llm", "language model", "openai", "anthropic", "claude", "gemini", "rag", "retrieval"],
    "infra": ["kubernetes", "docker", "podman", "aws", "gcp", "azure", "container"],
    "data": ["data", "analytics", "observability", "evaluation", "benchmark"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in TRACKING_PARAMS]
    parsed = parsed._replace(fragment="", query=urlencode(query, doseq=True))
    return urlunparse(parsed)


def parse_date(entry: Any) -> str | None:
    for key in ("published", "updated", "created"):
        value = getattr(entry, key, None) or entry.get(key)
        if value:
            try:
                return parsedate_to_datetime(value).astimezone(timezone.utc).replace(microsecond=0).isoformat()
            except Exception:
                return str(value)
    return None


def infer_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags: list[str] = []
    for tag, keywords in KEYWORD_TAGS.items():
        if any(keyword in lowered for keyword in keywords):
            tags.append(tag)
    return tags


def make_summary(title: str, description: str, source: SourceDefinition) -> tuple[str, str, int, str]:
    text = clean_html(description)
    summary = text[:280] + ("…" if len(text) > 280 else "")
    tags = infer_tags(f"{title} {text} {source.category}")
    if not summary:
        summary = f"New item from {source.name}."
    reason = f"Tracked under {source.category.replace('-', ' ')} from {source.name}."
    score = min(100, source.priority + (10 if tags else 0))
    return summary, reason, score, ",".join(tags)


def source_signature(source: SourceDefinition, url: str) -> str:
    return hashlib.sha1(f"{source.slug}:{url}".encode()).hexdigest()[:12]


def sync_sources(db_path: Path | None = None) -> None:
    init_db(db_path)
    with connect(db_path) as conn:
        for source in DEFAULT_SOURCES:
            conn.execute(
                """
                INSERT INTO sources(slug, name, url, category, kind, priority, enabled)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(slug) DO UPDATE SET
                  name=excluded.name,
                  url=excluded.url,
                  category=excluded.category,
                  kind=excluded.kind,
                  priority=excluded.priority
                """,
                (source.slug, source.name, source.url, source.category, source.kind, source.priority),
            )


def ingest_source(source: SourceDefinition, db_path: Path | None = None) -> int:
    parsed = feedparser.parse(source.url)
    inserted = 0
    checked_at = now_iso()
    with connect(db_path) as conn:
        for entry in parsed.entries[:50]:
            raw_url = entry.get("link") or entry.get("id") or f"urn:{source_signature(source, entry.get('title', 'untitled'))}"
            url = canonicalize_url(raw_url)
            title = clean_html(entry.get("title") or "Untitled")
            description = entry.get("summary") or entry.get("description") or ""
            summary, reason, score, tags = make_summary(title, description, source)
            cursor = conn.execute(
                insert_article_sql(),
                (url, url, title, source.slug, source.name, source.category, source.kind, parse_date(entry), summary, reason, score, tags),
            )
            inserted += cursor.rowcount
        conn.execute("UPDATE sources SET last_checked_at=? WHERE slug=?", (checked_at, source.slug))
    return inserted


def ingest_all(db_path: Path | None = None) -> dict[str, int]:
    sync_sources(db_path)
    results: dict[str, int] = {}
    for source in DEFAULT_SOURCES:
        try:
            results[source.slug] = ingest_source(source, db_path)
        except Exception:
            results[source.slug] = -1
    return results


def list_articles(status: str | None = None, category: str | None = None, limit: int = 100, db_path: Path | None = None) -> list[dict]:
    init_db(db_path)
    clauses: list[str] = []
    params: list[object] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if category:
        clauses.append("category = ?")
        params.append(category)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    with connect(db_path) as conn:
        rows = conn.execute(f"SELECT * FROM articles {where} ORDER BY discovered_at DESC, id DESC LIMIT ?", params).fetchall()
        return [row_to_dict(row) for row in rows]


def set_article_status(article_id: int, status: str, db_path: Path | None = None) -> dict | None:
    if status not in {"new", "read", "saved", "skipped", "archived"}:
        raise ValueError("invalid status")
    timestamp_column = {
        "read": "read_at",
        "saved": "saved_at",
        "skipped": "skipped_at",
        "archived": "archived_at",
    }.get(status)
    init_db(db_path)
    with connect(db_path) as conn:
        if timestamp_column:
            conn.execute(
                f"UPDATE articles SET status=?, {timestamp_column}=?, updated_at=? WHERE id=?",
                (status, now_iso(), now_iso(), article_id),
            )
        else:
            conn.execute("UPDATE articles SET status=?, updated_at=? WHERE id=?", (status, now_iso(), article_id))
        row = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
        return row_to_dict(row) if row else None
