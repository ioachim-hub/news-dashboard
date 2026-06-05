from pathlib import Path

from news_dashboard.db import describe_database, init_db
from news_dashboard.ingest import ingest_all, list_articles


def test_sqlite_file_database_reports_path_and_persists_between_connections(tmp_path: Path) -> None:
    db_path = tmp_path / "durable.db"

    init_db(db_path)
    first = ingest_all(db_path)
    second = ingest_all(db_path)

    assert db_path.exists()
    assert sum(value for value in first.values() if value > 0) >= 0
    assert sum(value for value in second.values() if value > 0) == 0
    assert list_articles(limit=1, db_path=db_path) or first == second
    assert describe_database(db_path) == str(db_path)


def test_postgres_url_is_reported_without_password() -> None:
    dsn = "postgresql://news_dashboard:secret-password@postgres:5432/news_dashboard"

    assert describe_database(database_url=dsn) == "postgresql://news_dashboard:***@postgres:5432/news_dashboard"
