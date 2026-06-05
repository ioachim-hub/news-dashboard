from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit, urlunsplit

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - optional unless DATABASE_URL is PostgreSQL
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]

DB_PATH = Path(os.getenv("NEWS_DASHBOARD_DB", "/data/news-dashboard.db"))
POSTGRES_PREFIXES = ("postgres:" + "//", "postgresql:" + "//")

SQLITE_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sources (
  slug TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  category TEXT NOT NULL,
  kind TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 50,
  enabled INTEGER NOT NULL DEFAULT 1,
  last_checked_at TEXT
);

CREATE TABLE IF NOT EXISTS articles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT NOT NULL UNIQUE,
  canonical_url TEXT NOT NULL,
  title TEXT NOT NULL,
  source_slug TEXT NOT NULL REFERENCES sources(slug),
  source_name TEXT NOT NULL,
  category TEXT NOT NULL,
  kind TEXT NOT NULL,
  published_at TEXT,
  discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new','read','saved','skipped','archived')),
  importance_score INTEGER NOT NULL DEFAULT 50,
  summary TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '',
  read_at TEXT,
  saved_at TEXT,
  skipped_at TEXT,
  archived_at TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_discovered ON articles(discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_slug);
"""

POSTGRES_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS sources (
      slug TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      url TEXT NOT NULL,
      category TEXT NOT NULL,
      kind TEXT NOT NULL,
      priority INTEGER NOT NULL DEFAULT 50,
      enabled INTEGER NOT NULL DEFAULT 1,
      last_checked_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS articles (
      id BIGSERIAL PRIMARY KEY,
      url TEXT NOT NULL UNIQUE,
      canonical_url TEXT NOT NULL,
      title TEXT NOT NULL,
      source_slug TEXT NOT NULL REFERENCES sources(slug),
      source_name TEXT NOT NULL,
      category TEXT NOT NULL,
      kind TEXT NOT NULL,
      published_at TEXT,
      discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new','read','saved','skipped','archived')),
      importance_score INTEGER NOT NULL DEFAULT 50,
      summary TEXT NOT NULL DEFAULT '',
      reason TEXT NOT NULL DEFAULT '',
      tags TEXT NOT NULL DEFAULT '',
      read_at TEXT,
      saved_at TEXT,
      skipped_at TEXT,
      archived_at TEXT,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status)",
    "CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category)",
    "CREATE INDEX IF NOT EXISTS idx_articles_discovered ON articles(discovered_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_slug)",
]


def active_database_url(database_url: str | None = None) -> str | None:
    if database_url is not None:
        return database_url
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")
    host = os.getenv("POSTGRES_HOST")
    if not host:
        return None
    user = os.getenv("POSTGRES_USER", "news_dashboard")
    password = os.getenv("POSTGRES_PASSWORD", "")
    database = os.getenv("POSTGRES_DB", "news_dashboard")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def is_postgres(database_url: str | None = None) -> bool:
    url = active_database_url(database_url)
    return bool(url and url.startswith(POSTGRES_PREFIXES))


def describe_database(db_path: Path | None = None, database_url: str | None = None) -> str:
    url = active_database_url(database_url)
    if url:
        parts = urlsplit(url)
        if parts.password:
            host = parts.hostname or ""
            netloc = f"{parts.username}:***@{host}"
            if parts.port:
                netloc += f":{parts.port}"
            return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
        return url
    return str(db_path or DB_PATH)


class PostgresConnection:
    def __init__(self, conn: Any):
        self.conn = conn

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] | None = None) -> Any:
        return self.conn.execute(sql.replace("?", "%s"), params)

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


@contextmanager
def connect(db_path: Path | None = None, database_url: str | None = None) -> Iterator[Any]:
    url = active_database_url(database_url)
    if is_postgres(url):
        if psycopg is None:
            raise RuntimeError("DATABASE_URL is PostgreSQL but psycopg is not installed")
        conn = psycopg.connect(url, row_factory=dict_row)
        wrapped = PostgresConnection(conn)
        try:
            yield wrapped
            wrapped.commit()
        finally:
            wrapped.close()
        return

    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path | None = None, database_url: str | None = None) -> None:
    if is_postgres(database_url):
        with connect(db_path, database_url) as conn:
            for statement in POSTGRES_SCHEMA:
                conn.execute(statement)
        return
    with connect(db_path, database_url) as conn:
        conn.executescript(SQLITE_SCHEMA)


def row_to_dict(row: Any) -> dict:
    if isinstance(row, dict):
        return dict(row)
    return {key: row[key] for key in row.keys()}


def insert_article_sql() -> str:
    if is_postgres():
        return """
            INSERT INTO articles(
              url, canonical_url, title, source_slug, source_name, category, kind,
              published_at, summary, reason, importance_score, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (url) DO NOTHING
            """
    return """
        INSERT OR IGNORE INTO articles(
          url, canonical_url, title, source_slug, source_name, category, kind,
          published_at, summary, reason, importance_score, tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
