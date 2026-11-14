# EvolvXSI — source-to-module mapping

> Downloaded projects are reference only. EvolvXSI owns its runtime and contracts. See the [provider decision](EvolvXSI_Provider-SDK-Decision.md).

Reviewed: 2026-11-05 · Status: reference study

This document maps source snapshots to EvolvXSI modules. The external reference collection retains manifest.json and reuse-map.json for local provenance. The links below point to the recorded upstream commits.

## Module mapping

| Target from the repository root | Primary reference | Disposition |
| --- | --- | --- |
| apps/workspace | Sim application UI | Reference only |
| services/control-plane | Sim auth, organization and authorization modules | Reference only |
| services/execution | Sim executor | Reference only |
| packages/agents | Agno agent/team definitions and Mini-Agent examples | Reference only |
| packages/skills | MiniMax skills | Reference only |
| services/model-gateway | Sim providers and Agno model adapters | Reference only |
| services/knowledge | Upstream-core knowledge backend | Reference only |
| packages/integrations | Sim tools/connectors and Opengeni gateway | Reference only |
| evaluations | Agno/upstream-core evaluation code and Sim testing helpers | Reference only |
| packages/pack-sdk | MiniApps plugin and Busabase package patterns | Reference only |
| packages/contracts | Existing workflow/event contracts | Reference only |
| infrastructure | Sim deployment assets plus service-specific upstream deployment | Reference only |

## Evidence and remaining work

### apps/workspace

