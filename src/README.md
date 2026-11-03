# EvolvXSI source workspace

Independent local Git repositories grouped by architecture responsibility. Each leaf listed below has its own `.git` directory and main branch. Group folders and this source container are not parent Git repositories.

| Path | Proposed remote name | Responsibility |
| --- | --- | --- |
| [apps/workspace](apps/workspace/README.md) | evolvxsi-workspace | Web workspace, chat, projects, agent studio, artifact editing and review screens. |
| [apps/control-plane](apps/control-plane/README.md) | evolvxsi-control-plane | Tenant and identity integration, tasks, registry, policies and approval decisions. |
| [platform/execution](platform/execution/README.md) | evolvxsi-execution | Execution API, run coordinator, agent harness, orchestration, checkpoints, artifacts and exports. |
| [platform/agents](platform/agents/README.md) | evolvxsi-agents | Shared versioned agent definitions and collaboration templates. |
| [platform/skills](platform/skills/README.md) | evolvxsi-skills | Shared versioned capability packages, dependencies, permissions and local evaluations. |
| [platform/hybrid](platform/hybrid/README.md) | evolvxsi-hybrid | Inference destination policy, provider adapters, routing, fallback, budgets and usage. |
| [platform/knowledge](platform/knowledge/README.md) | evolvxsi-knowledge | Ingestion, context assembly, retrieval, evidence, indexes and scoped memory. |
| [platform/integrations](platform/integrations/README.md) | evolvxsi-integrations | Shared tools, connectors, MCP adapters and connection health. |
| [platform/evaluations](platform/evaluations/README.md) | evolvxsi-evaluations | Cross-service regression suites, rubrics, runners and release reports. |
| [packages/pack-sdk](packages/pack-sdk/README.md) | evolvxsi-pack-sdk | Pack authoring and validation helpers consuming canonical contract schemas. |
| [packages/contracts](packages/contracts/README.md) | evolvxsi-contracts | Versioned API schemas, events, agent/skill/pack manifests and generated clients. |
| [infra/deployment](infra/deployment/README.md) | evolvxsi-deploy | Environment profiles, infrastructure, compatible release sets, monitoring and rollback. |

See [repositories.json](repositories.json) for the machine-readable inventory and [packs](packs/README.md) for the vertical template. No dependencies, code builds, remote repositories or initial commits were created.

Canonical product documents are independently versioned in [evolvxsi-docs](../docs/README.md), outside these 12 source repositories. See its [governance rules](../docs/07-implementation/EvolvXSI_Documentation-Governance.md) for release baseline pinning.
