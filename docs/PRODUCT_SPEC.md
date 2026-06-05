# Product specification: news.lihor.ro

## Purpose

A private personal news dashboard for Ioachim. It combines:

1. News inbox — Clau/cron collects useful sources automatically.
2. Reading tracker — records what was read, saved, skipped, and archived.
3. Summary archive — stores short summaries/reasons on article cards.
4. Future AI question layer — ask Clau questions over saved/read history.

## Non-goals for v1

- No public unauthenticated access.
- No broad all-tech firehose.
- No complex AI Q&A before article history exists.
- No manual article creation as a primary workflow.
- No Anthropic scraping in initial feed-only MVP unless RSS becomes available.

## Initial sources

See `backend/news_dashboard/sources.py` for the canonical source list.

Sources are split by kind:

- `rss_feed`
- `github_release_feed`
- `trending_feed`

Future source kinds:

- `scraped_page`
- `newsletter_email`
- `manual_link`

## Status model

- `new`
- `read`
- `saved`
- `skipped`
- `archived`

## Future AI layer

After enough saved/read items exist:

- Add full text extraction for selected articles.
- Add SQLite FTS or vector embeddings.
- Add Ask Clau endpoint for questions like:
  - What did I read about LangGraph last month?
  - Which repos looked useful for agentic workflows?
  - What Python typing updates happened recently?
