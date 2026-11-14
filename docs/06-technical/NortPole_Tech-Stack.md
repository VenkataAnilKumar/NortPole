# NortPole — tech stack

Status: current as built · Updated: 2026-11-12

What the product runs on today, read from the repository (`apps/workspace/package.json`, `services/core/pyproject.toml`). "Adopted" means it came with the copied upstream open-source core ([decision 0004](../decisions/0004-adopt-community-source-as-pilot-core.md)); "NortPole" means it was built in this project. Everything below has been run only in a sandbox with mock model routes.

## Web app (`apps/workspace`)

| Layer | Choice | Origin |
| --- | --- | --- |
| Framework | Next.js 16.4 (App Router), React 19.2, TypeScript | Adopted |
| Styling | Tailwind CSS 4; Opal components; design tokens built with Style Dictionary (warm neutral palette) | Adopted, restyled |
| Data and state | SWR for server data, Zustand for local state | Adopted |
| Themes and languages | next-themes (Light, Dark, System); next-intl with 9 locales (new labels are English placeholders) | Adopted |
| UI primitives | Radix UI | Adopted |
| Fonts | Inter, Newsreader, DM Mono, bundled with the app; no font fetched from Google | NortPole |
| Tests | Jest (unit), Playwright (browser checks) | Adopted |

## Backend (`services/core`)

| Layer | Choice | Origin |
| --- | --- | --- |
| Language | Python 3.13 | Adopted |
| API | FastAPI 0.133, Uvicorn, Pydantic 2 | Adopted |
| Database | PostgreSQL 16, SQLAlchemy, Alembic migrations | Adopted |
| Background work | Celery 5.5 with Redis: indexing, metadata re-sync, permission sync. Not running in lite mode | Adopted |
| Cache and locks | Redis; a Postgres-backed cache in lite mode | Adopted |
| Search index | OpenSearch 3.6: keyword and vector search with per-document access lists | Adopted |
| Model access | LiteLLM: one interface to local, private and cloud providers | Adopted |
| Sign-in | fastapi-users (basic login in use; SSO and SCIM code present, not configured) | Adopted |
| File storage | Postgres in lite mode; object storage in a full deployment | Adopted |

## NortPole-owned parts

| Part | Where | What it does |
| --- | --- | --- |
| Route policy | `services/core/nortpole/governance/route_policy/` | Which model route (local, private, cloud) may process which data class; refuses before sending; audited |
| Knowledge access | `services/core/nortpole/knowledge/knowledge_access/` | Group access for people and documents, source reading groups, group management; search-time source check enforced by default |
| Reviewed tasks | `services/core/nortpole/work/tasks/` | Draft, explicit start, plan drafted through the route policy, plan review |
| Packs | `services/core/nortpole/work/packs/` | Signed (Ed25519) vertical packs: task templates plus the data classes and route kinds each may run on; install, activate, upgrade, rollback, revoke |
| Actions | `services/core/nortpole/work/actions/` | Send an approved draft to an administrator-registered destination; exact-payload approval, policy and access re-checks, idempotent and address-pinned delivery |
| Audit log | `services/core/nortpole/governance/audit_log/` | Administrator view of the audit trail with filters and paging |
| Action binding | `services/core/nortpole/governance/action_binding/` | Approval tied to one exact action and payload; single use; policy block wins |
| User preferences | `services/core/nortpole/user_preferences/` | Default route and notification choices per person |
| Mock model routes | `services/model-gateway/src/adapters/mock/` | OpenAI-compatible test server standing in for local and cloud models |

## Development and testing

- Lite mode for the sandbox: Postgres, Redis and the mock model routes; no index or workers. See the [local runbook](../../infrastructure/profiles/local/README.md).
- OpenSearch 3.6 in Docker for the permission tests in `services/core/tests/nortpole_integration/`.
- `tools/validate_structure.py` before each commit; a one-time rebrand script was used for the original rebrand (removed; in git history at 7cabc08).

## Not chosen yet

| Decision | Blocked on |
| --- | --- |
| Real model runtimes and providers (for example vLLM or Ollama locally; a private or cloud provider) | Model access |
| Embedding model | The default model host is blocked in the sandbox; needs model access or a host allowance |
| Hosting (managed, customer cloud, on premises), orchestration (Kubernetes or Docker Compose), secrets management | Hosting decision ([deployment architecture](NortPole_Deployment-Architecture.md)) |
| Sandbox runtime for agent actions (Craft) | A full deployment with index, workers and a sandbox runtime |
