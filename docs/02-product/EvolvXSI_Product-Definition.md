# NortPole — product definition

> **Where this lives in code (2026-11-14).** Service and package names here (`services/control-plane`, `services/execution`, `services/knowledge`, `packages/*`, `evaluations`) are logical owners from the design stage. [Decision 0006](../decisions/0006-scalable-repository-structure.md) maps them to the code: the three services are implemented inside `services/core`, and the packages and evaluations are planned modules in `modules.json`, created when their first code arrives.

Status: **draft; first market not selected** · Updated: 2026-11-05

## Definition

NortPole is a proposed governed agent workflow product. Its horizontal platform supplies task intake, permission-aware knowledge access, agent execution, model and tool policy, human approval, evidence, evaluation, and run operations. Vertical solutions add a specific domain's tasks, tools, output formats, policies, and evaluation cases.

The product is valuable when a team can complete a real workflow with less effort while retaining the ability to inspect evidence, correct errors, and control consequential actions.

## Product structure

| Layer | Customer-facing outcome | Scope rule |
| --- | --- | --- |
| Workspace | Start, review, and find tasks and outputs. | One consistent experience across workflows. |
| Workflow service | Run versioned tasks with checkpoints and approval. | One execution record per run. |
| Knowledge and tools | Retrieve permitted information and perform approved actions. | Enforce the user's effective access rights. |
| Model access | Use approved inference destinations within budget and quality rules. | Deny prohibited destinations before transmission. |
| Trust and operations | Show evidence, status, errors, feedback, and evaluation. | Make outcomes reviewable and supportable. |
| Vertical solution | Package domain workflows and evaluation. | Shares platform identity, audit, and policy controls. |

## What users can do across the horizontal platform

| Product area | First workflow | Broader product direction |
| --- | --- | --- |
| Unified workspace | Start a task, reopen its run, inspect evidence, and approve an output. | Move between chat, team libraries, tasks, and shared artifacts. |
| Agent and Automation Studio | An owner publishes one tested workflow version. | Authors configure agents, test skills, schedule automations, inspect failures, and disable a schedule. |
| Knowledge and context | Retrieve permitted passages from one source and preserve citation locations. | Manage shared libraries and memory with explicit user, project, and tenant scopes. |
| Hybrid model access | Apply the administrator's destination policy before processing content. | Choose among local, private, and cloud routes within the same policy, including during fallback. |
| Secure agent runtime | Show progress, pause for review, and recover interrupted work. | Delegate bounded tasks and run approved tools with scoped access. |
| Enterprise admin | Grant access, configure destinations, and disable a workflow or connector. | Manage team policy, spend, and audit history across workflows. |
| Developer portal | Document how an authorized caller starts a task and reads its result. | Provide worked integration examples and versioned extension contracts. |
| Observability and evaluation | Inspect run history and compare workflow versions on a fixed set of tasks. | Compare quality, cost, and recovery across teams and deployments. |

NortPole owns these product contracts. Downloaded open-source projects are design references only.

## Product coverage and engineering ownership

| Product coverage area | Engineering layers |
| --- | --- |
| Core product modules | L01 workspace, L02 definitions, L03 control plane, L06 knowledge |
| Discover, Create, Automate and Customize | L01 user journeys backed by L02 and L05–L08 |
| Models and inference | L07 gateway, L04 destination policy, L10 serving placement |
| Data and retrieval | L06 knowledge, L08 connectors, L04 authorization |
| Agent runtime and orchestration | L05 execution, L02 definitions, L04 approvals |
| Portals and surfaces | L01, with role-specific capabilities from all layers |
| Security and governance | L04 policy, enforced by the owning service |
| Deployment | L10 operations, with placement controlled separately for L07 inference |
| Integrations and ecosystem | L08 adapters and extension interfaces, L03 contracts |
| Vertical solutions and go-to-market | L02 pack definitions, L01 distribution, L09 pilot evidence and a commercial workstream |

The first offer proves a reviewed, cited deliverable for one team. The industry, customer source and deployment profile remain open. See the [ten engineering layers](../06-technical/EvolvXSI_System-Architecture.md#ten-engineering-layers) and [portal inventory](../05-design/EvolvXSI_UI-Spec.md#portal-and-surface-inventory-l01).

## Initial offer hypothesis

Sell a complete, configured workflow to an organization, with the shared platform visible as the way to operate and extend it. The first workflow in the PRD is an **example research report workflow**. It remains a candidate until discovery confirms a user, buyer, source system, report type, and measurable pain.

## Personas and decisions

| Persona | Needs to accomplish | Decisions they control |
| --- | --- | --- |
| Practitioner | Complete and review a task using trustworthy evidence. | Scope, edits, final approval. |
| Workflow owner | Define what good output means and manage process changes. | Workflow rules, evaluation criteria, rollout. |
| Administrator | Keep access, tools, model destinations, and runs within policy. | Connections, roles, permissions, publication. |
| Buyer | Fund a measurable outcome. | Pilot purchase, expansion, renewal. |

## First-release scope

The first release includes one configured workflow, one selected source type, task history, evidence-linked output, human review, policy-controlled model and tool access, export, and a repeatable evaluation set. The precise source and artifact depend on the selected market. Release acceptance is detailed in [EvolvXSI_First-Workflow-PRD.md](../04-specs/EvolvXSI_First-Workflow-PRD.md).

## Product principles

1. Start with a user outcome and measure it against the current process.
2. Preserve permission and provenance throughout the run.
3. Put human approval where an action or final artifact has material consequences.
4. Make failures, uncertainty, and unsupported claims visible.
5. Share platform controls across vertical solutions.
6. Add capabilities when the chosen workflow demonstrates a need.

## Commercial hypothesis

Test a recurring platform fee plus a usage metric tied to completed work, with deployment or integration services when needed. Pricing, packaging, buyer, and procurement model require discovery. Do not present a price list until costs and willingness to pay are measured.

## Definition of success

The first customer can repeatedly complete the selected workflow with an acceptable quality and security profile, lower effort than its baseline, and operating economics that support a paid deployment. A second workflow should demonstrate that shared platform capabilities reduce delivery effort.

## Decisions to close

First customer segment; workflow; practitioner and buyer; deployment location; permitted data destinations; artifact standard; approval policy; baseline and target; visual identity.

## Product feature scope

The [platform feature catalog](../04-specs/EvolvXSI_Feature-Spec.md#full-platform-feature-catalog) separates the engineering fixture, customer pilot and expansion features across all ten layers.

## Horizontal and vertical packs

Horizontal packs bundle domain-neutral capabilities such as evidence briefing or document comparison for reuse across teams. Vertical packs add domain terminology, workflows, templates, tool mappings, reviewer rules and evaluation cases. Both use the same versioned manifest, compatibility checks, evaluation gate and tenant activation rules. Neither owns a separate identity, runtime, gateway or audit system.

PF-02.04 records horizontal-pack expansion acceptance; the first pilot uses selected shared agents and skills plus one selected vertical pack. Existing `packages/agents`, `packages/skills` and `packages/pack-sdk` own shared definitions and validation. Physical bundle layout is decided when contracts are implemented; no new repository or active pack is implied by this proposal.
