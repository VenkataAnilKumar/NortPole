# Single-host profile (lite mode): API, PostgreSQL, Redis

Status: **checked once in a sandbox on 2026-11-12; not a supported production deployment.** It runs the EvolvXSI API in a container with its database, without a search index, a model server, or a web container. Retrieval-based sources therefore do not work in this profile; chat, reviewed tasks without sources, packs, actions, audit and route policy do.

## Start

Set two secrets (never commit them), then build and start:

```bash
export POSTGRES_PASSWORD=$(openssl rand -hex 16)
export USER_AUTH_SECRET=$(openssl rand -hex 32)
docker compose build
docker compose up -d
curl http://127.0.0.1:8080/health
```

The compose file refuses to start if either secret is missing. The API is published on `127.0.0.1:8080` only; put a TLS reverse proxy in front before exposing it. The API applies database migrations when it starts. The first account that registers becomes the administrator.

## What was checked
- The image (`services/core/Dockerfile`) builds with no system packages and is about 520 MB.
- `/health` answers; registering, signing in, and calling the pack, action, audit, task and route-usage endpoints work; the database is at the latest migration.
- `docker compose down` followed by `up` keeps accounts (named volume).
- Building in the sandbox needed a proxy certificate and an HTTPS package mirror that a normal network does not; those sandbox-only steps are not in the file.

## Not covered
- The web app has no container yet (it is run with `next dev` or a production build by hand).
- No search index, so no document retrieval; no model server; no real model route (register one in the admin console).
- Backups, upgrades with downtime, log shipping, secrets management, TLS, and resource limits.
