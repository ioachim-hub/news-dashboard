# news-dashboard

Private dashboard for `news.lihor.ro`: a news inbox, reading tracker, source registry, and later summary/AI question layer for Ioachim.

## Product intent

The first useful version is intentionally small:

- Clau/cron jobs collect articles automatically from curated feeds.
- The dashboard stores reading evidence/history: new, read, saved, skipped, archived.
- Each item has source/category metadata plus a short summary/reason.
- Trending stories and GitHub repositories are separated from the curated inbox to avoid noise.
- AI Q&A over saved/read content is a later layer after the corpus exists.

## Source categories

- Python
- AI / LLM / agents
- Cloud / infrastructure
- Engineering
- Trending stories
- Trending repositories

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
npm install
NEWS_DASHBOARD_DB=./data/news-dashboard.db news-dashboard init
NEWS_DASHBOARD_DB=./data/news-dashboard.db news-dashboard ingest
NEWS_DASHBOARD_DB=./data/news-dashboard.db uvicorn news_dashboard.main:app --reload --app-dir backend
npm run dev
```

Open `http://localhost:5173`.

## Container

```bash
docker build -t news-dashboard:local .
docker run --rm -p 8080:8080 -v news-dashboard-data:/data news-dashboard:local
```

Open `http://localhost:8080`.

## Deployment notes

- The app should be private/auth-protected when exposed publicly.
- `news.lihor.ro` DNS is intentionally not configured here; Ioachim will handle DNS.
- Do not enable a Caddy/Ingress host until DNS resolves, otherwise ACME will fail with NXDOMAIN.
- GitHub Actions publishes `ghcr.io/ioachim-hub/news-dashboard`.
- For the local Kubernetes cluster, if GHCR pull auth is unavailable, build and push to `localhost:5000/news-dashboard:<tag>` and override Helm image values.
