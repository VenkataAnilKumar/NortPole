# EvolvXSI — UI specification

Status: **platform surfaces and proposed first-workflow screens** · Updated: 2026-11-05

## Portal and surface inventory (L01)

| Surface | Audience and primary job | Delivery scope |
| --- | --- | --- |
| Unified Workspace | Practitioners start tasks, inspect evidence, and reopen results. | First workflow |
| Review & Approval | Reviewers request changes or approve the exact artifact version. | First workflow, within Workspace |
| Enterprise Admin | Admins grant workflow and source access, configure destinations and inspect audit records. | Basic controls first; enterprise provisioning later |
| Run Operations & Evaluation | Operators diagnose failures; authors compare candidates before publication. | Run history first; full diagnostics and evaluation views later |
| Agent & Automation Studio | Authors define, test, publish, schedule and disable workflows. | One configured workflow first; self-service authoring later |
| Developer Portal | Developers start authorized runs and inspect results using documented contracts. | API contract first; quickstarts, webhooks and SDK guides later |
| Deployment Console | Customer operators manage health, upgrades and recovery. | When the selected deployment needs customer operation |
| Public Website & Demo | Buyers discover capabilities and evaluate a governed workflow. | Commercial rollout |
| Trust & Legal Center | Buyers and security teams inspect deployment and data commitments. | Commercial rollout, with claims matched to verified evidence |
| Support Console | Authorized support staff manage entitlements, rollout and support cases. | Controlled customer rollout |
| Embedded Experiences | Users interact through Slack, Teams or customer applications. | Start with status and links; add actions after channel authorization is verified |

Use the same tenant policies and run contracts across these surfaces. Pack views use a controlled host interface and receive only authorized records and actions.

## Navigation

Primary areas: **Tasks**, **Sources**, **Workflows**, and **Operations**. Practitioners see Tasks and their permitted sources. Workflow owners see evaluation and version controls. Administrators see connection, policy, and operations controls. Navigation must reflect permission; hiding a link does not replace server authorization.

## Screen inventory

| Screen | Main content | Primary action | Required states |
| --- | --- | --- | --- |
| Task list | Owned and shared tasks, status, owner, update time, search. | Create draft. | Empty, loading, results, error. |
| New task | Question, scope, desired output, source constraints. | Save draft. | Valid, incomplete, denied, unavailable workflow. |
| Task detail | Progress, plan, evidence, drafts, comments, activity. | Continue current step. | Planning, waiting, running, failed, draft ready, approved. |
| Plan review | Outline, source coverage, gaps, editable scope. | Accept plan. | Pending, changed, accepted, rejected. |
| Evidence view | Claim, source title, passage, location, date, access state. | Open source. | Available, stale, missing, access removed. |
| Draft review | Structured artifact, claim links, revisions, comments. | Approve or request revision. | Draft, revision pending, rejected, approved. |
| Source admin | Connection status, permissions, last refresh, errors. | Connect or disable source. | Connected, syncing, partial, failed, disabled. |
| Workflow admin | Versions, policy, evaluation summary, publication. | Publish version. | Draft, evaluating, failed gate, published, disabled. |
| Run operations | Searchable run list, steps, error category, cost estimate. | Inspect or retry. | Healthy, waiting, failed, completed. |

## Task detail layout

Use a clear task header with status and owner, a main artifact area, and a side panel for evidence and run activity. Keep the current action visible. When a user selects a claim, show the exact linked passage and its source location. When source access has changed, withhold the affected artifact until its access can be revalidated or its content safely regenerated.

## Workspace review flow

A question becomes a saved draft. Show an explicit Start action before creating a run. In the result view, selecting a claim opens its source passage and version. Mark an unsupported finding in plain language. Keep revision and approval actions beside the version under review. On a later visit, show whether that version is approved and whether its sources are still accessible. A restricted item should expose a useful status without revealing its title or text when those are protected.

## Interaction rules

- Show what the agent will do before the user starts a consequential run.
- Display explicit waiting states for plan review, tool approval, and final approval.
- Separate **Save draft**, **Request revision**, **Reject**, and **Approve** actions.
- Require approval for every first-release external write; summarize target and payload. Changed arguments require fresh approval.
- Keep user edits distinct from generated text in version history.
- Never show a success toast before the server confirms the action.

## Accessibility and content

All main flows must be keyboard usable. Controls have visible labels and focus states. Status uses text and icon, never color alone. Errors identify the affected step and a recovery action. Evidence links must have meaningful names. Avoid animated progress that obscures whether the run is actually active. Select the accessibility standard and test method during delivery planning.

## Responsive behavior

At narrow widths, stack the evidence panel beneath the artifact and preserve a way to jump between a claim and source. The approval action remains clear, but never becomes a floating button that hides report content.

## Open design decisions

Artifact format, source citation style, plan-review timing, collaboration model, mobile priority, and whether a dedicated agent studio is needed for the first customer.

## Feature coverage by surface

| Surface group | Feature references |
| --- | --- |
| Workspace and review | PF-01.01–03, PF-01.06, PF-01.08–01.10, PF-01.12, PF-04.02, PF-05.05, PF-06.01, PF-06.03–06.05 |
| Studio | PF-01.05, PF-01.11, PF-02.01–06, PF-03.02, PF-03.05, PF-05.03, PF-09.02, PF-09.04 |
| Enterprise Admin | PF-03.05, PF-04.01–07, PF-07.03–07.06, PF-08.01–02, PF-08.05, PF-10.04 |
| Developer Portal and embedded channels | PF-01.04, PF-01.13, PF-03.03–03.04, PF-08.02–08.04 |
| Public Website, Trust Center and Support Console | PF-01.07, PF-04.06 |
| Run Operations and Deployment Console | PF-09.01–09.07, PF-10.02–10.05 |

The [feature catalog](../04-specs/EvolvXSI_Feature-Spec.md#full-platform-feature-catalog) specifies what each capability must demonstrate. The portal inventory also covers public, trust and support surfaces for rollout.
