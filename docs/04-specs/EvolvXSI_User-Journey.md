# NortPole — user journey

Status: **proposed journey for a candidate research report workflow** · Updated: 2026-11-05

The first vertical is undecided. This journey makes the [first-workflow PRD](EvolvXSI_First-Workflow-PRD.md) concrete enough to test with practitioners and administrators. Adapt the task, sources, and output after discovery.

## Practitioner journey

| Stage | User action | System response | Risk and design response |
| --- | --- | --- | --- |
| 1. Start | Enter a question, scope, intended audience, and report format. | Validate and save a draft without dispatch. Show the proposed data/tool scope; only explicit Start creates a run. | Ambiguous request: allow revision before execution. |
| 2. Plan | Review proposed outline, source coverage, and known gaps. | Show a concise plan and estimated next steps. | Wrong scope: practitioner edits or rejects plan. |
| 3. Gather evidence | Inspect retrieved sources and passages. | Display source identity, permission status, timestamp, and passage link. | Missing or conflicting evidence: flag explicitly. |
| 4. Draft | Open structured report and claim-to-source links. | Show progress, unsupported claims, and failures. | Hallucination: require evidence review before approval. |
| 5. Review | Edit, ask for a targeted revision, or reject. | Preserve revisions and show what changed. | Automation overreach: no silent finalization. |
| 6. Approve | Confirm final artifact. | Record the authorized approver, exact version and timestamp. Export is a separate action with a fresh access check. | Accountability: keep a clear approval record. |
| 7. Revisit | Search prior task or reopen an issue. | Show source set, run history, feedback, and current artifact. | Stale evidence: mark when source freshness needs review. |

## Administrator journey

1. Create a tenant or workspace and assign roles.
2. Connect one approved source and verify ingestion status.
3. Define access rules, permitted model destinations, tool scopes, and retention.
4. Review a versioned workflow and its evaluation results before publishing.
5. Observe runs, failures, cost, and user feedback.
6. Disable a workflow or connector and revoke access when needed.

## Key states and transitions

`Draft task → Explicit start → Submitted → Planning → Awaiting scope review → Running → Draft ready → Awaiting final review → Approved → Exported`

These are task stages. Run states are queued, running, waiting_for_review, paused, succeeded, failed, and cancelled. Approval belongs to an artifact version; export is a separate event. Alternative task states: `Needs input`, `Failed`, `Rejected`, `Cancelled`, and `Archived`. A run must never appear approved when the practitioner has only reviewed an outline. Retry should preserve the original task and create an auditable new attempt where appropriate.

## Usability questions for interviews

- At which point does the practitioner want to see and change the plan?
- Which source details are necessary to trust a citation?
- Is review easier in a report view, claim list, or side-by-side source panel?
- Which revisions are common, and how should they be requested?
- Who can approve, export, reopen, or delete a task?

## From a question to a reusable team workflow

A practitioner opens a question in the workspace and selects the team's published workflow. The review screen keeps each finding beside the permitted passage that supports it. If two versions disagree, the practitioner can inspect both and refer the uncertainty to the reviewer. After approval, a colleague reopening the task sees only material their own access permits. When the task repeats, the workflow owner can use reviewer corrections as cases for evaluating the next version.

## Journey success measures

Time to first useful draft, practitioner review time, percentage of tasks completed, number of revisions, citation verification rate, and successful return to a previous task. Set targets only after observing the current process.

## Portal handoffs

The practitioner and reviewer use the Workspace and Review & Approval surfaces. Admin grants and run diagnostics use separate role views. See the [surface inventory](../05-design/EvolvXSI_UI-Spec.md#portal-and-surface-inventory-l01).
