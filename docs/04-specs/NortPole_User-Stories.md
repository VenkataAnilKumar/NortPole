# NortPole — user stories

Status: **candidate first-release backlog and platform expansion epics** · Updated: 2026-11-05

Priority labels: **P0** required for a credible first workflow, **P1** pilot improvement, **Later** dependent on observed demand. These are product stories, not engineering estimates. The [PRD](NortPole_First-Workflow-PRD.md) is the source for release gates.

## Epic 1 — task and workspace

| ID | Priority | Story | Acceptance |
| --- | --- | --- | --- |
| US-01 | P0 | As a practitioner, I can create a task with a question, scope, and output request. | Required fields are validated; save creates a draft and zero jobs. Explicit start creates one authorized run, including under duplicate requests. |
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

## Pilot walkthrough for the existing stories

Give two practitioners different access to the same project. The first creates an evidence brief and sends it for review. The second opens the shared task after losing access to one supporting source. Verify that the second user can understand the task state without seeing the restricted passage or dependent text. Ask the reviewer to edit the brief, approve the new version, and identify the exact version that was exported.

## Later backlog

Multiple verticals, public marketplace, advanced workflow builder, broad connector catalog, and autonomous workflow changes require evidence from the first paid deployment. They are outside the first-release commitment.

## Cross-layer ownership

Use the [requirement-to-layer map](../06-technical/NortPole_Feature-Architecture-Mapping.md#layer-traceability-for-the-first-release) when assigning stories. Treat portal and pack extensions as later backlog unless the first workflow needs them.

## Platform capability epics

| Epic | Story and evidence | Feature references |
| --- | --- | --- |
| Author and publish (pilot controls; self-service Studio in expansion) | An author configures a workflow, compares two candidates and publishes the exact version that passed. | PF-01.05, PF-02.01, PF-03.02, PF-09.02 |
| Automate safely | An operator disables a schedule and resolves an uncertain tool outcome before retrying. | PF-05.03, PF-08.02 |
| Govern enterprise access | An admin revokes access and verifies it across the workspace, embedded channels and exports. | PF-01.04, PF-04.02–03 |
| Integrate and operate | A developer starts a run through the API. An operator identifies a failure and restores the selected environment. | PF-03.03, PF-09.03, PF-10.02 |
| Extend with packs | A domain owner activates an evaluated pack and upgrades it while existing runs keep their pinned versions. | PF-02.02–03 |

Use the [platform feature catalog](NortPole_Feature-Spec.md#full-platform-feature-catalog) to assign engineering owners and acceptance evidence.

## Additional expansion acceptance

| Epic | Story and evidence | Feature references |
| --- | --- | --- |
| Collaborate | A practitioner shares a task and hands off review; revoked recipients cannot read content or receive protected notifications. | PF-01.06 |
| Reuse horizontal packs | A pack author uses the same evaluated domain-neutral bundle in two verticals and demonstrates that tenant grants remain separate. | PF-02.04 |
| Operate commercial surfaces | A buyer sees evidence-backed commitments; support staff access only authorized tenant records and leave an audit trail. | PF-01.07 |
| Review and notify | A reviewer finds pending approvals in one inbox and receives an alert; after losing access the reviewer sees neither the item nor its protected text. | PF-01.08–01.09 |
| Delegate and escalate | A parent run delegates to a sub-agent within budget and routes a policy hold to a reviewer queue. | PF-05.04–05.05 |
| Resist hostile content | A document contains injected instructions; the agent neither calls an unapproved tool nor sends content to a prohibited destination, and sensitive fields are redacted before transmission. | PF-04.04–04.05 |
| Control autonomy and spend | An administrator sets an agent to draft-only and sets a quota; the alert fires before the limit, and a blocked call stays blocked after approval. | PF-04.07, PF-07.06 |
| Extend safely | An administrator allows one MCP server with read-only tools; a blocked server is never called, and an external client uses the MCP server interface within its scopes. | PF-08.03–08.05 |
| Extend within limits | An administrator allows personal connectors and skills at Self-serve; a user adds one, sees only their own access, and a personal skill is blocked from a route that policy disallows. | PF-08.06 |
| Learn from feedback | Reviewer corrections are stored with the artifact version and enter an evaluation dataset only after authorization and redaction; a candidate runs in shadow mode before publication. | PF-09.04–09.05 |
| Report outcomes | A workflow owner compares completion, reviewer time and cost per completed task with the manual baseline and exports usage for billing. | PF-09.06–09.07 |
| Operate hybrid | A customer keeps documents and credentials local while a cloud control plane distributes signed definitions; local policy holds offline, and a revoked key stops reads. | PF-10.04–10.05 |

Capability epics span pilot foundations and expansion. The feature catalog's First target and the phase matrix control scope; an epic title is not a pilot commitment.
