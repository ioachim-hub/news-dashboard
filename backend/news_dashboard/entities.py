"""LLM-backed named-entity extraction and the news knowledge graph.

Entities (people, orgs, products, places) are extracted once per article via
the free-LLM gateway and cached in ``articles.entities`` as JSON
``{"v": 1, "entities": [{"name", "type"}]}`` — mirroring how ``insights``
caches its bullets. ``knowledge_graph()`` aggregates the cached entities only
and never invokes the LLM, so the endpoint stays fast and free; a scheduler
job (``entity_extraction``) fills the cache in the background.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from news_dashboard.db import connect, init_db

logger = logging.getLogger(__name__)

DEFAULT_ENTITIES_MODEL = "gpt-4o-mini"
ENTITIES_CACHE_VERSION = 1
_ENTITY_TYPES = frozenset({"person", "org", "product", "place"})
_MAX_TEXT_CHARS = 4_000
_MAX_ENTITIES_PER_ARTICLE = 10
_MAX_GRAPH_ARTICLES = 300
_PROMPT = (
    "Extract the named entities from the news article below. "
    "Return ONLY a JSON array (no prose, no code fences) of at most "
    f"{_MAX_ENTITIES_PER_ARTICLE} objects, each shaped "
    '{"name": "<canonical short name>", "type": "<person|org|product|place>"}. '
    "Use the most canonical short form of each name (e.g. 'OpenAI', not "
    "'OpenAI, Inc.'). Only include entities that are clearly mentioned in the "
    "article text; do not invent or infer entities from general knowledge."
)


class EntitiesNotConfiguredError(Exception):
    """Raised when no AI key is configured for entity extraction."""


def _entities_ai_config() -> tuple[str, str | None, str]:
    from news_dashboard.ai_client import free_llm_config

    api_key, base_url = free_llm_config()
    if not api_key:
        msg = "FREE_LLM_API_KEY (or OPENAI_API_KEY) is not configured"
        raise EntitiesNotConfiguredError(msg)
    model = os.getenv("OPENAI_ENTITIES_MODEL", DEFAULT_ENTITIES_MODEL)
    return api_key, base_url, model


def _build_text(article: dict[str, Any]) -> str:
    parts = [
        str(article.get("title") or ""),
        str(article.get("summary") or ""),
        str(article.get("body") or ""),
    ]
    return "\n\n".join(p for p in parts if p.strip())[:_MAX_TEXT_CHARS]


def _parse_entities(response_text: str) -> list[dict[str, str]]:
    """Parse the model response into a validated, deduplicated entity list."""
    text = response_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()

    try:
        raw = json.loads(text)
    except ValueError:
        return []
    if not isinstance(raw, list):
        return []

    entities: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        entity_type = str(item.get("type") or "").strip().lower()
        if not name or entity_type not in _ENTITY_TYPES:
            continue
        key = (name.lower(), entity_type)
        if key in seen:
            continue
        seen.add(key)
        entities.append({"name": name, "type": entity_type})
        if len(entities) >= _MAX_ENTITIES_PER_ARTICLE:
            break
    return entities


def extract_entities(article: dict[str, Any], user_id: int | None = None) -> list[dict[str, str]]:
    """Call the LLM and return the extracted entity list.

    Raises EntitiesNotConfiguredError when no AI key is configured.
    """
    api_key, base_url, model = _entities_ai_config()

    text = _build_text(article)
    if not text.strip():
        return []

    from news_dashboard.ai_client import chat_create, get_chat_client, get_prompt

    client = get_chat_client(api_key=api_key, base_url=base_url)
    prompt = get_prompt("entity-extraction", fallback=_PROMPT)
    logger.info("Extracting entities for article %s", article.get("id"))
    result = chat_create(
        client,
        name="entity-extraction",
        tags=["entities"],
        user_id=user_id,
        prompt=prompt,
        model=model,
        messages=[{"role": "user", "content": f"{prompt.text}\n\n{text}"}],
        max_tokens=512,
    )
    response_text = (result.choices[0].message.content or "").strip()
    entities = _parse_entities(response_text)
    logger.info("Entities extracted for article %s: %d entities", article.get("id"), len(entities))
    return entities


def _decode_cached(raw: str | None) -> list[dict[str, str]] | None:
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    entities = payload.get("entities")
    if not isinstance(entities, list):
        return None
    return [e for e in entities if isinstance(e, dict)]


def _store_entities(
    article_id: int, entities: list[dict[str, str]], database_url: str | None
) -> None:
    payload = json.dumps({"v": ENTITIES_CACHE_VERSION, "entities": entities})
    with connect(database_url=database_url) as conn:
        conn.execute("UPDATE articles SET entities = %s WHERE id = %s", (payload, article_id))


def get_or_extract_entities(
    article_id: int,
    user_id: int | None = None,
    database_url: str | None = None,
) -> list[dict[str, str]]:
    """Return cached entities or extract + cache them.

    When user_id is provided the article must be visible to that user.
    Returns [] for invisible or non-existent articles.
    """
    init_db(database_url=database_url)

    with connect(database_url=database_url) as conn:
        if user_id is not None:
            row = conn.execute(
                """
                SELECT a.id, a.title, a.summary, a.body, a.entities
                FROM articles a
                JOIN sources src ON src.slug = a.source_slug
                LEFT JOIN user_sources us_src
                  ON us_src.source_slug = a.source_slug AND us_src.user_id = %s
                WHERE a.id = %s AND (
                  (src.owner_user_id IS NULL AND COALESCE(us_src.enabled, TRUE))
                  OR src.owner_user_id = %s
                )
                """,
                (user_id, article_id, user_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, title, summary, body, entities FROM articles WHERE id = %s",
                (article_id,),
            ).fetchone()

    if row is None:
        return []

    cached = _decode_cached(row["entities"])
    if cached is not None:
        return cached

    entities = extract_entities(dict(row), user_id=user_id)
    _store_entities(article_id, entities, database_url)
    return entities


def extract_missing_entities(
    limit: int = 25,
    days: int = 7,
    database_url: str | None = None,
) -> int:
    """Extract entities for up to ``limit`` recent articles lacking them.

    Per-article failures are logged and skipped so one bad article does not
    starve the batch. Returns the number of articles successfully extracted.
    """
    init_db(database_url=database_url)

    with connect(database_url=database_url) as conn:
        rows = conn.execute(
            """
            SELECT id, title, summary, body
            FROM articles
            WHERE discovered_at::timestamptz >= NOW() - INTERVAL '1 day' * %s
              AND entities IS NULL
            ORDER BY discovered_at DESC
            LIMIT %s
            """,
            (days, limit),
        ).fetchall()

    extracted = 0
    for row in rows:
        try:
            entities = extract_entities(dict(row))
        except EntitiesNotConfiguredError:
            raise
        except Exception:
            logger.exception("Entity extraction failed for article %s", row["id"])
            continue
        _store_entities(int(row["id"]), entities, database_url)
        extracted += 1
    return extracted


def _entity_id(name: str, entity_type: str) -> str:
    return f"{entity_type}:{name.lower().replace(' ', '-')}"


def knowledge_graph(
    user_id: int | None = None,
    days: int = 7,
    max_nodes: int = 40,
    database_url: str | None = None,
) -> dict[str, Any]:
    """Aggregate cached entities over recent visible articles into a graph.

    Reads the cache only — never calls the LLM. ``pending_count`` reports how
    many visible recent articles still lack extracted entities so the UI can
    explain a sparse graph.
    """
    init_db(database_url=database_url)

    with connect(database_url=database_url) as conn:
        if user_id is None:
            rows = conn.execute(
                """
                SELECT id, title, entities
                FROM articles
                WHERE discovered_at::timestamptz >= NOW() - INTERVAL '1 day' * %s
                ORDER BY discovered_at DESC
                LIMIT %s
                """,
                (days, _MAX_GRAPH_ARTICLES),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT a.id, a.title, a.entities
                FROM articles a
                JOIN sources src ON src.slug = a.source_slug
                LEFT JOIN user_sources us
                  ON us.source_slug = src.slug AND us.user_id = %s
                LEFT JOIN user_article_state uas
                  ON uas.article_id = a.id AND uas.user_id = %s
                WHERE a.discovered_at::timestamptz >= NOW() - INTERVAL '1 day' * %s
                  AND COALESCE(uas.state, 'today') != 'archived'
                  AND (
                    (
                      src.owner_user_id IS NULL
                      AND COALESCE(us.enabled, TRUE) IS TRUE
                    )
                    OR (
                      src.owner_user_id = %s
                      AND src.enabled IS TRUE
                    )
                  )
                ORDER BY a.discovered_at DESC
                LIMIT %s
                """,
                (user_id, user_id, days, user_id, _MAX_GRAPH_ARTICLES),
            ).fetchall()

    pending_count = 0
    # node key -> {"id", "name", "type", "count", "article_ids"}
    node_map: dict[tuple[str, str], dict[str, Any]] = {}
    # article id -> list of node keys mentioned in it
    mentions: dict[int, list[tuple[str, str]]] = {}
    titles: dict[int, str] = {}

    for row in rows:
        entities = _decode_cached(row["entities"])
        if entities is None:
            pending_count += 1
            continue
        article_id = int(row["id"])
        keys: list[tuple[str, str]] = []
        for entity in entities:
            name = str(entity.get("name") or "").strip()
            entity_type = str(entity.get("type") or "").strip().lower()
            if not name or entity_type not in _ENTITY_TYPES:
                continue
            key = (name.lower(), entity_type)
            if key in keys:
                continue
            keys.append(key)
            node = node_map.setdefault(
                key,
                {
                    "id": _entity_id(name, entity_type),
                    "name": name,
                    "type": entity_type,
                    "count": 0,
                    "article_ids": [],
                },
            )
            node["count"] += 1
            node["article_ids"].append(article_id)
        if keys:
            mentions[article_id] = keys
            titles[article_id] = str(row["title"] or "")

    kept = sorted(node_map.values(), key=lambda n: (-n["count"], n["name"]))[:max_nodes]
    kept_keys = {(n["name"].lower(), n["type"]) for n in kept}
    node_id_by_key = {(n["name"].lower(), n["type"]): n["id"] for n in kept}

    # edge (id_a, id_b) sorted -> {"weight", "article_ids"}
    edge_map: dict[tuple[str, str], dict[str, Any]] = {}
    referenced_articles: set[int] = set()
    for article_id, keys in mentions.items():
        visible = [k for k in keys if k in kept_keys]
        for i in range(len(visible)):
            for j in range(i + 1, len(visible)):
                id_a = node_id_by_key[visible[i]]
                id_b = node_id_by_key[visible[j]]
                edge_key = (id_a, id_b) if id_a < id_b else (id_b, id_a)
                edge = edge_map.setdefault(edge_key, {"weight": 0, "article_ids": []})
                edge["weight"] += 1
                edge["article_ids"].append(article_id)
        if visible:
            referenced_articles.add(article_id)

    edges = [
        {
            "source": source,
            "target": target,
            "weight": data["weight"],
            "article_ids": data["article_ids"],
        }
        for (source, target), data in sorted(edge_map.items(), key=lambda item: -item[1]["weight"])
    ]

    return {
        "nodes": kept,
        "edges": edges,
        "articles": [
            {"id": article_id, "title": titles[article_id]}
            for article_id in sorted(referenced_articles)
        ],
        "article_count": len(rows),
        "pending_count": pending_count,
        "days": days,
    }
