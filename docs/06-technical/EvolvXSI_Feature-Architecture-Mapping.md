# EvolvXSI — feature and architecture mapping

Reviewed: 2026-11-05 · Status: ownership mapped; application features not implemented

The module skeletons in modules.json cover the proposed shared platform boundaries. Each currently contains a skeleton, not working product behavior. The vertical area contains a template rather than an active domain repository. This matrix records the primary owner and required collaborators so that coverage is not mistaken for implementation.

## Boxed architecture alignment

| Target box | Primary local paths from the repository root | Coverage |
| --- | --- | --- |
| Experience | apps/workspace | Chat, projects, studio, artifacts and review interface. |
| Vertical intelligence packs | packs/_template; future packs/vertical/<domain> | Domain-package template exists; first active vertical is undecided. |
| Horizontal agent platform | services/execution, packages/agents, packages/skills, services/knowledge, packages/integrations | Execution, definitions, capabilities, retrieval and tool boundaries exist. |
| Hybrid intelligence | services/model-gateway | Local/private/cloud adapters and policy-aware inference boundary. |
| Execution infrastructure | infrastructure | Storage, queue, compute, sandbox and operational configuration ownership. |
| Cross-cutting control plane | services/control-plane, evaluations | Authority and configuration; quality suites and release evidence. Every service enforces its own protected boundary. |
| Shared contracts and pack authoring | packages/contracts, packages/pack-sdk | Wire schemas and manifest contracts; authoring/validation helpers. |

## Core and horizontal feature ownership

| Feature | Primary owner from the repository root | Collaborators / boundary |
| --- | --- | --- |
| Chat, task intake and projects | apps/workspace | Control plane owns task/project records; execution owns runs. |
| Agent runtime, harness and orchestration | services/execution | Agents supply definitions; control plane grants activation and permission. |
| Durable execution, retries and recovery | services/execution | Deployment provisions queues/storage; execution owns checkpoints and idempotency. |
| Scheduling and event triggers | services/execution | Control plane owns tenant configuration; integrations handles provider subscriptions. |
| Agent Studio and workflow builder | apps/workspace | Control plane validates and publishes definitions; execution interprets workflows. Advanced builder scope remains later. |
| Agent definitions and collaboration patterns | packages/agents | Execution performs delegation; control plane owns tenant registry metadata. |
| Reusable skills | packages/skills | Domain skills belong in their pack; execution provides the permitted tool/sandbox environment. |
| Hybrid routing and model access | services/model-gateway | Control plane supplies policy; deployment provisions private inference. |
| Deterministic processing and human judgment | services/execution | Skills and tools supply deterministic functions; people review through workspace/control plane. |
| Context, RAG, citations and scoped memory | services/knowledge | Execution records artifact dependencies; workspace displays evidence. |
| Connectors, MCP and external tools | packages/integrations | Control plane authorizes access; execution binds invocation to the run and approval. |
| Code/browser/computer execution | services/execution | Deployment owns isolation infrastructure; integrations provides scoped external access. |
| Artifact generation, editing and export | services/execution | Skills render outputs; workspace provides editing/review; knowledge supplies provenance. |
| Team collaboration and handoff | apps/workspace | Control plane owns membership/sharing; execution checks acting authority on resumed work. |
| Approvals, tenant isolation and policy | services/control-plane | Execution enforces action binding; all APIs enforce tenant access independently. |
| Evaluation and reviewed improvement | evaluations | Skill/pack-local cases stay with their authors; control plane gates publication. No automatic production self-modification. |
| Traces, audit, metrics and cost views | services/control-plane | Execution/hybrid/knowledge/integrations emit records; deployment operates telemetry; workspace presents views. |
| Administration | apps/workspace | Control plane owns configuration and disable decisions; owning services apply revocation. |
| APIs, embedding and version compatibility | packages/contracts | Each service implements its APIs; workspace hosts supported embedded views. |
| Deployment, backups and release operations | infrastructure | Each service owns migrations and operating procedures; deployment pins compatible release sets. |
| Voice channel | apps/workspace | Future integrations and execution speech tools; excluded from the current report-workflow PRD. |

## First-workflow PRD traceability

| Requirement | Primary backend owner | Supporting modules |
| --- | --- | --- |
| FR-01 Task intake | services/control-plane | apps/workspace, packages/contracts |
| FR-02 Source ingestion | services/knowledge | packages/integrations, services/model-gateway, apps/workspace |
| FR-03 Access-aware retrieval | services/knowledge | services/control-plane, services/execution |
| FR-04 Evidence provenance | services/knowledge | services/execution, apps/workspace |
| FR-05 Agent workflow | services/execution | packages/agents, packages/skills, packages/contracts |
| FR-06 Human control | services/control-plane | services/execution, apps/workspace, packages/integrations |
| FR-07 Failure handling | services/execution | packages/integrations, infrastructure |
| FR-08 Model policy | services/model-gateway | services/control-plane, infrastructure |
| FR-09 History and cost | services/execution | services/model-gateway, services/control-plane, apps/workspace |
| FR-10 Evaluation | evaluations | Skill/pack owners, services/control-plane |
| FR-11 Export | services/execution | packages/skills, services/knowledge, apps/workspace |
| FR-12 Administration | services/control-plane | Owning services apply disable/revoke actions; workspace provides controls. |
| FR-13 Agent safety controls | services/control-plane | Execution enforces autonomy tiers and untrusted-content checks; the model gateway applies redaction and destination policy. |
| FR-14 Review inbox and notifications | apps/workspace | Control-plane supplies decisions and preferences; access is rechecked when an item is opened. |

