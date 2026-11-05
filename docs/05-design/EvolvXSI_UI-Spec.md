# EvolvXSI — UI specification

Status: **proposed screens for the candidate first workflow** · Updated: 2026-11-04

## Navigation

Primary areas: **Tasks**, **Sources**, **Workflows**, and **Operations**. Practitioners see Tasks and their permitted sources. Workflow owners see evaluation and version controls. Administrators see connection, policy, and operations controls. Navigation must reflect permission; hiding a link does not replace server authorization.

## Screen inventory

| Screen | Main content | Primary action | Required states |
| --- | --- | --- | --- |
| Task list | Owned and shared tasks, status, owner, update time, search. | Start task. | Empty, loading, results, error. |
| New task | Question, scope, desired output, source constraints. | Submit. | Valid, incomplete, denied, unavailable workflow. |
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
