# EvolvXSI repository structure

Updated: 2026-11-05. Status: approved structural direction; module skeletons only.

## Structure and ownership

One modular monorepo preserves the existing product history and original documents. Services can deploy and scale independently. Engineering layers define ownership, not a requirement for ten processes or repositories.

| Location | Responsibility | Current scope |
| --- | --- | --- |
| apps/workspace | Unified workspace, Studio, admin and operations feature areas | Existing skeleton |
| apps/developer-portal | Developer guides, API examples and extension discovery | Planned; create when implemented |
| apps/public-site | Product, trust and support entry points | Planned; create when implemented |
| services/control-plane | Public API, tenant membership, projects, drafts, registry, policy and approval records | Existing API skeleton moved here |
| services/execution | Runs, jobs, outbox, checkpoints, scheduling, artifacts and exports | Existing skeleton |
| services/knowledge | Ingestion, source permissions, retrieval, citations and scoped memory | Existing skeleton |
| services/model-gateway | Inference adapters, destination checks, routing, budgets and usage | Existing skeleton |
| packages/contracts | Canonical public API, event and pack manifest schemas | Existing skeleton |
| packages/identity-policy | Shared identity verification and policy enforcement primitives | Existing skeleton |
| packages/ui | Accessible components and design tokens | Existing skeleton |
| packages/agents, packages/skills | Shared immutable definitions and reusable capabilities | Existing skeletons |
| packages/integrations, packages/pack-sdk | Tool/source adapters and pack authoring/validation | Existing skeletons |
| packages/telemetry, packages/testing | Shared instrumentation and test utilities | Planned; create when required |
| packs/_template | Common pack authoring template | Template only |
| packs/horizontal, packs/vertical | Domain-neutral and domain-specific bundles | Planned namespaces; no active packs |
| sdks | Supported external clients using canonical contracts | Planned; select languages from demand |
| evaluations | Runner, shared suites, synthetic fixtures, rubrics and evaluation formats | Existing skeleton; runners renamed runner |
| tests | Cross-module contract, integration, end-to-end, security and resilience checks | Planned; local tests remain with modules |
| infrastructure | Local setup, reusable modules, profiles, observability and releases | Existing skeletons aligned to target names |
| tools | Repository maintenance and validation | Structure validator available |
| examples | Supported integration and pack examples | Planned |
| docs | Original numbered documents, decisions and operational runbooks | Original documents retained; decision recorded |

The [module inventory](../../modules.json) distinguishes existing skeletons from planned modules. Do not create empty future applications or mark capabilities implemented because their folders exist.

## Service layout

```text
services/<service>/
  src/
    domain/          # Business rules
    application/     # Use cases
    interfaces/      # API and event consumers
    adapters/        # Storage and external systems
    entrypoints/     # API/worker/scheduler processes, added as needed
  migrations/        # Only service-owned records
  tests/             # Service-local verification
  README.md
```

Execution workers and ingestion workers remain owned by their respective service, even when deployed separately. Model serving capacity may be external to the gateway and selected through deployment profiles. Existing auxiliary docs, deploy and test folders are preserved. Repository workflows will live in root .github/workflows; nested workflow placeholders are legacy scaffolding, not active CI.

## Dependency and state rules

Applications and services consume shared packages. Packages must not import applications or service internals. A pack depends on public extension contracts and declared capabilities. Service-to-service access uses explicit APIs/events; no cross-service table writes or direct imports of another service's business implementation.

Control plane owns task drafts and configuration; execution owns atomic run/job/outbox creation and artifact history; knowledge owns source versions and retrieval state. Each owner supplies migrations and recovery procedures. A shared physical database is possible initially with separate ownership and credentials; it does not grant unrestricted table access.

Canonical wire and manifest schemas live in packages/contracts. Evaluation-local rubrics and formats live in evaluations; published evaluation event contracts remain canonical. SDKs consume or generate from canonical contracts rather than defining competing schemas.

## Packs

Target: packs/horizontal/<name> and packs/vertical/<name>. Both use manifest.yaml, agents/, skills/, workflows/, schemas/, templates/, knowledge/, tools/, views/, policies/, evaluations/ and tests/ as applicable. The manifest schema is a P01/P05 deliverable, so no executable manifest is fabricated now.

Horizontal bundles package reusable workflows; vertical bundles reference them and add domain rules. Compatibility, dependency digests, requested permissions and evaluations are checked before tenant activation. Pack policies cannot grant authority. Customer records never belong in pack folders.

## Scaling and release rules

- Scale API processes and worker pools separately by measured demand; use bounded concurrency, tenant quotas and queue admission controls.
- Isolate untrusted tools/code with scoped credentials, network restrictions and resource limits. Directory separation is not a security boundary.
- Keep Studio, administration and operations inside the workspace initially. Extract a portal only for a demonstrated release, access or ownership need.
- CI checks changed modules and dependent consumers, plus required release-wide security and end-to-end gates. Root workflows and real dependency declarations are implementation work.
- Release manifests pin component artifacts, pack versions, contract compatibility, evaluation evidence and the documentation commit. Restore compatible sets during rollback.
- Assign named owners in P00 before introducing enforceable CODEOWNERS rules. Do not invent team identities.

## Migration and verification

The existing API skeleton moves from the former apps location to services/control-plane. Each service's src/api becomes src/interfaces and src/infrastructure becomes src/adapters. Infrastructure environments, infrastructure and monitoring directories become profiles, modules and observability respectively. evaluations/runners becomes evaluations/runner. These are ownership-preserving moves; existing files and placeholders remain intact.

Run `python tools/validate_structure.py` using the available Python runtime to check existing/planned inventory entries, maturity, responsibilities, service layouts, active-pack paths and inline local Markdown links. Run `python -m unittest discover -s tools/tests` for checker regression tests. Dependency, build, cache and Git directories are excluded. Link checks support inline links and heading fragments; reference-style links, raw HTML anchors and full Markdown parsing are outside this lightweight checker. It does not inspect code dependencies or enforce service isolation. This validates documentation/layout only. No application build, dependency installation or runtime readiness is implied.

Upstream source snapshots remain outside the product tree and reference-only. See [source mapping](../07-implementation/EvolvXSI_Source-Repository-Mapping.md). No NorthWritX dependency is introduced.

See the [ten engineering layers](EvolvXSI_System-Architecture.md#ten-engineering-layers) and [structure decision](../decisions/0001-modular-monorepo.md).

## Inventory conventions and preserved scaffolding

Existing modules have a repository-relative path, responsibility, implemented flag and maturity (skeleton or implemented). Future modules use maturity planned and implemented false. Paths are unique across both lists. Active packs are repository-relative paths beneath packs/horizontal or packs/vertical, each with manifest.yaml; manifest contents will be validated against the future canonical schema.

The current local profile is infrastructure/profiles/local; staging and production are placeholder profiles, not validated deployment offerings. No separate infrastructure/local folder is needed now. Existing infrastructure/containers, evaluations/reports and evaluations/rubrics remain owned scaffolding. Reports must use synthetic/redacted data and exclude customer records and secrets. Named deployment profiles and evaluation formats are added only with their implementation.

Responsibility fields describe capability ownership; they are not assigned people or a machine-enforced dependency graph. Named owners, dependency manifests and affected-consumer CI remain P00/P01 deliverables.
