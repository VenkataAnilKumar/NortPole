# EvolvXSI — source-to-repository mapping

> Current dependency direction (2026-11-02): downloaded projects are reference-only. Earlier fork, adapter-copy and runtime-selection suggestions below are historical candidates, superseded by [the provider SDK decision](EvolvXSI_Provider-SDK-Decision.md). Implement EvolvXSI-owned boundaries using official provider clients; no third-party agent platform is a required dependency.

Reviewed: 2026-11-02 · Status: implementation candidates; no source integrated

This document maps the actual local source snapshots to the 12 first-party repository skeletons. Evidence is directory-level inspection and selected READMEs, not a build, security review, or demonstrated extraction. Exact commits are pinned in [source inventory](../../sources/manifest.json); [machine-readable mapping](../../sources/reuse-map.json) records evidence paths and commit IDs.

## Repository mapping

| Target under src/ | Primary candidate/reference | Reuse approach |
| --- | --- | --- |
| apps/workspace | Sim application UI | Fork/extract candidate |
| apps/control-plane | Sim auth, organization and authorization modules | Selective reuse plus custom services |
| platform/execution | Sim executor as the first integration candidate | One primary runtime; alternatives evaluated separately |
| platform/agents | Agno agent/team definitions and Mini-Agent examples | Definition patterns and adapters |
| platform/skills | MiniMax skills | Adapt selected capability packages |
| platform/hybrid | Sim providers and Agno model adapters | Adapter reuse candidate |
| platform/knowledge | Onyx knowledge backend | Service integration candidate |
| platform/integrations | Sim tools/connectors and Opengeni gateway | Selected adapters behind EvolvXSI tool contracts |
| platform/evaluations | Agno/Onyx evaluation code and Sim testing helpers | Reference harnesses plus custom business suites |
| packages/pack-sdk | MiniApps plugin and Busabase package patterns | Reference plus new SDK |
| packages/contracts | Existing workflow/event contracts | Reference plus EvolvXSI-owned schemas |
| infra/deployment | Sim deployment assets plus service-specific upstream deployment | Adapt per selected component |

## Evidence and remaining work

### apps/workspace

[sim/apps/sim/app](../../sources/sim/apps/sim/app/) · [sim/apps/sim/components](../../sources/sim/apps/sim/components/) · [openagents-workspace/workspace/frontend](../../sources/openagents-workspace/workspace/frontend/)

Separate the UI from upstream server modules; preserve existing behavior during the first fork. MiniApps/OpenRoom provide domain-view patterns.

### apps/control-plane

[sim/packages/auth](../../sources/sim/packages/auth/) · [sim/packages/platform-authz](../../sources/sim/packages/platform-authz/) · [sim/apps/sim/lib/organizations](../../sources/sim/apps/sim/lib/organizations/) · [opengeni/packages/decisions](../../sources/opengeni/packages/decisions/)

Build the unified tenant registry, task API and approval-payload contract; existing tables cannot be shared across independently owned services.

### platform/execution

[sim/apps/sim/executor](../../sources/sim/apps/sim/executor/) · [sim/apps/sim/background](../../sources/sim/apps/sim/background/) · [sim/apps/sim/sandboxes](../../sources/sim/apps/sim/sandboxes/) · [agno/libs/agno/agno/workflow](../../sources/agno/libs/agno/agno/workflow/) · [opengeni/apps/worker](../../sources/opengeni/apps/worker/) · [minimax-code/packages/agent-runtime](../../sources/minimax-code/packages/agent-runtime/)

Prove checkpoint/recovery and approval semantics first. Agno and Opengeni are alternate runtimes; MiniMax Code/OpenAgentCore are optional coding backends, not concurrent owners of the same run.

### platform/agents

[agno/libs/agno/agno/agent](../../sources/agno/libs/agno/agno/agent/) · [agno/libs/agno/agno/team](../../sources/agno/libs/agno/agno/team/) · [minimax-mini-agent/mini_agent](../../sources/minimax-mini-agent/mini_agent/)

Define EvolvXSI manifests in contracts; do not copy framework agent objects into public APIs.

### platform/skills

[minimax-skills/skills](../../sources/minimax-skills/skills/) · [minimax-mini-agent/mini_agent/skills](../../sources/minimax-mini-agent/mini_agent/skills/)

Select document/report skills, declare dependencies and permissions, and validate output quality in isolated execution. Domain skills remain with their pack.

### platform/hybrid

[sim/apps/sim/providers](../../sources/sim/apps/sim/providers/) · [agno/libs/agno/agno/models](../../sources/agno/libs/agno/agno/models/) · [kortix/apps/llm-gateway](../../sources/kortix/apps/llm-gateway/)

EvolvXSI must own data-placement decisions, policy-preserving fallback, budgets and usage identity. Multiple model clients do not establish a working hybrid policy.

### platform/knowledge

[onyx/backend/onyx/indexing](../../sources/onyx/backend/onyx/indexing/) · [onyx/backend/onyx/document_index](../../sources/onyx/backend/onyx/document_index/) · [onyx/backend/onyx/file_processing](../../sources/onyx/backend/onyx/file_processing/) · [agno/libs/agno/agno/memory](../../sources/agno/libs/agno/agno/memory/) · [busabase/packages/busabase-core](../../sources/busabase/packages/busabase-core/)

