# Decision 0006: scalable repository structure

Date: 2026-11-14. Status: **accepted** by the product owner, delivered phase by phase. It replaces the target layout in
[decision 0001](0001-modular-monorepo.md) and the [repository structure](../06-technical/EvolvXSI_Repo-Structure.md) document,
which described service skeletons that were never built.

## Context

The working product is two deployables: `services/core` (API and background workers) and `apps/workspace` (web app).
Placeholder services and packages from the design stage hold only `README` and `.gitkeep` files, `modules.json` calls the
working code a skeleton, EvolvXSI's own modules sit unmarked among the inherited ones, and first-party workflow packs live
outside the `packs/` folder (one as a sample file, the rest only in a sandbox database). The product will add more packs,
vertical editions, connectors, a cloud offering and partners, so the repository must make ownership and boundaries clear.

## Decision

1. **One repository, one core deployable.** Split a service out only when it needs its own scaling, release cycle or
   security boundary. Background workers already scale separately as processes.
2. **Folders exist only with code.** Future areas are listed in `modules.json` under `planned_modules`, not created empty.
3. **EvolvXSI's own modules are grouped by domain** inside `services/core/evolvxsi`: `governance/`, `work/`, `knowledge/`
   and `insight/`. Inherited modules stay where they are, so upstream fixes can still be compared file by file. Two of our
   modules stay at the top level because inherited code looks them up by path: `extensions` (the hook point) and
   `external_permissions` (the permission-sync implementation).
4. **Boundaries are tested.** A unit test reads every import: inherited code may reach EvolvXSI code only through the
   entry points it already uses (a ratchet: new ones fail until reviewed), and `governance` never imports `work`,
   `knowledge` or `insight`.
5. **Packs are source.** `packs/horizontal/<pack>/` holds domain-neutral packs and `packs/vertical/<industry>/<pack>/`
   holds industry packs, each with a `manifest.yaml`. `packs/editions/<industry>.json` bundles packs for an industry. The
   folder must match the manifest's `vertical`; pack ids are unique; horizontal packs never depend on vertical ones.
6. **Contracts are generated.** The pack manifest schema and the API description of EvolvXSI's routes are generated from
   the code into `packages/contracts`, and a test fails when they drift. `packages/pack-sdk` validates, builds and signs
   packs from source using that schema, producing the same digest the server verifies.

## Target structure

```text
apps/workspace/                 web app: user side and admin console
services/core/                  API + background workers
  evolvxsi/governance/          route_policy, redaction, tool_catalog, admin_changes, action_binding, audit_log, retention
  evolvxsi/work/                tasks, workflow_schedules, packs, actions
  evolvxsi/knowledge/           knowledge_access, source_requests
  evolvxsi/insight/             quality, overview, inventory
  evolvxsi/extensions/          hook point (fixed path)
  evolvxsi/external_permissions/ permission sync (fixed path)
  evolvxsi/…                    inherited platform modules, unchanged
services/model-gateway/         mock model server used by tests and the sandbox
packs/horizontal/<pack>/        domain-neutral packs (manifest.yaml)
packs/vertical/<industry>/<pack>/ industry packs (manifest.yaml)
packs/editions/<industry>.json  bundles per industry
packs/_template/                authoring template
packages/contracts/             generated pack schema and API description
packages/pack-sdk/              validate, build and sign packs
evaluations/  infrastructure/  tools/  docs/
.github/workflows/  .github/CODEOWNERS  Makefile  modules.json
```

## Phases

| Phase | Plan and design | Tests that close it |
|---|---|---|
| **1. Tidy** | Remove the placeholder services and packages; keep the model-gateway mock. Make `modules.json` true and list future areas as planned. Update the structure check (no service-skeleton rule; nested vertical packs). Add `CODEOWNERS`, a `Makefile`, and CI jobs for the web app and a nightly full backend suite. Rewrite the repository structure document. | Structure check and its tests pass; no link points at a removed folder; CI runs green on the pull request. |
| **2. Domains** | Move the 17 movable EvolvXSI modules into `governance/`, `work/`, `knowledge/` and `insight/`, updating imports, patch targets and documents. Add the import-boundary test. | Full unit suite (same failures as before, all sandbox-only), integration suite, route contract and boundary tests pass; the API starts. |
| **3. Packs as source** | Bring the first-party packs into `packs/horizontal/everyday-brief` and `packs/vertical/finance/finance-policy-review` as `manifest.yaml`; add the finance edition; register active packs in `modules.json`. | Each manifest validates against the server's model; folder matches `vertical`; ids unique; editions name existing packs. |
| **4. Contracts and pack SDK** | Generate the manifest JSON Schema and the OpenAPI description of EvolvXSI routes into `packages/contracts`; build `packages/pack-sdk` (validate, build, sign). | Drift tests pass; a pack built and signed by the SDK installs on the server and has the same digest. |
| **5. When needed** | Tenancy decision, Kubernetes and cloud profiles, splitting the model gateway or indexer, a connector SDK. | Decided separately. |

## Consequences

- Imports of EvolvXSI modules change once (phase 2). Inherited code changes only where it already called our code.
- Contributors find our code by domain, and reviews can be assigned per folder.
- Pack authors work in `packs/` with a validator, and a vertical edition is a file, not a fork.

## Delivery

Phases 1–4 were delivered on 2026-11-14 in pull requests #94 (tidy), #95 (domains), #96 (packs as source) and the
phase 4 pull request (contracts and pack SDK), each with the tests listed above; details are in the
[review log](../REVIEW.md). Phase 5 items are done when a need arises.
