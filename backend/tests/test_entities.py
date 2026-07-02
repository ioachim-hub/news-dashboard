"""Tests for LLM-backed entity extraction and the knowledge graph."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from news_dashboard.db import connect
from news_dashboard.entities import (
    EntitiesNotConfiguredError,
    _parse_entities,
    extract_entities,
    extract_missing_entities,
    get_or_extract_entities,
    knowledge_graph,
)

# ── helpers ───────────────────────────────────────────────────────────────────


def _seed_source(pg_url: str, slug: str, *, owner_user_id: int | None = None) -> None:
    with connect(database_url=pg_url) as conn:
        conn.execute(
            """
            INSERT INTO sources(slug, name, url, category, kind, owner_user_id)
            VALUES (%s, %s, %s, 'tech', 'rss_feed', %s)
            ON CONFLICT(slug) DO NOTHING
            """,
            (slug, slug, f"https://{slug}.example", owner_user_id),
        )


def _seed_article(
    pg_url: str,
    *,
    slug: str = "ent-src",
    url_slug: str,
    title: str,
    summary: str = "Summary.",
    entities: str | None = None,
) -> int:
    _seed_source(pg_url, slug)
    with connect(database_url=pg_url) as conn:
        row = conn.execute(
            """
            INSERT INTO articles(
              url, canonical_url, title, source_slug, source_name,
              category, kind, summary, entities, discovered_at
            )
            VALUES (%s, %s, %s, %s, %s, 'tech', 'rss_feed', %s, %s, NOW())
            RETURNING id
            """,
            (
                f"https://{slug}.example/{url_slug}",
                f"https://{slug}.example/{url_slug}",
                title,
                slug,
                slug,
                summary,
                entities,
            ),
        ).fetchone()
    assert row is not None
    return int(row["id"])


def _seed_user(pg_url: str, username: str) -> int:
    with connect(database_url=pg_url) as conn:
        row = conn.execute(
            "INSERT INTO users(username, password_hash) VALUES (%s, 'x') RETURNING id",
            (username,),
        ).fetchone()
    assert row is not None
    return int(row["id"])


def _entities_json(*pairs: tuple[str, str]) -> str:
    return json.dumps({"v": 1, "entities": [{"name": n, "type": t} for n, t in pairs]})


def _mock_llm(content: str) -> MagicMock:
    completion = MagicMock()
    completion.choices[0].message.content = content
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    return client


# ── _parse_entities ───────────────────────────────────────────────────────────


def test_parse_entities_handles_fenced_json() -> None:
    payload = '[{"name": "OpenAI", "type": "org"}, {"name": "Sam Altman", "type": "person"}]'
    raw = f"```json\n{payload}\n```"
    parsed = _parse_entities(raw)
    assert parsed == [
        {"name": "OpenAI", "type": "org"},
        {"name": "Sam Altman", "type": "person"},
    ]


def test_parse_entities_drops_invalid_types_and_dedupes() -> None:
    raw = json.dumps(
        [
            {"name": "OpenAI", "type": "org"},
            {"name": "openai", "type": "org"},  # duplicate, case-insensitive
            {"name": "Something", "type": "alien"},  # invalid type
            {"name": "", "type": "org"},  # empty name
            {"name": "Paris", "type": "place"},
        ]
    )
    parsed = _parse_entities(raw)
    assert parsed == [{"name": "OpenAI", "type": "org"}, {"name": "Paris", "type": "place"}]


def test_parse_entities_returns_empty_for_garbage() -> None:
    assert _parse_entities("not json at all") == []
    assert _parse_entities(json.dumps({"name": "x"})) == []


# ── extract_entities ──────────────────────────────────────────────────────────


def test_extract_entities_raises_without_api_key() -> None:
    import os

    env = dict(os.environ.items())
    for key in ("FREE_LLM_API_KEY", "FREE_LLM_BASE_URL", "OPENAI_API_KEY"):
        env.pop(key, None)
    with patch.dict("os.environ", env, clear=True), pytest.raises(EntitiesNotConfiguredError):
        extract_entities({"id": 1, "title": "T", "summary": "S", "body": None})


def test_extract_entities_calls_llm_and_returns_parsed_list() -> None:
    client = _mock_llm('[{"name": "OpenAI", "type": "org"}, {"name": "OpenAI", "type": "org"}]')
    with (
        patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
        patch("openai.OpenAI", return_value=client),
    ):
        result = extract_entities(
            {"id": 1, "title": "OpenAI ships", "summary": "OpenAI news", "body": "text"}
        )
    assert result == [{"name": "OpenAI", "type": "org"}]
    client.chat.completions.create.assert_called_once()


# ── get_or_extract_entities ───────────────────────────────────────────────────


def test_get_or_extract_entities_returns_cached_without_api_call(pg_clean: str) -> None:
    cached = _entities_json(("OpenAI", "org"))
    article_id = _seed_article(pg_clean, url_slug="cached", title="T", entities=cached)

    client = _mock_llm("[]")
    with (
        patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
        patch("openai.OpenAI", return_value=client),
    ):
        result = get_or_extract_entities(article_id, database_url=pg_clean)

    assert result == [{"name": "OpenAI", "type": "org"}]
    client.chat.completions.create.assert_not_called()


def test_get_or_extract_entities_extracts_and_caches_when_missing(pg_clean: str) -> None:
    article_id = _seed_article(pg_clean, url_slug="fresh", title="OpenAI ships a model")

    client = _mock_llm('[{"name": "OpenAI", "type": "org"}]')
    with (
        patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
        patch("openai.OpenAI", return_value=client),
    ):
        first = get_or_extract_entities(article_id, database_url=pg_clean)
        second = get_or_extract_entities(article_id, database_url=pg_clean)

    assert first == [{"name": "OpenAI", "type": "org"}]
    assert second == first
    client.chat.completions.create.assert_called_once()

    with connect(database_url=pg_clean) as conn:
        row = conn.execute("SELECT entities FROM articles WHERE id = %s", (article_id,)).fetchone()
    stored = json.loads(row["entities"])
    assert stored["v"] == 1
    assert stored["entities"] == [{"name": "OpenAI", "type": "org"}]


def test_get_or_extract_entities_invisible_article_returns_empty(pg_clean: str) -> None:
    owner_id = _seed_user(pg_clean, "ent-owner")
    other_id = _seed_user(pg_clean, "ent-other")
    _seed_source(pg_clean, "ent-private", owner_user_id=owner_id)
    article_id = _seed_article(
        pg_clean,
        slug="ent-private",
        url_slug="priv",
        title="Private",
        entities=_entities_json(("Secret Corp", "org")),
    )

    assert get_or_extract_entities(article_id, user_id=other_id, database_url=pg_clean) == []
    assert get_or_extract_entities(article_id, user_id=owner_id, database_url=pg_clean) == [
        {"name": "Secret Corp", "type": "org"}
    ]


# ── extract_missing_entities ──────────────────────────────────────────────────


def test_extract_missing_entities_respects_limit_and_survives_failures(pg_clean: str) -> None:
    for idx in range(4):
        _seed_article(pg_clean, url_slug=f"m-{idx}", title=f"Article {idx}")

    calls: list[int] = []

    def fake_extract(article: dict[str, Any], user_id: int | None = None) -> list[dict[str, str]]:
        calls.append(int(article["id"]))
        if len(calls) == 1:
            msg = "transient failure"
            raise RuntimeError(msg)
        return [{"name": "OpenAI", "type": "org"}]

    with patch("news_dashboard.entities.extract_entities", side_effect=fake_extract):
        extracted = extract_missing_entities(limit=3, database_url=pg_clean)

    assert len(calls) == 3
    assert extracted == 2

    with connect(database_url=pg_clean) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM articles WHERE entities IS NOT NULL"
        ).fetchone()
    assert row["n"] == 2


# ── knowledge_graph ───────────────────────────────────────────────────────────


def test_knowledge_graph_empty_corpus(pg_clean: str) -> None:
    result = knowledge_graph(database_url=pg_clean)
    assert result["nodes"] == []
    assert result["edges"] == []
    assert result["pending_count"] == 0


def test_knowledge_graph_builds_nodes_edges_and_article_refs(pg_clean: str) -> None:
    a1 = _seed_article(
        pg_clean,
        url_slug="g1",
        title="OpenAI and Altman",
        entities=_entities_json(("OpenAI", "org"), ("Sam Altman", "person")),
    )
    a2 = _seed_article(
        pg_clean,
        url_slug="g2",
        title="OpenAI and Altman again",
        entities=_entities_json(("OpenAI", "org"), ("Sam Altman", "person")),
    )
    a3 = _seed_article(
        pg_clean,
        url_slug="g3",
        title="OpenAI alone",
        entities=_entities_json(("OpenAI", "org")),
    )
    _seed_article(pg_clean, url_slug="g4", title="Pending extraction")

    result = knowledge_graph(database_url=pg_clean)

    nodes = {n["name"]: n for n in result["nodes"]}
    assert nodes["OpenAI"]["type"] == "org"
    assert nodes["OpenAI"]["count"] == 3
    assert nodes["Sam Altman"]["count"] == 2
    assert set(nodes["OpenAI"]["article_ids"]) == {a1, a2, a3}

    assert len(result["edges"]) == 1
    edge = result["edges"][0]
    assert edge["weight"] == 2
    assert set(edge["article_ids"]) == {a1, a2}
    assert {edge["source"], edge["target"]} == {nodes["OpenAI"]["id"], nodes["Sam Altman"]["id"]}

    titles = {a["id"]: a["title"] for a in result["articles"]}
    assert titles[a1] == "OpenAI and Altman"
    assert result["pending_count"] == 1
    assert result["article_count"] == 4


def test_knowledge_graph_truncates_to_max_nodes(pg_clean: str) -> None:
    pairs = [(f"Entity {i}", "org") for i in range(6)]
    _seed_article(pg_clean, url_slug="t1", title="Many entities", entities=_entities_json(*pairs))
    result = knowledge_graph(database_url=pg_clean, max_nodes=3)
    assert len(result["nodes"]) == 3


def test_knowledge_graph_scopes_to_user_visible_articles(pg_clean: str) -> None:
    user_id = _seed_user(pg_clean, "kg-user")
    other_id = _seed_user(pg_clean, "kg-other")
    _seed_source(pg_clean, "kg-global")
    _seed_source(pg_clean, "kg-other-private", owner_user_id=other_id)

    _seed_article(
        pg_clean,
        slug="kg-global",
        url_slug="vis",
        title="Visible",
        entities=_entities_json(("OpenAI", "org")),
    )
    _seed_article(
        pg_clean,
        slug="kg-other-private",
        url_slug="hid",
        title="Hidden",
        entities=_entities_json(("Secret Corp", "org")),
    )

    result = knowledge_graph(user_id=user_id, database_url=pg_clean)
    names = {n["name"] for n in result["nodes"]}
    assert "OpenAI" in names
    assert "Secret Corp" not in names
