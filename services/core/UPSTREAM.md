# Upstream source

Adapted from the Onyx Community Edition, commit `919578e0408a2d739a16215c09844c6762793891` (shallow clone, taken 2026-11-10).

## What was copied

- Backend `onyx`, `alembic`, `alembic_tenants`, `model_server`, `shared_configs`, `requirements`, `pyproject.toml`, `uv.lock` and unit tests.
- The web app source into `apps/workspace`.

## What was left out

- All `ee` directories (Onyx Enterprise License), including external permission sync and enterprise search.
- Deployment files (Docker, Helm, Terraform, CI), desktop, mobile, extensions, widget, CLI, documentation, markdown docs and integration and end-to-end tests.
- The license public key and multi-tenant migration scripts that import `ee`.

## Changes after copying

- Rebranded with `tools/rebrand_onyx.py` (Onyx to EvolvXSI). Re-run it on a fresh copy when taking a newer upstream commit.
- Community stubs replace `ee` imports in the web app: `src/lib/community/*`, `src/sections/SearchUI.tsx` and the hooks admin page.

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

## Leftovers found while running it

- The footer text "Open Source AI Platform" (`i18n/messages/*.json`, key `slogan`) is upstream wording.
- A seeded anonymous user is created as `anonymous@onyx.app`.
- The connector-request feature (`server/documents/connector.py`) tracks to PostHog and sends an email to an upstream address. Remove or make it configurable before release.
- The web dev server accepts only the `localhost` origin in development.

## Known gaps to build

- Per-user external permission sync (upstream keeps it in `ee`).
- The search results view and search API (upstream keeps them in `ee`).
- Lock files still name the upstream project and must be regenerated (`uv lock`, `bun install`).
