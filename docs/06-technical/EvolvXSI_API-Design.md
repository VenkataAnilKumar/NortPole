# EvolvXSI — API design

Status: **proposed contract; no implementation exists** · Updated: 2026-11-02

## Scope

Define stable boundaries for tasks, runs, evidence, approvals, workflows, sources, and evaluation. These illustrative paths are not committed public APIs. The implementation should refine them after the first workflow and identity model are selected.

## Common conventions

- All requests are authenticated and authorized for a tenant and actor.
- Resource IDs are opaque. Clients never infer access from an ID.
- Write requests carry an idempotency key where duplicate submission could repeat work.
- Responses include a request ID; run-related responses include a run ID.
- Timestamps are stored as UTC instants and rendered in the user's locale.
- APIs validate schema versions and reject unknown or unsupported workflow versions explicitly.
- Lists use cursor pagination and a stable sort order.

## Candidate endpoints

| Method and path | Purpose | Required control |
| --- | --- | --- |
| `POST /v1/tasks` | Create a task from a published workflow. | Workflow use permission. |
| `GET /v1/tasks` | List authorized tasks. | Tenant and user filtering. |
| `GET /v1/tasks/{id}` | Read task, latest artifact, and status. | Task read permission. |
| `POST /v1/tasks/{id}/runs` | Start a run. | Idempotency and model policy. |
| `GET /v1/runs/{id}` | Read run status and steps. | Run read permission. |
| `GET /v1/runs/{id}/events` | Read or stream structured progress. | Run read permission; redact sensitive content. |
| `POST /v1/runs/{id}/decisions` | Accept plan, request revision, reject, or approve. | Role, step, and state validation. |
| `GET /v1/tasks/{id}/evidence` | List authorized citations and passages. | Source permission recheck. |
| `POST /v1/tasks/{id}/exports` | Generate an approved artifact export. | Approved version and export permission. |
| `POST /v1/sources` | Create a source connection. | Administrator permission. |
| `GET /v1/workflows` | List available workflow versions. | Workflow view permission. |
| `POST /v1/workflows/{id}/evaluations` | Run a fixed evaluation suite. | Workflow owner permission. |

## Example task creation

```json
{
  "workflow_id": "wf_example",
  "workflow_version": "1",
  "title": "Review a research question",
  "input": { "question": "Example question", "scope": "Defined by the user" }
}
```

The response returns `task_id`, draft status, accepted workflow version, and a task link. It does not create or return a run. Validation errors identify the field without echoing sensitive input.

## Error model

Use stable codes such as `VALIDATION_ERROR`, `ACCESS_DENIED`, `POLICY_BLOCKED`, `STATE_CONFLICT`, `SOURCE_UNAVAILABLE`, `RATE_LIMITED`, and `INTERNAL_ERROR`. Return a safe user message, request ID, and retry guidance where appropriate. Logs may hold diagnostic details under controlled access; client errors must not expose credentials, source content, or internal stack traces.

## Events and side effects

Run events carry sequence number, run ID, step ID, event type, timestamp, and safe payload. Consumers must tolerate reconnection and duplicate delivery. First-release external writes require a tool permission check, explicit approval record, and a deduplication key. A retry must not repeat a completed write silently.

## Contract tests to add during implementation

Verify tenant isolation, denied source access, invalid state transitions, idempotent run start, safe error payloads, event replay, and export of only the approved artifact version.


## Required lifecycle controls

| Method and path | Purpose | Control |
| --- | --- | --- |
| POST /v1/runs/{id}/pause | Pause at a safe checkpoint. | Report pending versus effective pause. |
| POST /v1/runs/{id}/resume | Resume a paused run. | Recheck user, source, model, and tool access. |
| POST /v1/runs/{id}/cancel | Stop pending work. | Block new tool calls; report completed side effects. |
| POST /v1/runs/{id}/retry | Create a linked new run attempt. | Preserve side-effect deduplication. |
| POST /v1/tasks/{id}/artifacts | Save an edited artifact version. | Edit permission and expected version. |
| GET /v1/exports/{id} | Read status or download an export. | Recheck artifact and evidence access; expire links. |
| POST /v1/workflows/{id}/versions | Create a draft version. | Workflow owner permission. |
| POST /v1/workflows/{id}/versions/{version}/publish | Publish a tested version. | Passing release gates and publisher permission. |
| POST /v1/workflows/{id}/disable | Block new runs and stop active runs at safe checkpoints. | Administrator permission and audit event. |
| POST /v1/sources/{id}/disable | Revoke retrieval and tool access. | Administrator permission; revalidate affected runs. |

Task creation saves a draft; run creation starts execution. Decisions specify the exact pending step or artifact version and expected state. Duplicate decisions are idempotent; conflicting or stale decisions return STATE_CONFLICT. Tool approvals bind immutable action arguments and cannot authorize a changed payload. Export creation returns a job ID and status; download authorization is checked again even if creation succeeded earlier.

## Explicit run-start contract

POST /v1/tasks belongs to control; POST /v1/tasks/{id}/runs belongs to execution, routed through the workspace BFF. The start request carries an idempotency key and expected task version. Execution obtains the authorized task snapshot and current published definition versions through control APIs, rejecting stale versions or disabled resources. It commits the run, job, start-request digest/result and dispatch outbox atomically in execution-owned storage. No cross-service transaction is assumed.

A repeated key within the tenant/task/start-operation scope with the same request returns the original run ID; changed input returns STATE_CONFLICT. A timeout is retried with the same key. Task creation retries cannot start a run. Intentional reruns use a new key; retries of failed runs use the linked retry operation and retain external-action deduplication. Workers recheck current permissions before protected actions. Contract tests cover duplicate/concurrent starts, lost responses, stale task versions, and a saved draft producing zero jobs.