Validate edition-specific source ACLs and derived-content access. Choose one scoped-memory owner; Busabase is an optional work-product data reference, not an extra mandatory store.

### platform/integrations

[sim/apps/sim/tools](../../sources/sim/apps/sim/tools/) · [sim/apps/sim/connectors](../../sources/sim/apps/sim/connectors/) · [opengeni/packages/tool-gateway](../../sources/opengeni/packages/tool-gateway/)

Adapt credentials, actor identity, approval binding, idempotency and provider rate limits. Source-ingestion connectors execute under knowledge ownership.

### platform/evaluations

[agno/libs/agno/agno/eval](../../sources/agno/libs/agno/agno/eval/) · [onyx/backend/onyx/evals](../../sources/onyx/backend/onyx/evals/) · [sim/packages/testing](../../sources/sim/packages/testing/)

Author pilot-specific cases and cross-service gates; framework unit tests do not prove EvolvXSI outcomes.

### packages/pack-sdk

[minimax-miniapps/plugins](../../sources/minimax-miniapps/plugins/) · [busabase/packages/busabase-package](../../sources/busabase/packages/busabase-package/)

Build EvolvXSI authoring/validation helpers; MiniApps desktop host plugins require adaptation to the chosen web extension boundary.

### packages/contracts

[sim/packages/workflow-types](../../sources/sim/packages/workflow-types/) · [opengeni/packages/contracts](../../sources/opengeni/packages/contracts/) · [minimax-agent-core/contracts](../../sources/minimax-agent-core/contracts/)

Define stable tenant-aware API/events and agent/skill/pack manifests. Compatibility with upstream internals must use explicit adapters.

### infra/deployment

[sim/docker](../../sources/sim/docker/) · [sim/helm](../../sources/sim/helm/) · [opengeni/deploy](../../sources/opengeni/deploy/) · [onyx/deployment](../../sources/onyx/deployment/)

Create a compatible deployment set, migration order, resource/network boundaries and recovery procedures. Compose files from unrelated products cannot simply be merged.

## All downloaded projects

| Source directory | Assigned role |
| --- | --- |
| [agno](../../sources/agno/) | Agent/model adapters and evaluation reference; alternate runtime candidate. |
| [busabase](../../sources/busabase/) | Structured work-product persistence and package authoring reference. |
| [kortix](../../sources/kortix/) | Workspace, inference-gateway and sandbox patterns; optional reference. |
| [minimax-agent-core](../../sources/minimax-agent-core/) | Optional coding-session/sandbox backend; protocol reference. |
| [minimax-code](../../sources/minimax-code/) | Optional coding harness and SDK backend; preserve one run authority. |
| [minimax-mini-agent](../../sources/minimax-mini-agent/) | Readable agent-loop, tool and skill reference. |
| [minimax-miniapps](../../sources/minimax-miniapps/) | Vertical interactive workspace and plugin-host reference. |
| [minimax-openroom](../../sources/minimax-openroom/) | Structured app actions and browser-local interface reference. |
| [minimax-skills](../../sources/minimax-skills/) | Selected report, office-document and multimodal skill candidates. |
| [onyx](../../sources/onyx/) | Knowledge/retrieval service candidate. |
| [openagents](../../sources/openagents/) | Different OpenAgents project; retained but excluded from the collaboration mapping. |
| [opengeni](../../sources/opengeni/) | Durable execution, approval and tool-gateway reference; alternate runtime. |
| [rerun](../../sources/rerun/) | Coworker/task-review UX reference; no core-service assignment. |
| [sim](../../sources/sim/) | Primary workspace/workflow base candidate; extraction still required. |
| [openagents-workspace](../../sources/openagents-workspace/) | Correct openagents.org collaboration workspace; supplemental workspace reference. |

## Vertical packs

The template can use shared platform contracts, selected MiniMax skills and MiniApps interface patterns. Domain data, schemas, review criteria and evaluation sets still require domain-specific sources. None of the downloaded generic platforms is a complete Bio, Legal, Finance or other vertical pack. The first domain remains undecided.

## Source identity correction

The earlier clone named sources/openagents points to OpenAgentsInc/openagents, whose local README describes a different project. The [GitHub link from openagents.org](https://openagents.org/) resolves to [openagents-org/openagents](https://github.com/openagents-org/openagents). The correct project is now downloaded at sources/openagents-workspace. The earlier checkout is retained and explicitly excluded. Any previous link to OpenAgentsInc as evidence for the collaboration product is superseded by this correction.

## Integration gates

Choose one runtime owner and one authoritative data owner per capability. Run a thin workflow against the proposed sources before extracting services. Verify tenant/actor propagation, approvals, source permissions, checkpoint recovery, artifact provenance and model destination policy. Forks retain upstream dependency boundaries until extraction is tested. No downloaded code has been copied into src/, dependencies installed, or builds started.


## Commercial reference research — 4 November 2026

The [commercial reference review](EvolvXSI_Commercial_Reference_Research.md) evaluates Temporal, Langfuse, LiteLLM, Qdrant, Infisical, Appsmith, E2B, Dify, n8n and Airbyte against named adoption evidence and product-module relevance. It records source-license boundaries and maps each study to an EvolvXSI design question. Temporal and LiteLLM were already mentioned in earlier research. All entries remain reference only. This review adds research candidates to the documentation. The downloaded-source manifest continues to describe only existing local snapshots.
