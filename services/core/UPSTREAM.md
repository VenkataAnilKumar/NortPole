# Upstream source

Adapted from the upstream open-source core, commit `919578e0408a2d739a16215c09844c6762793891` (shallow clone, taken 2026-11-10).

## What was copied

- Backend package (renamed `evolvxsi`), `alembic`, `alembic_tenants`, `model_server`, `shared_configs`, `requirements`, `pyproject.toml`, `uv.lock` and unit tests.
- The web app source into `apps/workspace`.

## What was left out

- All `ee` directories (upstream enterprise licence), including external permission sync and enterprise search.
- Deployment files (Docker, Helm, Terraform, CI), desktop, mobile, extensions, widget, CLI, documentation, markdown docs and integration and end-to-end tests.
- The license public key and multi-tenant migration scripts that import `ee`.

## Changes after copying

- Rebranded by a one-time script that renamed the upstream product name to EvolvXSI. The script was removed afterwards; recover it from git history (commit 7cabc08, `tools/`) and re-run it on a fresh copy when taking a newer upstream commit.
- Community stubs replace `ee` imports in the web app: `src/lib/community/*`, `src/sections/SearchUI.tsx` and the hooks admin page.

## Restored later from the same commit (2026-11-14)

The first copy left out every markdown file and the integration tests, which also dropped some files the product or
its unit tests need. These were taken from the same upstream commit (`919578e`) and rebranded with
the same one-time script; none comes from an `ee` directory:

- Craft runtime templates: `evolvxsi/server/features/build/AGENTS.template.md` and
  `evolvxsi/server/features/build/sandbox/image/templates/outputs/web/AGENTS.md` (without them Craft wrote empty
  agent instructions).
- Dev scripts with unit tests: `scripts/env_inventory.py` (and its baseline), `sync_price_table.py`,
  `check_migration_determinism.py`, `run_enterpriserag_bench_questions.py`, `update_recommended_models.py`,
  `update_recommended_models_agent.py` (and its rules file and `openai_agent.py` helper),
  `generate_credential_bound_fields.py` (pointed at `apps/workspace`).
- Test helpers: `tests/integration/mock_services/mock_llm_server/`, `tests/external_dependency_unit/` (`conftest.py`,
  `full_setup.py`, `session_state_guard.py`, `oauth_provider/test_native_clients.py`) and
  `tests/unit/evolvxsi/connectors/source_operation_harnesses.py` (adapted to work without `ee`).

Tests for upstream deployment files that EvolvXSI does not ship now check EvolvXSI's own deployment
(`infrastructure/profiles/staging/docker-compose.retrieval.yml`) where it has the same thing (worker queues, the
index image) and were removed where it does not (the Craft compose file and CLI copy, the model-server image).
Tests that switch on Enterprise mode are skipped with a stated reason.

## Brand assets and documents

- Upstream brand assets were removed and replaced with new EvolvXSI placeholder assets: `public/logo*.png`, `logo.svg`, `logotype*.png`, `evolvxsi.ico`, `OpenSource.png`, the chat background images and thumbnails, the inline logo components in `lib/opal/src/logos` and `lib/opal/src/icons`, and the favicon and app icons in the sandbox web template. The wordmark text uses a system font; final brand artwork and typeface are still open.
- The upstream licensed font (KH Teka) was removed. The font token is now `font-brand` (Inter, then system fonts).
- Unreferenced Vercel and Next.js sample images and `favicon.zip` were removed from the sandbox web template, and the `ee` requirements file was removed.
- Third-party product logos (connector, model-provider and Slack source icons) were kept because they identify other companies' products. Check each company's brand rules before release.
- Unit-test fixture documents (PDF, Office files) were kept so the copied tests still work.

## Changes that matter for safety

- Telemetry: upstream sends fleet telemetry to an upstream domain by default. In this copy telemetry is **off by default** (`DISABLE_TELEMETRY` defaults to true) and the default endpoint is empty. Do not enable it without a deliberate decision.
- About 292 references to upstream domains (docs links, an HTTP-Referer header, pricing links) were deliberately left as written. Review them and replace or remove each before release; none is a data endpoint beyond the telemetry default above, but this was a grep, not an audit.

## Verified so far (2026-11-10, in a sandbox)

