# EvolvXSI — product definition

Status: **draft; first market not selected** · Updated: 2026-11-04

## Definition

EvolvXSI is a proposed governed agent workflow product. Its horizontal platform supplies task intake, permission-aware knowledge access, agent execution, model and tool policy, human approval, evidence, evaluation, and run operations. Vertical solutions add a specific domain's tasks, tools, output formats, policies, and evaluation cases.

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

EvolvXSI owns these product contracts. Downloaded open-source projects are design references only.

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
