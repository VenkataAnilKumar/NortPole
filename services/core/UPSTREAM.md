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

## Clean-up of upstream leftovers (done 2026-11-10)

- Seeded and placeholder users now use `evolvxsi.local` addresses (code and migrations); all other `@onyx.app` addresses, including a named person's, were replaced or removed.
- The connector-request email is sent only when `CONNECTOR_REQUEST_EMAIL` is set; it no longer goes to an upstream address.
- The `HTTP-Referer` header for model providers now uses the app's own `WEB_DOMAIN`; the web crawler user agent no longer links to an upstream site; the evaluation CLI default points to localhost.
- Sandbox label keys moved from `onyx.app/...` to `evolvxsi.local/...`.
- The Craft background video no longer loads from an upstream CDN (and the content security policy no longer allows it); the footer link and slogan are now neutral ("Governed agent workspace", English in every locale until translated); the contact-sales link is `NEXT_PUBLIC_SALES_URL` or `#`.
- The enterprise-only agent statistics links were removed, because that page was part of `ee`.
- **Still to review:** about 290 references to the upstream documentation site (`docs.onyx.app`) remain as help links and in a few skill and migration text strings; none sends data.
- The web dev server accepts only the `localhost` origin in development.

## EvolvXSI-owned additions (kept apart from the adapted upstream files)

- `evolvxsi/route_policy/`: route kinds (local, private, cloud), data classes (public, internal, confidential, restricted), the administrator's policy, a decision function, `GET /route-policy`, `POST /route-policy/check` and `PUT /admin/route-policy`. A request to a blocked route fails with `POLICY_BLOCKED` before any content is sent; a model that cannot be placed on a provider, and a provider with no route type, are treated as cloud (fail closed). The one upstream edit is the `enforce_route` call in `chat/process_message.py` (`_select_models`).
- Web: `RoutePicker` (`sections/model-selector/RoutePicker.tsx`) replaces the upstream model selector on the home and chat screens; a blocked route is listed but disabled with its reason.
- Audit trail: table `evolvxsi_audit_event` (migration `9b1e7c3a5d20`), `evolvxsi/route_policy/audit.py` and `GET /admin/route-policy/audit`. Every policy change (with a before and after diff) and every request refused with `POLICY_BLOCKED` is stored with the actor, time and policy facts, never message content. The same events also go to the log-only audit stream under two new, append-only `AuditAction` values (`route_policy.change`, `route.blocked`) in `utils/audit.py`. Rows are not pruned yet, and allowed requests are not logged.
- Admin page `Route Policy` (`/admin/route-policy`, view `RoutePolicyPage.tsx`): route type per provider, the data-class matrix, the workspace data class and a test panel. It needs the manage-LLMs permission. The sidebar label is English in every locale until translated.
- `services/model-gateway/src/adapters/mock/`: the deterministic mock model route used for development.
- The policy lives in the key-value store; the workspace data class is one default value for now. Per-task data classes need the source and classification work.

## Known gaps to build

- Per-user external permission sync (upstream keeps it in `ee`).
- The search results view and search API (upstream keeps them in `ee`).
- Lock files still name the upstream project and must be regenerated (`uv lock`, `bun install`).