## Vertical pack coverage

The template supplies agents, skills, workflows, tools, schemas, knowledge configuration, views, templates, policies, evaluations and tests. A validated pack manifest must be added after contracts are defined. Research, Bio, Pharma, Legal, Finance, Sales, Support, Engineering/IT, HR, Operations, Marketing and Healthcare Administration remain candidate packs. None is implemented or selected as the first release.

Each pack can reuse the same shared platform; it does not create its own identity, checkpoint, routing, or audit engine. Domain-specific integrations remain with the pack unless promoted into a reusable adapter with a single owner.

## Gaps and limits

All identified platform capabilities have a proposed owner. Runtime implementations, schemas, deployment manifests, CI pipelines and end-to-end tests remain to be built. Empty directory placeholders do not establish those capabilities. A first vertical, deployment profile and measurable release thresholds are still open. Voice and advanced studio/marketplace breadth are target capabilities rather than first-release requirements.

The pack SDK is part of the monorepo. The product commit versions canonical documents under docs/. Downloaded sources remain outside the product tree as references.

## Layer traceability for the first release

| Requirements | Primary layer | Observable acceptance |
| --- | --- | --- |
| FR-01 | L03 with L01 and L05 | Save an authorized draft with zero jobs. A separate start creates one run. |
| FR-02–04 | L06 with L04 and L08 | Retrieve permitted passages, cite their versions, and withhold affected content on revocation. |
| FR-05–07 | L05 with L02 and L04 | Run a pinned definition, honor exact-version approvals and recover without repeating completed writes. |
| FR-08 | L07 with L04 | Block prohibited model destinations before transmission. |
| FR-09–10 | L09 with L03 and L05 | Inspect history and compare immutable candidates on a fixed suite. |
| FR-11–12 | L01 with L03–L06 | Export only an approved accessible version and enforce disable decisions. |

