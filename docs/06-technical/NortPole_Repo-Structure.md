# NortPole repository structure

Updated: 2026-11-14. Status: current layout, per [decision 0006](../decisions/0006-scalable-repository-structure.md). The
[module inventory](../../modules.json) is the machine-checked list of what exists and what is planned.

## Layout

```text
apps/workspace/                 Web app: the user workspace and the admin console (Next.js)
services/core/                  API and background workers (FastAPI, Celery): one deployable
services/model-gateway/         Mock model server for tests and the local profile
packages/contracts/             Generated: pack manifest JSON Schema, OpenAPI of NortPole routes
packages/pack-sdk/              Validate, build and sign packs without the server
packs/                          Workflow packs as source: horizontal/, vertical/<industry>/, editions/, _template/
infrastructure/profiles/        local runbook; staging profile (Compose, TLS, retrieval, backup, restore, release)
tools/                          Structure and link check, licence screen, software bill of materials
docs/                           Product, design, architecture, decisions, review log
.github/                        CI and code owners
Makefile                        One entry point for common commands
modules.json                    Existing and planned modules, with maturity
```

## Rules

1. **Folders exist only with code.** A future area is listed under `planned_modules` in `modules.json`; the structure check
   rejects a listed module that holds only placeholders and a planned module whose folder already exists.
2. **One core deployable.** API, workers, indexing and the scheduler already run as separate processes and scale
   separately. A service is split out only for its own scaling, release cycle or security boundary.
3. **NortPole code is grouped by domain inside `services/core/nortpole`**; inherited platform modules stay where they are
   so upstream fixes can still be compared file by file. `tests/unit/nortpole/test_domain_boundaries.py` enforces the
   layers (below) and lists the only places where inherited code calls into our domains.
4. **Packs are source**: `packs/horizontal/<pack>/` and `packs/vertical/<industry>/<pack>/`, each with `manifest.yaml`,
   bundled per industry by `packs/editions/<industry>.json`. See the [packs README](../../packs/README.md) for the rules
   and their tests.
5. **Contracts are generated** into `packages/contracts` (`make contracts`) and a test fails when they drift; the
   [pack SDK](../../packages/pack-sdk/README.md) validates and signs packs against them (`make packs`).

## NortPole domains in `services/core/nortpole`

| Domain | Modules | May import |
|---|---|---|
| `governance/` | `route_policy`, `redaction`, `tool_catalog`, `admin_changes`, `action_binding`, `audit_log`, `retention` | platform only |
| `work/` | `tasks`, `workflow_schedules`, `packs`, `actions` | governance, knowledge |
| `knowledge/` | `knowledge_access`, `source_requests` | governance, work |
| `insight/` | `quality`, `overview`, `inventory` | governance, work, knowledge (nothing imports insight) |
| top level | `extensions` (hook point), `external_permissions` (permission sync), `user_preferences` | fixed paths the inherited code looks up |

## Where the design-stage owners live

The design documents name logical owners. This is where each one is implemented:

| Design name | In code |
|---|---|
| `services/control-plane` (tenants, policy, approvals, registry) | `services/core`: platform modules, `governance/`, `work/packs` |
| `services/execution` (runs, jobs, scheduling, exports) | `services/core`: `work/` and the background workers |
| `services/knowledge` (ingestion, permissions, retrieval, citations) | `services/core`: inherited connectors, indexing and search, `knowledge/`, `external_permissions` |
| `services/model-gateway` (routing, budgets, usage) | `services/core`: inherited `llm`, `governance/route_policy` (routing, redaction, usage); the folder holds the mock server |
| `packages/contracts`, `packages/pack-sdk` | `packages/contracts` (generated) and `packages/pack-sdk` |
| `packages/agents`, `packages/skills` | `services/core`: inherited agents and skills; pack agents and guides in pack manifests |
| `packages/integrations` | `services/core`: inherited connectors, tools and MCP |
| `packages/identity-policy`, `packages/ui`, `evaluations` | `services/core` auth and policy; `apps/workspace` components; the pack evaluation gate. Separate packages are planned when needed |

## Checks

- `python tools/validate_structure.py`: inventory, module content, pack locations and every local Markdown link.
- `python -m pytest tools/tests`: tests for the checker and the other tools.
- `make check` runs both; `make help` lists the other commands.
