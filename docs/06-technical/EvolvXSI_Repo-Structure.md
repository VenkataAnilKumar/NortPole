# EvolvXSI — repository structure

Status: local repository skeletons created; implementation and builds paused · Updated: 2026-11-02

## Workspace layout

Use independent Git repositories grouped by responsibility under src/. Group folders are local containers. Each active leaf is an independent local repository; CI pipelines and releases will be added during implementation. Local paths are short; remote repository names retain the evolvxsi- prefix. The src/ layout is created with 12 independent local repositories. No remotes or initial commits exist. packs/_template/ supplies the vertical directory template; the first active domain remains undecided.

```text
EvolvXSI/
  README.md
  docs/                              Canonical product and architecture documents
  sources/                           Downloaded upstream reference checkouts
  src/
    apps/
      workspace/
      control-plane/
    platform/
      execution/
      agents/
      skills/
      hybrid/
      knowledge/
      integrations/
      evaluations/
    packs/
      <domain>/                      One repository per active vertical
    packages/
      pack-sdk/
      contracts/
    infra/
      deployment/
```

The workspace and grouping folders do not track child repository source in a parent Git index. Keep docs/ as the canonical documentation location and independent evolvxsi-docs Git repository. It is separate from the 12 source repositories. sources/ is reference material and is excluded from product builds.

## Repository ownership

| Local path under src/ | Remote repository | Architecture layer and responsibility |
| --- | --- | --- |
| apps/workspace | evolvxsi-workspace | Experience: chat, projects, studio, artifact editor and review screens. |
| apps/control-plane | evolvxsi-control-plane | Cross-cutting control: identity integration, tenants, tasks/projects, configuration, registry, policy and approval decisions. |
| platform/execution | evolvxsi-execution | Horizontal: runtime, harness, orchestration, scheduling, workflows, checkpoints, artifact versions and exports. |
| platform/agents | evolvxsi-agents | Horizontal: shared agent definitions and collaboration templates. |
| platform/skills | evolvxsi-skills | Horizontal: shared capability packages and skill-local evaluations. |
| platform/hybrid | evolvxsi-hybrid | Hybrid intelligence: model adapters, placement policy, routing, fallback, budgets and usage. |
| platform/knowledge | evolvxsi-knowledge | Horizontal: context, retrieval, scoped memory, ingestion, evidence and source permissions. |
| platform/integrations | evolvxsi-integrations | Horizontal: tools, connectors, MCP adapters and connection health. |
| platform/evaluations | evolvxsi-evaluations | Cross-cutting quality: cross-service suites, rubrics and release reports. |
| packs/<domain> | evolvxsi-pack-<domain> | Vertical: domain agents, skills, workflows, tools, schemas, views, templates and evaluations. |
| packages/pack-sdk | evolvxsi-pack-sdk | Pack authoring helpers, validation tooling and host adapter interfaces. |
| packages/contracts | evolvxsi-contracts | API/event schemas, manifests, compatibility rules and generated clients. |
| infra/deployment | evolvxsi-deploy | Infrastructure: environment profiles, compatible release sets, monitoring and rollback. |

Runtime, harness, orchestration and workflows remain internal execution modules initially. Context and memory remain internal knowledge modules. Control-plane policy is enforced locally at every protected service boundary. No service reads another service's business tables.

## Service repository template

```text
<service>/
  src/
    api/
    application/
    domain/
    infrastructure/
  migrations/
  tests/
    contracts/
    integration/
    e2e/
  deploy/
  docs/
  .github/workflows/
  README.md
```

Adapt this template to the implementation language. Build EvolvXSI-owned modules and use official provider clients behind internal adapters. Each service owns its tests, migrations and operating instructions. Cross-service tests belong with evaluation or deployment verification rather than a central implementation test directory.

## Agent and skill repositories

```text
platform/agents/
  agents/<agent-name>/
    agent.yaml
    instructions.md
    evaluations/
  tests/

platform/skills/
  skills/<skill-name>/
    skill.yaml
    SKILL.md
    schemas/
    scripts/
    templates/
    evaluations/
  tests/
```

Agents pin skill/tool versions, limits and model requirements. Skill manifests declare schemas, dependencies, permissions and runtime compatibility. The contracts repository owns canonical manifest schemas. The pack SDK consumes those schemas rather than duplicating them. Agents and skills publish immutable packages; they do not each require a service. Customer secrets and tenant configuration stay outside these packages.

## Vertical repository template

```text
packs/<domain>/
  pack.yaml
  agents/
  skills/
  workflows/
  tools/
  schemas/
  knowledge/
  views/
  templates/
  policies/
  evaluations/
  tests/
  README.md
```

knowledge/ stores domain schemas and configuration, not customer data. Domain definitions live with their pack; shared agents and skills are referenced by released version. Packs request permissions and cannot override tenant policy. Views use a controlled host interface. The first vertical remains undecided; create only the selected pack when work starts.

## Release and dependency rules

- Each leaf repository will have independent ownership, CI and versioned releases; current skeletons have no CI configuration or releases.
- Services communicate through authenticated APIs and events; package consumers pin released versions.
- No cross-repository relative imports or shared business-table access.
- Deployment configuration pins a tested compatible set of services, agents, skills and packs.
- Contracts own wire schemas; pack SDK owns authoring helpers; service repositories own business behavior.
- One repository can produce multiple processes, such as execution API, coordinator and worker.
- A package repository may require no deployed service.
- Provider and infrastructure dependency selections are recorded in decision/reference documents. Downloaded platforms remain reference-only.
- Release manifests pin the documentation commit and its approval record, following [documentation governance](../07-implementation/EvolvXSI_Documentation-Governance.md).

## Creation sequence

All 12 shared-platform repository skeletons are created. Begin implementation with contracts, deployment, workspace, control plane, execution and one chosen vertical. Populate the existing agents, skills, hybrid and knowledge skeletons as those capabilities are implemented. Add pack SDK helpers when pack authoring needs them. Connectors can start as packaged adapters and gain separate service deployment for load or credential isolation. Populate the existing evaluations repository with shared cross-service suites.

The repository map does not require creating every project immediately. See the [system architecture](EvolvXSI_System-Architecture.md) and [deployment architecture](EvolvXSI_Deployment-Architecture.md) for runtime responsibilities and data ownership.

See [feature and architecture mapping](EvolvXSI_Feature-Architecture-Mapping.md) for detailed feature ownership.


## Current implementation direction

EvolvXSI owns the service logic and public contracts. Use official provider clients behind internal adapters. Downloaded application and agent-framework sources are reference material; earlier extraction suggestions are not selected dependencies. The optional agent-loop SDK choice remains separate from the API client choice. See the [dependency decision](../07-implementation/EvolvXSI_Provider-SDK-Decision.md).

## Learning environment ownership

[Learning environments](EvolvXSI_Learning-Environments.md) initially use contracts, evaluations, execution and domain packs. A future platform/learning repository is conditional on approved training scope; it is not created or included in the current 12-repository inventory.
