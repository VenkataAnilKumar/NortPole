# Local development profile (lite mode)

Runs the adapted backend and web app on one machine with no search index, no model server and no external model provider. Verified once in a sandbox on 2026-11-10; not a supported deployment.

## What you need

- PostgreSQL 16 and Redis (Redis holds login tokens).
- Python 3.13 with `uv`, and Node 22 with `bun`.

## Steps

1. **Database:** create an empty database and run `alembic upgrade head` in `services/core`.
2. **Mock model routes (no keys needed):** from `services/model-gateway/src/adapters/mock`, run `python mock_openai_server.py --name local-mock --port 18001` and `--name cloud-mock --port 18002`. These are deterministic test replies, not real models.
3. **Backend:** in `services/core`, run `uvicorn evolvxsi.main:app --port 8080` with these environment variables: `DISABLE_VECTOR_DB=true`, `CACHE_BACKEND=postgres`, `FILE_STORE_BACKEND=postgres`, `AUTH_TYPE=basic`, `USER_AUTH_SECRET=<random hex>`, `EVOLVXSI_OFFLINE_TOKENIZER=true`, and `NO_PROXY=127.0.0.1,localhost` if your shell sets an outbound proxy.
4. **Routes:** sign up in the app, make the first account an administrator, then register each mock route as an `openai_compatible` provider whose base URL is `http://127.0.0.1:18001/v1` or `http://127.0.0.1:18002/v1`, and set a default model.
5. **Web:** in `apps/workspace`, run `bun install`, build the shared packages (`build:tokens` in `lib/shared`, then `build` in `lib/opal`), and start `next dev` with `INTERNAL_URL=http://127.0.0.1:8080`. Open it as `localhost`, not `127.0.0.1`.

## Known problems seen in the sandbox

- On a fresh database the first account becomes an administrator (checked through the API on 2026-11-10). In the sandbox an unexplained extra registration took that slot first, and the next account landed in the Basic group. If nobody can reach the admin panel, run `PYTHONPATH=. python scripts/grant_admin.py <email>` in `services/core` with the same database settings. It moves an existing user into the Admin group and recomputes permissions; it never creates users, and running it requires database access.
- The `xlsx` package is downloaded from a host a sandbox may block.
- Without `EVOLVXSI_OFFLINE_TOKENIZER=true` the backend tries to download a tokenizer and chat fails if the download is blocked.

## Retrieval index for the permission harness (sandbox)

Lite mode has no index. To run the A5 permission harness, start a single-node OpenSearch 3.6.0 with security off (local testing only, never a shared host):

```bash
docker run -d --name evx-opensearch -p 9200:9200 -e discovery.type=single-node -e DISABLE_SECURITY_PLUGIN=true -e DISABLE_INSTALL_DEMO_CONFIG=true -e "OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g" opensearchproject/opensearch:3.6.0
```

If the host disk is over 90% full, OpenSearch blocks index creation. On a throwaway test container only, turn the disk check off:

```bash
curl -s -XPUT http://127.0.0.1:9200/_cluster/settings -H 'Content-Type: application/json' -d '{"persistent":{"cluster.routing.allocation.disk.threshold_enabled":false,"cluster.blocks.create_index":null}}'
```

Redis must be running (index creation takes a lock). Then, from `services/core`:

```bash
OPENSEARCH_HOST=127.0.0.1 OPENSEARCH_USE_SSL=false NO_PROXY=127.0.0.1,localhost PYTHONPATH=. pytest tests/evolvxsi_integration/test_retrieval_acl.py
```

The harness skips itself when no OpenSearch answers.