- Backend dependencies install from the regenerated `uv.lock` (backend group only; the model server and dev groups were not installed).
- `evolvxsi.main` imports without `ee`, and the FastAPI app builds with 616 routes including `/health`. Telemetry is off by default.
- 825 unit tests passed in `tests/unit/evolvxsi/skills` and `tests/unit/evolvxsi/utils`; one module needs the dev package `hypothesis`. The full unit suite has not been run.
- Web dependencies install except `xlsx` (its download host was blocked in the sandbox). `tsc` reports no errors in non-test source apart from the spreadsheet preview that needs `xlsx`. Test files fail type-checking because the upstream test setup folder was not copied.
- **Runs end to end in a sandbox, lite mode:** Postgres 16 plus Redis (Redis holds login tokens), with `DISABLE_VECTOR_DB=true`, `CACHE_BACKEND=postgres` and `FILE_STORE_BACKEND=postgres`. All 100-plus migrations apply; `/health` and `/health/ready` return 200; the web dev server renders the sign-up and sign-in pages with the new logo, and sign-up, sign-in and the main chat screen work.
- Chat has not been tried: no language model is configured, and search and indexing are off in lite mode. The run also needs `USER_AUTH_SECRET` set; the backend refuses to start without it.
- Not done: a production build, the full unit suite, or any connector test.
- Functional markdown (the built-in skill definitions under `skills/builtin`) is required at start-up and is included; other markdown documentation was left out.

## Clean-up of upstream leftovers (done 2026-11-10)

- Seeded and placeholder users now use `evolvxsi.local` addresses (code and migrations); all other upstream-domain addresses, including a named person's, were replaced or removed.
- The connector-request email is sent only when `CONNECTOR_REQUEST_EMAIL` is set; it no longer goes to an upstream address.
- The `HTTP-Referer` header for model providers now uses the app's own `WEB_DOMAIN`; the web crawler user agent no longer links to an upstream site; the evaluation CLI default points to localhost.
- Sandbox label keys moved from the upstream domain to `evolvxsi.local/...`.
- The Craft background video no longer loads from an upstream CDN (and the content security policy no longer allows it); the footer link and slogan are now neutral ("Governed agent workspace", English in every locale until translated); the contact-sales link is `NEXT_PUBLIC_SALES_URL` or `#`.
- The enterprise-only agent statistics links were removed, because that page was part of `ee`.
- Upstream names removed from code, tests and documents (2026-11-14). Help links go to the in-product Help page (`/help`); data files the product fetches (recommended models, price tables, Slack source icons, release notes) are read from this repository; the built-in skill that pointed the agent at the upstream documentation site was removed (migration `e5a7c9d1f346`). The upstream name remains only in the two `NOTICE` files, which the MIT licence requires, and in the Craft sandbox's command-line package name (`initial-requirements.in`), which is the published package's real name.
- The web dev server accepts only the `localhost` origin in development.

## EvolvXSI-owned additions (kept apart from the adapted upstream files)

- `evolvxsi/route_policy/`: route kinds (local, private, cloud), data classes (public, internal, confidential, restricted), the administrator's policy, a decision function, `GET /route-policy`, `POST /route-policy/check` and `PUT /admin/route-policy`. A request to a blocked route fails with `POLICY_BLOCKED` before any content is sent; a model that cannot be placed on a provider, and a provider with no route type, are treated as cloud (fail closed). The one upstream edit is the `enforce_route` call in `chat/process_message.py` (`_select_models`).
- Web: `RoutePicker` (`sections/model-selector/RoutePicker.tsx`) replaces the upstream model selector on the home and chat screens; a blocked route is listed but disabled with its reason.
- Audit trail: table `evolvxsi_audit_event` (migration `9b1e7c3a5d20`), `evolvxsi/route_policy/audit.py` and `GET /admin/route-policy/audit`. Every policy change (with a before and after diff) and every request refused with `POLICY_BLOCKED` is stored with the actor, time and policy facts, never message content. The same events also go to the log-only audit stream under two new, append-only `AuditAction` values (`route_policy.change`, `route.blocked`) in `utils/audit.py`. Rows are not pruned yet, and allowed requests are not logged.
- Admin page `Route Policy` (`/admin/route-policy`, view `RoutePolicyPage.tsx`): route type per provider, the data-class matrix, the workspace data class and a test panel. It needs the manage-LLMs permission. The sidebar label is English in every locale until translated.
- `services/model-gateway/src/adapters/mock/`: the deterministic mock model route used for development.
- The policy lives in the key-value store; the workspace data class is one default value for now. Per-task data classes need the source and classification work.

## Notification seeds disabled (2026-11-11)

The notifications poll used to create three upstream-seeded items on every read: a build-mode intro, a permissions-migration announcement linking to the upstream docs site, and release notes fetched from the upstream project's changelog on GitHub (an outbound network call). `_check_for_notifications_to_create` now does nothing. Admin-authored system announcements and the license-expiry notice still work, and EvolvXSI's own events arrive in later phases.

## Known gaps to build

- Per-user external permission sync (upstream keeps it in `ee`).
- The search results view and search API (upstream keeps them in `ee`).
- Lock files still name the upstream project and must be regenerated (`uv lock`, `bun install`).
