# Self-Hosting

**Note**: The GHCR package must be made public (or accessible via pull secret) for this to work.
> This is a one-time maintainer action: go to the repository's Packages settings,
> select the `ghcr.io/lihor-hub/news-dashboard` package, and change its visibility to Public.

This guide explains how to deploy News Dashboard for production use using the published Docker image from GitHub Container Registry (GHCR).

## Docker Compose: Dev vs Production

The repository provides two Docker Compose files:

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Local development only (builds from source, insecure dev defaults) |
| `docker-compose.prod.yml` | Production deployment (uses published image, requires secure configuration) |

> **Warning**: Never use `docker-compose.yml` for production. It contains insecure defaults suitable only for local development.

## Running with Docker Compose (Production)

### Prerequisites

- PostgreSQL database (version 16+)
- Docker or container runtime
- Required environment variables (see [Configuration](#configuration))

### Step 1: Create Environment File

Copy `.env.example` to `.env` and fill in the required values:

```bash
cp .env.example .env
# Edit .env with your secure values
```

See the [.env.example reference](#environment-variables) below for all available options.

### Step 2: Start the Stack

```bash
docker compose -f docker-compose.prod.yml up -d
```

The compose file will fail fast if required secrets (`SESSION_SECRET`, `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_PASSWORD`, `POSTGRES_PASSWORD`) are not set.

### Verifying the Deployment

```bash
# Check service status
docker compose -f docker-compose.prod.yml ps

# Check health endpoint
curl http://localhost:8080/api/health
# Should return: {"status":"ok"}
```

## Image Tags and Versioning

The image is available with the following tags:

- `ghcr.io/lihor-hub/news-dashboard:latest` - Rolling update to the most recent release
- `ghcr.io/lihor-hub/news-dashboard:v<version>` - Specific version (e.g., `v1.21.0`)
- `ghcr.io/lihor-hub/news-dashboard:<commit-sha>` - Exact commit (e.g., `a1b2c3d4e5f6`)

For production deployments, we recommend pinning to a specific version or commit SHA to ensure consistency and prevent unexpected updates.

### Updating docker-compose.prod.yml to Pin a Version

Edit the `image` line in `docker-compose.prod.yml`:

```yaml
services:
  news-dashboard:
    image: ghcr.io/lihor-hub/news-dashboard:v1.21.0  # Pin to specific version
    # ...
```

Then pull and restart:

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

## Environment Variables

See the [README Configuration section](../README.md#configuration) for the complete list of environment variables.

### Required Variables

| Variable | Description |
|----------|-------------|
| `SESSION_SECRET` | Signed session key. Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `BOOTSTRAP_ADMIN_USERNAME` | Initial admin username (created on first run) |
| `BOOTSTRAP_ADMIN_PASSWORD` | Initial admin password |
| `POSTGRES_PASSWORD` | PostgreSQL database password |

### Optional AI Features

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for summaries, insights, TTS |
| `FREE_LLM_API_KEY` | Alternative LLM API key |
| `FREE_LLM_BASE_URL` | Custom LLM endpoint |

> **Important**: Never commit secrets to version control. Use environment variables or a `.env` file (not committed to Git) to manage sensitive values.

## Upgrading

To upgrade to a newer version:

1. Pull the new image: `docker compose -f docker-compose.prod.yml pull`
2. Restart the service: `docker compose -f docker-compose.prod.yml up -d`
3. Run database migrations if needed:
   ```bash
   docker compose -f docker-compose.prod.yml run --rm news-dashboard news-dashboard init
   ```

> **Important**: Before upgrading, back up your PostgreSQL database. See [POSTGRES_BACKUP.md](./POSTGRES_BACKUP.md) for backup strategies.

## Health Checks

Verify your instance is healthy:

```bash
# Basic health check (public)
curl http://localhost:8080/api/health
# Should return: {"status":"ok"}

# Detailed health (admin only)
curl http://localhost:8080/api/health/details
# Returns database, scheduler, and source health information
```

### Kubernetes/Container Probe Examples

```yaml
# Kubernetes liveness probe
livenessProbe:
  httpGet:
    path: /api/health
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 30

# Kubernetes readiness probe
readinessProbe:
  httpGet:
    path: /api/health
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 10

# Docker HEALTHCHECK
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/api/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## Resource Sizing

Recommended resources for a personal instance with default sources:

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 0.5 cores | 1 core |
| RAM | 512 MB | 1 GB |
| Disk | 5 GB | 10 GB+ (depends on article retention) |

For high ingest frequency or many users, scale resources accordingly.

## Backups

Regularly back up your PostgreSQL database. See [POSTGRES_BACKUP.md](./POSTGRES_BACKUP.md) for backup strategies.

## Next Steps

- **Set up HTTPS** with a reverse proxy (see [CADDY_HTTPS_SETUP.md](./CADDY_HTTPS_SETUP.md))
- Configure optional features like AI capabilities, Keycloak SSO, or Web Push notifications
- Set up regular backups of your PostgreSQL data