[sim/apps/sim/app](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb/apps/sim/app) · [sim/apps/sim/components](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb/apps/sim/components) · [openagents-workspace/workspace/frontend](https://github.com/openagents-org/openagents/tree/4178b1e4a84b7e54de1d4e7dbb1d87e7a7c793cf/workspace/frontend)

Study workspace navigation, collaboration and review patterns. Implement the EvolvXSI workspace through first-party APIs.

### services/control-plane

[sim/packages/auth](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb/packages/auth) · [sim/packages/platform-authz](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb/packages/platform-authz) · [sim/apps/sim/lib/organizations](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb/apps/sim/lib/organizations) · [opengeni/packages/decisions](https://github.com/Cloudgeni-ai/opengeni/tree/6af476612385066db6919c176809705017976d52/packages/decisions)

Build the unified tenant registry, task API and approval-payload contract; existing tables cannot be shared across separately owned service data.

### services/execution

[sim/apps/sim/executor](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb/apps/sim/executor) · [sim/apps/sim/background](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb/apps/sim/background) · [sim/apps/sim/sandboxes](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb/apps/sim/sandboxes) · [agno/libs/agno/agno/workflow](https://github.com/agno-agi/agno/tree/b21807bb6d86d2a62efeb42d492c04e566ee7f90/libs/agno/agno/workflow) · [opengeni/apps/worker](https://github.com/Cloudgeni-ai/opengeni/tree/6af476612385066db6919c176809705017976d52/apps/worker) · [minimax-code/packages/agent-runtime](https://github.com/MiniMax-AI/minimax-code/tree/39c1f42444c110cfeb770c8d64bf801dc727111c/packages/agent-runtime)

Prove checkpoint/recovery and approval semantics first. Agno and Opengeni are runtime-design references; MiniMax Code/OpenAgentCore are coding-session references. None is selected as an EvolvXSI runtime or backend.

### packages/agents

[agno/libs/agno/agno/agent](https://github.com/agno-agi/agno/tree/b21807bb6d86d2a62efeb42d492c04e566ee7f90/libs/agno/agno/agent) · [agno/libs/agno/agno/team](https://github.com/agno-agi/agno/tree/b21807bb6d86d2a62efeb42d492c04e566ee7f90/libs/agno/agno/team) · [minimax-mini-agent/mini_agent](https://github.com/MiniMax-AI/Mini-Agent/tree/d76a4f6389688cabda39c224a6cdfa274215d47c/mini_agent)

Define EvolvXSI manifests in contracts; do not copy framework agent objects into public APIs.

### packages/skills

[minimax-skills/skills](https://github.com/MiniMax-AI/skills/tree/60aaae52bb2af8162732751a4332f62a5fef518b/skills) · [minimax-mini-agent/mini_agent/skills](https://github.com/MiniMax-AI/Mini-Agent/tree/d76a4f6389688cabda39c224a6cdfa274215d47c/mini_agent/skills)

Select document/report skills, declare dependencies and permissions, and validate output quality in isolated execution. Domain skills remain with their pack.

### services/model-gateway

[sim/apps/sim/providers](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb/apps/sim/providers) · [agno/libs/agno/agno/models](https://github.com/agno-agi/agno/tree/b21807bb6d86d2a62efeb42d492c04e566ee7f90/libs/agno/agno/models) · [kortix/apps/llm-gateway](https://github.com/kortix-ai/suna/tree/68fd3646bca1a7af4aee50cd3c314f6225e86c35/apps/llm-gateway)

EvolvXSI must own data-placement decisions, policy-preserving fallback, budgets and usage identity. Multiple model clients do not establish a working hybrid policy.

### services/knowledge

`upstream/backend/upstream/indexing` · `upstream/backend/upstream/document_index` · `upstream/backend/upstream/file_processing` · [agno/libs/agno/agno/memory](https://github.com/agno-agi/agno/tree/b21807bb6d86d2a62efeb42d492c04e566ee7f90/libs/agno/agno/memory) · [busabase/packages/busabase-core](https://github.com/busabase/busabase/tree/a525be9c5e3d74a21eec022469f9973378a49448/packages/busabase-core)

Validate edition-specific source ACLs and derived-content access. Choose one scoped-memory owner; Busabase is an optional work-product data reference, not an extra mandatory store.

### packages/integrations

[sim/apps/sim/tools](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb/apps/sim/tools) · [sim/apps/sim/connectors](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb/apps/sim/connectors) · [opengeni/packages/tool-gateway](https://github.com/Cloudgeni-ai/opengeni/tree/6af476612385066db6919c176809705017976d52/packages/tool-gateway)

Adapt credentials, actor identity, approval binding, idempotency and provider rate limits. Source-ingestion connectors execute under knowledge ownership.

### evaluations

[agno/libs/agno/agno/eval](https://github.com/agno-agi/agno/tree/b21807bb6d86d2a62efeb42d492c04e566ee7f90/libs/agno/agno/eval) · `upstream/backend/upstream/evals` · [sim/packages/testing](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb/packages/testing)

Author pilot-specific cases and cross-service gates; framework unit tests do not prove EvolvXSI outcomes.

### packages/pack-sdk

[minimax-miniapps/plugins](https://github.com/MiniMax-AI/MiniMax-Code-MiniApps/tree/0f2183f14dd8b8ebffcd08ba42ad719a53a5f5b8/plugins) · [busabase/packages/busabase-package](https://github.com/busabase/busabase/tree/a525be9c5e3d74a21eec022469f9973378a49448/packages/busabase-package)

Build EvolvXSI authoring/validation helpers; MiniApps desktop host plugins require adaptation to the chosen web extension boundary.

### packages/contracts

[sim/packages/workflow-types](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb/packages/workflow-types) · [opengeni/packages/contracts](https://github.com/Cloudgeni-ai/opengeni/tree/6af476612385066db6919c176809705017976d52/packages/contracts) · [minimax-agent-core/contracts](https://github.com/MiniMax-AI/OpenAgentCore/tree/d5a9c31d18b11c07af01777cb09c4db099a051bd/contracts)

Define stable tenant-aware API/events and agent/skill/pack manifests. Compatibility with upstream internals must use explicit adapters.

### infrastructure

[sim/docker](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb/docker) · [sim/helm](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb/helm) · [opengeni/deploy](https://github.com/Cloudgeni-ai/opengeni/tree/6af476612385066db6919c176809705017976d52/deploy) · `upstream/deployment`

Create a compatible deployment set, migration order, resource/network boundaries and recovery procedures. Compose files from unrelated products cannot simply be merged.

## All downloaded projects

| Source directory | Assigned role |
| --- | --- |
| [agno](https://github.com/agno-agi/agno/tree/b21807bb6d86d2a62efeb42d492c04e566ee7f90) | Agent/model adapters and evaluation study; supplemental commercial evidence pending. |
| [busabase](https://github.com/busabase/busabase/tree/a525be9c5e3d74a21eec022469f9973378a49448) | Structured work-product persistence and package authoring reference. |
| [kortix](https://github.com/kortix-ai/suna/tree/68fd3646bca1a7af4aee50cd3c314f6225e86c35) | Workspace, inference-gateway and sandbox patterns; optional reference. |
| [minimax-agent-core](https://github.com/MiniMax-AI/OpenAgentCore/tree/d5a9c31d18b11c07af01777cb09c4db099a051bd) | Coding-session/sandbox protocol reference only. |
| [minimax-code](https://github.com/MiniMax-AI/minimax-code/tree/39c1f42444c110cfeb770c8d64bf801dc727111c) | Coding harness and SDK-boundary reference only. |
| [minimax-mini-agent](https://github.com/MiniMax-AI/Mini-Agent/tree/d76a4f6389688cabda39c224a6cdfa274215d47c) | Readable agent-loop, tool and skill reference. |
| [minimax-miniapps](https://github.com/MiniMax-AI/MiniMax-Code-MiniApps/tree/0f2183f14dd8b8ebffcd08ba42ad719a53a5f5b8) | Vertical interactive workspace and plugin-host reference. |
| [minimax-openroom](https://github.com/MiniMax-AI/OpenRoom/tree/02468154c4d99f8925916425bf444d672454fb3d) | Structured app actions and browser-local interface reference. |
| [minimax-skills](https://github.com/MiniMax-AI/skills/tree/60aaae52bb2af8162732751a4332f62a5fef518b) | Report, office-document and multimodal skill-design references only. |
| `upstream` | Knowledge/retrieval design reference only. |
| [openagents](https://github.com/OpenAgentsInc/openagents/tree/1e3a10fa8eb36856063769dbce311bd953491c4b) | Different OpenAgents project; retained but excluded from the collaboration mapping. |
| [opengeni](https://github.com/Cloudgeni-ai/opengeni/tree/6af476612385066db6919c176809705017976d52) | Durable execution, approval and tool-gateway design reference only. |
| [rerun](https://github.com/rerun-build/rerun/tree/a6d63a4b542674ddd002e51b39ba0df6e0807bcc) | Coworker/task-review UX reference; no core-service assignment. |
| [sim](https://github.com/simstudioai/sim/tree/093ea9ddb2f3e47facbc2dc42d4e523ba050dedb) | Primary workspace/workflow design reference; no extraction or fork selected. |
| [openagents-workspace](https://github.com/openagents-org/openagents/tree/4178b1e4a84b7e54de1d4e7dbb1d87e7a7c793cf) | Correct openagents.org collaboration workspace; supplemental workspace reference. |

## Vertical packs

The template uses EvolvXSI-owned shared contracts and skills. MiniMax skills and MiniApps interface patterns may inform study; their code/assets are not copied into the template. Domain data, schemas, review criteria and evaluation sets still require domain-specific sources. None of the downloaded generic platforms is a complete Bio, Legal, Finance or other vertical pack. The first domain remains undecided.

## Source identity correction

The earlier clone named sources/openagents points to OpenAgentsInc/openagents, whose local README describes a different project. The [GitHub link from openagents.org](https://openagents.org/) resolves to [openagents-org/openagents](https://github.com/openagents-org/openagents). The correct project is now downloaded at sources/openagents-workspace. The earlier checkout is retained and explicitly excluded. Any previous link to OpenAgentsInc as evidence for the collaboration product is superseded by this correction.

## Integration gates

Verify tenant and actor propagation, approvals, source permissions, recovery, artifact provenance and model destination policy through EvolvXSI acceptance cases. Keep downloaded projects outside the product build.


## Commercial reference research — 4 November 2026

The [commercial reference review](EvolvXSI_Commercial_Reference_Research.md) evaluates Temporal, Langfuse, LiteLLM, Qdrant, Infisical, Appsmith, E2B, Dify, n8n and Airbyte against named adoption evidence and product-module relevance. It records source-license boundaries and maps each study to an EvolvXSI design question. Temporal and LiteLLM were already mentioned in earlier research. All entries remain reference only. This review adds research candidates to the documentation. The downloaded-source manifest continues to describe only existing local snapshots.

## Layer mapping

Targets are modules within the [ten-layer architecture](../06-technical/EvolvXSI_System-Architecture.md#ten-engineering-layers). Preserve upstream paths and commit provenance separately from product module ownership.

## Confirmed implementation disposition

The owner reconfirmed reference-only implementation on 2026-11-05. All historical candidate/runtime/extraction descriptions are superseded. Sim and the upstream core are primary local product references under the selected evidence approach; remaining snapshots retain supplemental status until the commercial-evidence gate is met. Existence in this table is not commercial certification or permission to integrate code. Follow the [phase reference workstream](EvolvXSI_Implementation-Phases.md#reference-only-implementation-workstream); preserve local snapshot provenance separately from current upstream research.