L10 supplies the reproducible environment and recovery evidence for all requirements. See the [canonical layer map](EvolvXSI_System-Architecture.md#ten-engineering-layers).

## Platform feature ownership and delivery

Every catalog entry is planned. Primary owner means the module responsible for coordinating acceptance; collaborators retain their state and authorization boundaries. Phase mappings include prerequisites and distinguish a pilot subset from full expansion. Named people and selected release scope remain P00 decisions.

| Feature | Primary module | Collaborators | Delivery phases |
| --- | --- | --- | --- |
| PF-01.01 | `apps/workspace` | services/control-plane, services/execution | P02 |
| PF-01.02 | `apps/workspace` | services/knowledge, services/execution | P04, P06 |
| PF-01.03 | `apps/workspace` | services/execution, packages/identity-policy | P11 |
| PF-01.04 | `apps/workspace` | services/control-plane, packages/contracts, packages/integrations | P07 foundations; P11 full surfaces |
| PF-01.05 | `apps/workspace` | services/control-plane, evaluations, services/execution | P05 publication foundation; P11 self-service Studio |
| PF-01.06 | `apps/workspace` | services/control-plane, services/knowledge | P11 |
| PF-01.07 | `apps/workspace` | services/control-plane, infrastructure; commercial and support owners | P10 required rollout evidence; P11 full portals |
| PF-01.08 | `apps/workspace` | services/control-plane, services/execution | P06 |
| PF-01.09 | `apps/workspace` | services/control-plane, packages/integrations | P06 |
| PF-01.10 | `apps/workspace` | packages/ui, services/control-plane | P11C |
| PF-01.11 | `apps/workspace` | services/control-plane, packages/agents, evaluations | P11A |
| PF-01.12 | `apps/workspace` | packages/skills, services/control-plane | P11A |
| PF-01.13 | `apps/workspace` | services/execution, packages/integrations, services/model-gateway | Not scheduled; needs a separately scoped decision |
| PF-02.01 | `packages/agents` | packages/skills, services/control-plane, services/execution | P05 |
| PF-02.02 | `packages/pack-sdk` | packs/_template, packages/contracts, evaluations | P05 contracts; P09 selected active pack |
| PF-02.03 | `packages/pack-sdk` | services/control-plane, evaluations | P11 |
| PF-02.04 | `packages/skills` | packages/agents, packages/pack-sdk, packages/contracts | P11 |
| PF-02.05 | `packages/pack-sdk` | services/control-plane, packages/skills, packages/contracts | P11A |
| PF-02.06 | `packages/pack-sdk` | services/control-plane, evaluations, apps/workspace | P11B; public marketplace needs a separate decision |
| PF-03.01 | `packages/contracts` | services/control-plane, services/execution | P01, P02 |
| PF-03.02 | `services/control-plane` | evaluations, packages/contracts | P05 |
| PF-03.03 | `packages/contracts` | services/control-plane, services/execution, packages/integrations | P07, P11 |
| PF-03.04 | `packages/contracts` | services/control-plane, services/execution; planned apps/developer-portal | P11D |
| PF-03.05 | `services/control-plane` | apps/workspace, packages/agents, packages/integrations | P11A |
| PF-04.01 | `packages/identity-policy` | services/control-plane; every protected service | P01, P02 |
| PF-04.02 | `services/control-plane` | services/execution, services/knowledge, apps/workspace | P03, P04, P06 |
| PF-04.03 | `services/control-plane` | packages/identity-policy, infrastructure | P10 selected controls; P11 broader provisioning |
| PF-04.04 | `services/control-plane` | services/model-gateway, services/knowledge, services/execution | P03 |
| PF-04.05 | `services/execution` | packages/identity-policy, services/knowledge, evaluations | P03, P04 |
| PF-04.06 | `services/control-plane` | infrastructure, evaluations; compliance owner | P11E |
| PF-04.07 | `services/control-plane` | services/execution, packages/identity-policy, apps/workspace | P03 |
| PF-05.01 | `services/execution` | services/control-plane, packages/contracts | P02 |
| PF-05.02 | `services/execution` | services/control-plane, apps/workspace | P03, P06 |
| PF-05.03 | `services/execution` | packages/integrations, infrastructure | P03 isolation; P07 required automation; P11 breadth |
| PF-05.04 | `services/execution` | packages/agents, services/control-plane | P11G |
| PF-05.05 | `services/execution` | apps/workspace, services/control-plane | P11C |
| PF-05.06 | `services/execution` | packages/integrations, infrastructure | P11G |
| PF-06.01 | `services/knowledge` | packages/integrations, services/model-gateway | P04 |
| PF-06.02 | `services/knowledge` | services/model-gateway, services/control-plane | P04 scoped baseline; P11 broad retrieval and sharing |
| PF-06.03 | `services/knowledge` | packages/integrations, services/model-gateway, apps/workspace | P11C |
| PF-06.04 | `services/knowledge` | apps/workspace, services/control-plane | P11C |
| PF-06.05 | `services/knowledge` | apps/workspace, services/execution | P11C |
| PF-07.01 | `services/model-gateway` | services/execution | P02 fixture gate |
| PF-07.02 | `services/model-gateway` | services/execution, infrastructure | P02 live-route gate |
| PF-07.03 | `services/model-gateway` | services/control-plane, infrastructure | P02 baseline budget; P08 selected routes; P11 breadth |
| PF-07.04 | `services/model-gateway` | services/control-plane, infrastructure | P11F |
| PF-07.05 | `services/model-gateway` | evaluations, services/control-plane, infrastructure | P11F |
| PF-07.06 | `services/model-gateway` | services/control-plane, apps/workspace | P11F |
| PF-08.01 | `packages/integrations` | services/knowledge, services/control-plane | P04 |
| PF-08.02 | `packages/integrations` | services/execution, services/control-plane | P07 required tools; P11 ecosystem |
| PF-08.03 | `packages/integrations` | packages/contracts, services/control-plane, services/execution | P11D |
| PF-08.04 | `packages/integrations` | services/control-plane, services/execution, packages/skills | P11D |
| PF-08.05 | `packages/integrations` | services/control-plane, services/execution, apps/workspace | P11D |
| PF-09.01 | `services/execution` | services/control-plane, apps/workspace, infrastructure | P02 |
| PF-09.02 | `evaluations` | services/control-plane, packages/agents, packages/skills | P05 gate; P09 domain evidence |
| PF-09.03 | `services/control-plane` | apps/workspace, infrastructure; all event producers | P10 required alerts; P11 analytics |
| PF-09.04 | `evaluations` | services/execution, services/control-plane | P11F |
| PF-09.05 | `evaluations` | apps/workspace, services/execution, services/control-plane | P11F |
| PF-09.06 | `services/control-plane` | apps/workspace, services/execution | P11E |
| PF-09.07 | `services/control-plane` | services/model-gateway, services/execution; commercial owner | P11E |
| PF-10.01 | `infrastructure` | services/control-plane, apps/workspace, services/execution | P01 configuration; P02 running slice |
| PF-10.02 | `infrastructure` | all deployed services | P10 |
| PF-10.03 | `infrastructure` | services/model-gateway; all deployed services | P11 |
| PF-10.04 | `infrastructure` | services/control-plane; all deployed services | P11F |
| PF-10.05 | `infrastructure` | services/control-plane, services/model-gateway, services/execution, services/knowledge | P11F |
