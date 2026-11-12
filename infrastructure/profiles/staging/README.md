# Single-host profile (lite mode): web, API, PostgreSQL, Redis, nginx

Status: **checked once in a sandbox on 2026-11-12; not a supported production deployment.** It runs the web app and the API in containers with their database and one nginx entry point; a search index and workers are an overlay. Without the overlay below, retrieval-based sources do not work; chat, reviewed tasks without sources, packs, actions, audit and route policy do.

## Start

Set two secrets (never commit them), then build and start:

```bash
export POSTGRES_PASSWORD=$(openssl rand -hex 16)
export USER_AUTH_SECRET=$(openssl rand -hex 32)
docker compose build
docker compose up -d
curl http://127.0.0.1:3000/api/health
```

The compose file refuses to start if either secret is missing. Only nginx is published, on `127.0.0.1:3000` (`/api/` goes to the API, everything else to the web app). The nginx file serves plain HTTP: add TLS before exposing it. The web image bakes the API address (`http://api:8080`) in at build time. The API applies database migrations when it starts. The first account that registers becomes the administrator.

## Retrieval (search index, embeddings, workers)

Add the overlay file to get document retrieval and cited, source-grounded drafts:

```bash
docker compose -f docker-compose.yml -f docker-compose.retrieval.yml up -d
```

This adds OpenSearch (not published outside the compose network, security plugin off for that reason) and starts the API with the vector database on. Search needs an embedding model: with Ollama on the host and `nomic-embed-text` pulled, run (inside the API container, then restart the API so it creates the index):

```bash
docker compose -f docker-compose.yml -f docker-compose.retrieval.yml exec api python scripts/setup_local_embeddings.py \
  --email <admin email> --password <admin password> --url http://host.docker.internal:11434/v1
docker compose -f docker-compose.yml -f docker-compose.retrieval.yml restart api
```

The background workers (crawling sources, syncing, indexing from connectors) are a separate optional service: add `--profile workers`. Documents sent through the ingestion API are indexed without workers.

## Use a model server on the same machine

The API container can reach a model server on the host as `http://host.docker.internal:<port>` (the compose file maps that name). In the admin console add an OpenAI-compatible provider with that base URL, set a default model, and mark the route local under Route policy. The server must listen on an address the container network can reach (for Ollama, `OLLAMA_HOST=0.0.0.0:11434`).

## What was checked
- The API image (`services/core/Dockerfile`) builds with no system packages and is about 520 MB; the web image (`apps/workspace/Dockerfile`) builds a production Next.js server.
- In a browser through nginx: sign-in, the home screen, Packs, Reviewed tasks, and the admin Route policy, Audit and Packs pages all loaded with no page errors.
- With a local Ollama (qwen2.5:7b) registered as above: a reviewed task planned with the real model, accepted and ran (with no source, so the run states that no source covers the request instead of calling the model), a chat message sent from the browser returned the requested word, and the admin route-usage view counted one `task_plan` and one `chat` request on the local route.
- With the retrieval overlay, `nomic-embed-text` embeddings and four documents sent through the ingestion API, a reviewed task for "how long do I have to hand in travel expense receipts and who approves large claims" returned a draft that cited the Travel Receipts source for the 30-day rule. It did not find the approval rule in the other indexed document (it said the document does not specify who approves): recall is limited by retrieval and the 7B relevance check, not solved. The worker container booted with all five workers and the scheduler running; no connector was crawled through it.
- `/api/health` answers; registering, signing in, and calling the pack, action, audit, task and route-usage endpoints work; the database is at the latest migration.
- `docker compose down` followed by `up` keeps accounts (named volume).
- Building in the sandbox needed a proxy certificate and an HTTPS package mirror that a normal network does not; those sandbox-only steps are not in the file.

## Not covered
- The web image build skips the type check (errors exist only in test files whose shared setup folder is missing from the repo); the web build needs `cdn.sheetjs.com` (the `xlsx` package).
- The model server of the core itself (embeddings and reranking inside the image) is not used; an external embedding server is required for retrieval.
- Backups, upgrades with downtime, log shipping, secrets management, TLS, and resource limits.
