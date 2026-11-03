# EvolvXSI — user stories

Status: **candidate first-release backlog** · Updated: 2026-11-02

Priority labels: **P0** required for a credible first workflow, **P1** pilot improvement, **Later** dependent on observed demand. These are product stories, not engineering estimates. The [PRD](EvolvXSI_First-Workflow-PRD.md) is the source for release gates.

## Epic 1 — task and workspace

| ID | Priority | Story | Acceptance |
| --- | --- | --- | --- |
| US-01 | P0 | As a practitioner, I can create a task with a question, scope, and output request. | Required fields are validated and the task is saved with an owner and status. |
| US-02 | P0 | As a practitioner, I can return to my prior tasks. | I can search and open tasks I am authorized to see; inaccessible tasks are absent. |
| US-03 | P1 | As a workflow owner, I can use a reusable task template. | Template version and user changes are recorded. |

## Epic 2 — knowledge and evidence

| ID | Priority | Story | Acceptance |
| --- | --- | --- | --- |
| US-04 | P0 | As an administrator, I can connect one approved source. | Ingestion status, last update, and errors are visible. |
| US-05 | P0 | As a practitioner, I receive only evidence I may access. | Permission tests cover search results, generated content, citations, and export. |
| US-06 | P0 | As a reviewer, I can open the passage behind a cited claim. | Citation resolves to a source identity and passage; missing passages are flagged. |
| US-07 | P1 | As a reviewer, I can flag a citation as incorrect or stale. | Feedback is stored against the run and source reference. |

## Epic 3 — execution and review

| ID | Priority | Story | Acceptance |
| --- | --- | --- | --- |
| US-08 | P0 | As a practitioner, I can review and revise the plan before drafting. | Execution pauses at the configured review point; edits are captured. |
| US-09 | P0 | As a practitioner, I can see task progress and errors. | Current step, completion state, and actionable error are visible. |
| US-10 | P0 | As a practitioner, I can reject, revise, or approve a draft. | Final approval is explicit and associated with a versioned artifact. |
| US-11 | P0 | As an administrator, I can require approval before an external write. | No classified side effect runs without a valid approval record. |
| US-12 | P0 | As a practitioner, I can request a targeted revision. | Original and revised artifacts remain distinguishable. |

## Epic 4 — policy and operations

| ID | Priority | Story | Acceptance |
| --- | --- | --- | --- |
| US-13 | P0 | As an administrator, I can restrict model destinations by data class. | Prohibited requests are blocked before transmission and logged without sensitive content. |
| US-14 | P0 | As an operator, I can inspect a failed run. | Run ID, step, error category, version, and retry eligibility are visible. |
| US-15 | P0 | As an administrator, I can disable a workflow or connector. | New runs cannot use it after disablement; active-run handling is explicit. |
| US-16 | P0 | As an operator, I can view cost per completed task. | Model and tool cost estimates aggregate under the run ID. |

## Epic 5 — quality and release

| ID | Priority | Story | Acceptance |
| --- | --- | --- | --- |
| US-17 | P0 | As a workflow owner, I can evaluate a version before publishing. | A fixed test set produces comparable results and keeps the version identifier. |
| US-18 | P0 | As a practitioner, I can export an approved report and citations. | Export includes the approved version and has a recorded timestamp. |
| US-19 | P1 | As a workflow owner, I can compare pilot outcomes with the manual baseline. | Completion, effort, quality, latency, and cost measures can be reviewed together. |

## Later backlog

Multiple verticals, public marketplace, advanced workflow builder, broad connector catalog, and autonomous workflow changes require evidence from the first paid deployment. They are outside the first-release commitment.
