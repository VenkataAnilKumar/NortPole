# EvolvXSI — feature and architecture mapping

Reviewed: 2026-11-02 · Status: ownership mapped; application features not implemented

The 12 repositories in src/repositories.json cover the proposed shared platform boundaries. Each currently contains a skeleton, not working product behavior. The vertical area contains a template rather than an active domain repository. This matrix records the primary owner and required collaborators so that coverage is not mistaken for implementation.

## Boxed architecture alignment

| Target box | Primary local paths under src/ | Coverage |
| --- | --- | --- |
| Experience | apps/workspace | Chat, projects, studio, artifacts and review interface. |
| Vertical intelligence packs | packs/_template; future packs/<domain> | Domain-package template exists; first active vertical is undecided. |
| Horizontal agent platform | platform/execution, agents, skills, knowledge, integrations | Execution, definitions, capabilities, retrieval and tool boundaries exist. |
| Hybrid intelligence | platform/hybrid | Local/private/cloud adapters and policy-aware inference boundary. |
| Execution infrastructure | infra/deployment | Storage, queue, compute, sandbox and operational configuration ownership. |
| Cross-cutting control plane | apps/control-plane, platform/evaluations | Authority and configuration; quality suites and release evidence. Every service enforces its own protected boundary. |
| Shared contracts and pack authoring | packages/contracts, packages/pack-sdk | Wire schemas and manifest contracts; authoring/validation helpers. |

## Core and horizontal feature ownership

| Feature | Primary owner under src/ | Collaborators / boundary |
| --- | --- | --- |
| Chat, task intake and projects | apps/workspace | Control plane owns task/project records; execution owns runs. |
| Agent runtime, harness and orchestration | platform/execution | Agents supply definitions; control plane grants activation and permission. |
| Durable execution, retries and recovery | platform/execution | Deployment provisions queues/storage; execution owns checkpoints and idempotency. |
| Scheduling and event triggers | platform/execution | Control plane owns tenant configuration; integrations handles provider subscriptions. |
| Agent Studio and workflow builder | apps/workspace | Control plane validates and publishes definitions; execution interprets workflows. Advanced builder scope remains later. |
| Agent definitions and collaboration patterns | platform/agents | Execution performs delegation; control plane owns tenant registry metadata. |
| Reusable skills | platform/skills | Domain skills belong in their pack; execution provides the permitted tool/sandbox environment. |
| Hybrid routing and model access | platform/hybrid | Control plane supplies policy; deployment provisions private inference. |
| Deterministic processing and human judgment | platform/execution | Skills and tools supply deterministic functions; people review through workspace/control plane. |
| Context, RAG, citations and scoped memory | platform/knowledge | Execution records artifact dependencies; workspace displays evidence. |
| Connectors, MCP and external tools | platform/integrations | Control plane authorizes access; execution binds invocation to the run and approval. |
| Code/browser/computer execution | platform/execution | Deployment owns isolation infrastructure; integrations provides scoped external access. |
| Artifact generation, editing and export | platform/execution | Skills render outputs; workspace provides editing/review; knowledge supplies provenance. |
| Team collaboration and handoff | apps/workspace | Control plane owns membership/sharing; execution checks acting authority on resumed work. |
| Approvals, tenant isolation and policy | apps/control-plane | Execution enforces action binding; all APIs enforce tenant access independently. |
| Evaluation and reviewed improvement | platform/evaluations | Skill/pack-local cases stay with their authors; control plane gates publication. No automatic production self-modification. |
| Traces, audit, metrics and cost views | apps/control-plane | Execution/hybrid/knowledge/integrations emit records; deployment operates telemetry; workspace presents views. |
| Administration | apps/workspace | Control plane owns configuration and disable decisions; owning services apply revocation. |
| APIs, embedding and version compatibility | packages/contracts | Each service implements its APIs; workspace hosts supported embedded views. |
| Deployment, backups and release operations | infra/deployment | Each service owns migrations and operating procedures; deployment pins compatible release sets. |
| Voice channel | apps/workspace | Future integrations and execution speech tools; excluded from the current report-workflow PRD. |

## First-workflow PRD traceability

| Requirement | Primary backend owner | Supporting repositories |
| --- | --- | --- |
| FR-01 Task intake | apps/control-plane | apps/workspace, packages/contracts |
| FR-02 Source ingestion | platform/knowledge | platform/integrations, platform/hybrid, apps/workspace |
| FR-03 Access-aware retrieval | platform/knowledge | apps/control-plane, platform/execution |
| FR-04 Evidence provenance | platform/knowledge | platform/execution, apps/workspace |
| FR-05 Agent workflow | platform/execution | platform/agents, platform/skills, packages/contracts |
| FR-06 Human control | apps/control-plane | platform/execution, apps/workspace, platform/integrations |
| FR-07 Failure handling | platform/execution | platform/integrations, infra/deployment |
| FR-08 Model policy | platform/hybrid | apps/control-plane, infra/deployment |
| FR-09 History and cost | platform/execution | platform/hybrid, apps/control-plane, apps/workspace |
| FR-10 Evaluation | platform/evaluations | Skill/pack owners, apps/control-plane |
| FR-11 Export | platform/execution | platform/skills, platform/knowledge, apps/workspace |
| FR-12 Administration | apps/control-plane | Owning services apply disable/revoke actions; workspace provides controls. |

## Vertical pack coverage

The template supplies agents, skills, workflows, tools, schemas, knowledge configuration, views, templates, policies, evaluations and tests. A validated pack manifest must be added after contracts are defined. Research, Bio, Pharma, Legal, Finance, Sales, Support, Engineering/IT, HR, Operations, Marketing and Healthcare Administration remain candidate packs. None is implemented or selected as the first release.

Each pack can reuse the same shared platform; it does not create its own identity, checkpoint, routing, or audit engine. Domain-specific integrations remain with the pack unless promoted into a reusable adapter with a single owner.

## Gaps and limits

All identified platform capabilities have a proposed owner. Runtime implementations, schemas, deployment manifests, CI pipelines and end-to-end tests remain to be built. Empty directory placeholders do not establish those capabilities. A first vertical, deployment profile and measurable release thresholds are still open. Voice and advanced studio/marketplace breadth are target capabilities rather than first-release requirements.

The pack SDK is part of the created repository inventory. Canonical documents remain at workspace docs/ in the independent evolvxsi-docs repository, separate from the 12 source repositories. Sources are reference checkouts, not integrated production dependencies.
