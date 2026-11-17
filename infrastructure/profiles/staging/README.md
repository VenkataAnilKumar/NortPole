# Single-host profile (lite mode): web, API, PostgreSQL, Redis, nginx

Status: **checked once in a sandbox on 2026-11-12; not a supported production deployment.** It runs the web app and the API in containers with their database and one nginx entry point; a search index and workers are an overlay. Without the overlay below, retrieval-based sources do not work; chat, reviewed tasks without sources, packs, actions, audit and route policy do.

## Start

Set three secrets (never commit them), then build and start:

```bash
export POSTGRES_PASSWORD=$(openssl rand -hex 16)
export USER_AUTH_SECRET=$(openssl rand -hex 32)
export ENCRYPTION_KEY_SECRET=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
docker compose build
docker compose up -d
curl http://127.0.0.1:3000/api/health
```

The compose file refuses to start if any of the three is missing. `ENCRYPTION_KEY_SECRET` seals the secrets the product stores (connector credentials, API keys, bot tokens, people's integration accounts, the Studio signing key). **Keep it with your backups and never change it without running the rotation command below:** a database restored without its key cannot open those secrets, and people would have to connect their accounts again. Only nginx is published, on `127.0.0.1:3000` (`/api/` goes to the API, everything else to the web app). The plain nginx file serves HTTP only: use the TLS overlay below before exposing it. The web image bakes the API address (`http://api:8080`) in at build time. The API applies database migrations when it starts. The first account that registers becomes the administrator.

## TLS

`docker-compose.tls.yml` swaps the entry point for `nginx-tls.conf`: HTTP on port 80 redirects to HTTPS on 443, HTTPS carries HSTS (one year, no preload), `nosniff` and a referrer policy (the web app's own copies are hidden so each header appears once), TLS 1.2 and 1.3 only. `/api/health` stays on plain HTTP so a load balancer can probe it. You supply the certificate: a folder with `tls.crt` (chain) and `tls.key`; they are mounted read-only and never belong in the repository.

```bash
export TLS_CERT_DIR=/path/to/certs      # holds tls.crt and tls.key
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d
```

It publishes on all interfaces by default (it is meant to be reached from outside); set `BIND_ADDRESS`, `HTTP_PORT` and `HTTPS_PORT` to narrow or move it. The redirect assumes HTTPS is on 443. Getting and renewing a certificate (a public CA, an internal CA, or a load balancer that ends TLS instead) is a hosting decision and is not set up here.

## Rotating or first sealing the key

Values stored before sealing existed are read as plain text until they are sealed. To seal them, or to move to a new key, run this once from `services/core` with the new key in the environment (add `--dry-run` first to see the count; `--old-key` is the key the values are sealed with now, and is left out for plain-text values). It is safe to run again:

```bash
ENCRYPTION_KEY_SECRET=<new key> python -m nortpole.db.rotate_encryption_key --dry-run
ENCRYPTION_KEY_SECRET=<new key> python -m nortpole.db.rotate_encryption_key [--old-key <old key>]
```

## Signing in to services (OAuth)

People can sign in to an integration with their own account instead of pasting a token. For each service you want, register an OAuth app with that service and put its client id and secret in `oauth.env` next to the compose file (the file is optional and must stay out of git):

```
NORTPOLE_OAUTH_GITHUB_CLIENT_ID=...
NORTPOLE_OAUTH_GITHUB_CLIENT_SECRET=...
```

The name is the provider in capitals with dashes as underscores: `GITHUB`, `GOOGLE_DRIVE`, `GOOGLE_EMAIL` (Gmail), `GOOGLE_CALENDAR`, `HUBSPOT`, `DROPBOX`, `SPOTIFY`, `WEBFLOW`, `NOTION`, `AIRTABLE`. Register the redirect address `<WEB_DOMAIN>/app/sources/oauth` with each service, where `WEB_DOMAIN` is the address people use (set it in the environment; the default is `http://localhost:3000`). A service with no client id and secret keeps the paste-a-token form. Slack and Stripe do not use this flow here. Tokens are sealed with `ENCRYPTION_KEY_SECRET` and renewed automatically when a service gives a refresh token. The service addresses were written from the services' public descriptions and have not been tried against the live services.

## Backup and restore

In this profile PostgreSQL holds everything that must survive: accounts, drafts, packs, settings, the audit log and uploaded files. Redis is rebuilt on start. The search index (retrieval overlay) is not backed up; it is rebuilt by re-indexing.

```bash
./backup.sh /path/to/backups                 # one compressed dump plus a manifest (checksum, migration revision, audit row count)
./restore.sh /path/to/backups/nortpole-<time>.dump    # replaces the current database after you type "replace"
```

Run both from this folder with the same `-f` files (or `COMPOSE_FILE`) and environment you start the stack with. The restore refuses a dump whose checksum does not match its manifest, stops the API and web app, recreates the database, loads the dump, starts them again (the API applies any newer migrations), and prints how to check the audit log chain afterwards. Copy the dump and manifest off the machine; the backups are not encrypted by these scripts, so store them with the same care as the database.

To keep a bounded number of dumps, set `KEEP=14` (delete all but the newest 14 after each backup; only files named `nortpole-*.dump` and their manifests are touched). To run it daily, a cron entry such as the following works; set the secrets the same way you start the stack:

```bash
15 2 * * *  cd /opt/nortpole/infrastructure/profiles/staging && . /etc/nortpole/env && KEEP=14 ./backup.sh /var/backups/nortpole >> /var/log/nortpole-backup.log 2>&1
```

Scheduling is only an example here and was not run on a clock; the script itself and `KEEP` were run by hand.

## Upgrade and rollback

Images are tagged with `NORTPOLE_VERSION` (default `dev`). To upgrade: take a backup, build or pull the new images tagged with the new version, then `NORTPOLE_VERSION=<new> docker compose up -d`; the API applies database migrations when it starts. `./release.sh manifest <version>` writes a small JSON record of the product commit, the two image IDs and the migration head for that version.

To roll back, start the previous version tag **and restore the backup taken before the upgrade**: migrations are not assumed to be reversible, so older code may not run against a newer database. A rollback therefore loses anything written after that backup.

Sharing images through a registry: tag both images with the registry name, push, and pull on the target machine before `up -d`:

```bash
docker tag nortpole-core:<version> <registry>/nortpole-core:<version>   # and the same for nortpole-web
docker push <registry>/nortpole-core:<version>
docker pull <registry>/nortpole-core:<version>
```

Pull and tag the images back to the plain `nortpole-core:<version>` names (or change the `image:` lines) so the compose file finds them. Signing images and scanning them for vulnerabilities are not set up.

## Building behind a proxy that re-signs HTTPS

If your network inspects TLS, `pip install` inside the build fails with a certificate error. Build a small base image that trusts your CA and tag it `python:3.13-slim` on the build machine (`COPY` the CA certificate into `/usr/local/share/ca-certificates/`, run `update-ca-certificates`, and set `SSL_CERT_FILE`, `PIP_CERT` and `UV_NATIVE_TLS=true`), then build with the proxy address as `HTTPS_PROXY`/`HTTP_PROXY` build arguments and `--network host` (with `docker buildx build --allow network.host`). That image carries your CA, so keep it local and do not push it. The sandbox used this route.

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
- TLS overlay with a self-signed certificate on other ports (sandbox, 2026-11-13): HTTP redirected to HTTPS (301), `/api/health` answered on both, the login page loaded over HTTP/2 with a single set of security headers, a client that trusted the certificate verified it, a TLS 1.1 client was refused, and the plain port 3000 listener was gone.
- Backup and restore drill (sandbox, 2026-11-13, on the older image already built here): an account and two drafts were created and backed up (524 KB dump, manifest with checksum); a third draft was added afterwards; a dump with one extra byte was refused; the restore then brought back exactly the two backed-up drafts, the account could sign in, and the API was healthy.
- Rebuilt API image and the upgrade path (sandbox, 2026-11-13): the API image was rebuilt from the current source (about 2.5 GB). The older backup (database at migration `4e2a7c9d5b36`) was restored under the new image: the API applied the newer migrations on start and reached `8c6e1a4b9d70`, the account signed in, both drafts were present, and the audit chain check answered. After three audited changes, a new backup was restored: the chain check read intact over the 3 backed-up rows (a fourth change made after the backup was gone, as expected).
- Clean-room start: with the volume deleted, `up -d` on the images alone gave a healthy API in about five seconds at migration head; the first registered account could reach admin endpoints; packs and the HTTPS login page answered.
- Registry round trip against a local `registry:2`: both images were pushed, the local core tag removed, and the pulled image had the same ID as the built one.
- `KEEP=2` kept the newest two of four backups, a non-numeric value was refused before any work, and unrelated files in the folder were left alone.
- Version pinning: with `NORTPOLE_VERSION=0.0.1` the API and web containers were recreated on the `0.0.1` images and `up -d` without it moved them back to `dev`. `release.sh manifest` printed the commit, image IDs and a migration head that matches `alembic heads`.
- Building in the sandbox needed a proxy certificate and an HTTPS package mirror that a normal network does not; those sandbox-only steps are not in the file.

## Not covered
- The web image was not rebuilt in this pass (it is the one built earlier), so the clean-room start used an older web build.
- The web image build skips the type check (errors exist only in test files whose shared setup folder is missing from the repo); the web build needs `cdn.sheetjs.com` (the `xlsx` package).
- The model server of the core itself (embeddings and reranking inside the image) is not used; an external embedding server is required for retrieval.
- Log shipping, secrets management, resource limits, certificate issuing and renewal, encrypted backups, a managed registry with signing and scanning, a backup run on a real schedule, CI, and upgrades without downtime.
