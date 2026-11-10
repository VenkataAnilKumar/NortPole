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

## Changes that matter for safety

- Telemetry: upstream sends fleet telemetry to an upstream domain by default. In this copy telemetry is **off by default** (`DISABLE_TELEMETRY` defaults to true) and the default endpoint is empty. Do not enable it without a deliberate decision.
- About 292 references to upstream domains (docs links, an HTTP-Referer header, pricing links) were deliberately left as written. Review them and replace or remove each before release; none is a data endpoint beyond the telemetry default above, but this was a grep, not an audit.

## Known gaps to build

- Per-user external permission sync (upstream keeps it in `ee`).
- The search results view and search API (upstream keeps them in `ee`).
- Lock files still name the upstream project and must be regenerated (`uv lock`, `bun install`).
