# NortPole — API design

> **Where this lives in code (2026-11-14).** Service and package names here (`services/control-plane`, `services/execution`, `services/knowledge`, `packages/*`, `evaluations`) are logical owners from the design stage. [Decision 0006](../decisions/0006-scalable-repository-structure.md) maps them to the code: the three services are implemented inside `services/core`, and the packages and evaluations are planned modules in `modules.json`, created when their first code arrives.

Status: **proposed contract; no implementation exists** · Updated: 2026-11-08

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
| GET /v1/exports/{id} | Read status or download an export. | Recheck artifact and evidence access on every new download request; do not rely on an unrevocable storage URL. |
| POST /v1/workflows/{id}/versions | Create a draft version. | Workflow owner permission. |
| POST /v1/workflows/{id}/versions/{version}/publish | Publish a tested version. | Passing release gates and publisher permission. |
| POST /v1/workflows/{id}/disable | Block new runs and stop active runs at safe checkpoints. | Administrator permission and audit event. |
| POST /v1/sources/{id}/disable | Revoke retrieval and tool access. | Administrator permission; revalidate affected runs. |

Task creation saves a draft; run creation starts execution. Decisions specify the exact pending step or artifact version and expected state. Duplicate decisions are idempotent; conflicting or stale decisions return STATE_CONFLICT. Tool approvals bind immutable action arguments and cannot authorize a changed payload. Export creation returns a job ID and status; download authorization is checked again even if creation succeeded earlier.

## Explicit run-start contract

POST /v1/tasks belongs to control in services/control-plane; POST /v1/tasks/{id}/runs belongs to services/execution, routed through the public API or workspace BFF. The start request carries an idempotency key and expected task version. Execution obtains the authorized task snapshot and current published definition versions through control APIs, rejecting stale versions or disabled resources. It commits the run, job, start-request digest/result and dispatch outbox atomically in execution-owned storage. No cross-service transaction is assumed.

A repeated key within the tenant/task/start-operation scope with the same request returns the original run ID; changed input returns STATE_CONFLICT. A timeout is retried with the same key. Task creation retries cannot start a run. Intentional reruns use a new key; retries of failed runs use the linked retry operation and retain external-action deduplication. Workers recheck current permissions before protected actions. Contract tests cover duplicate/concurrent starts, lost responses, stale task versions, and a saved draft producing zero jobs.

## Layer boundaries

L03 owns public schemas and task drafts. L04 records approval decisions. L05 owns explicit start and run state. A web, scheduled, or embedded caller must pass the same authorization and idempotency checks.

## Development fixture definition before publication exists

P02 uses a fixed, synthetic-only development workflow definition pinned by content digest and explicitly allowlisted in the local test configuration. It is not a published/activated customer package and must not expose a general publication bypass. The development profile rejects arbitrary workflow definitions and customer sources. The live-route test may use this same fixed definition with synthetic inputs and approved processing destinations.

Before P05 acceptance, replace the fixture definition resolution with the evaluated registry/publication path. Production and customer profiles must reject the development bootstrap path. Add tests for digest mismatch, an unlisted definition and attempts to enable bootstrap in a customer/production profile. The first-workflow APIs otherwise require published, authorized versions as specified above.

## Expansion endpoints (proposed, not first release)

Added 2026-11-08 for the expansion features in the feature catalog. These are illustrative paths that follow the common conventions above; none is committed and none changes first-release scope.

| Method and path | Purpose | Feature | Required control |
| --- | --- | --- | --- |
| `GET /v1/review-items` | List pending approvals and escalations for the caller. | PF-01.08, PF-05.05 | Current role and source access; withheld items are omitted, not masked. |
| `GET/PUT /v1/notification-preferences` | Read or set alert channels. | PF-01.09 | Self or administrator; alert bodies carry no protected text. |
| `POST /v1/agent-drafts` | Draft an agent definition from a prompt. | PF-01.11 | Draft only; publication still needs the evaluation gate. |
| `GET/POST /v1/saved-prompts` | Manage slash commands and saved prompts. | PF-01.12 | Owner or tenant scope; running one is an ordinary task start. |
| `POST /v1/packages/{id}/signatures` | Attach and verify a package signature. | PF-02.05 | Publisher key and registry policy; unsigned packages do not activate. |
| `POST /v1/partner-submissions` | Submit a partner package for review. | PF-02.06 | Partner identity; review and evaluation before listing. |
| `POST /v1/sandboxes` | Create an isolated developer sandbox. | PF-03.04 | Synthetic data only; no production credentials. |
| `GET /v1/inventory` | List agents, tools and grants. | PF-03.05 | Administrator permission. |
| `GET/PUT /v1/agents/{id}/guardrails` | Read or set autonomy tier and limits. | PF-04.07 | Administrator; changes are versioned and take effect on new runs. |
| `GET/PUT /v1/policies/redaction` | Manage sensitive-data rules. | PF-04.04 | Administrator; fixed test suite must pass before activation. |
| `POST /v1/compliance-exports` | Generate an evidence export. | PF-04.06 | Compliance role; evidence only, not a certification. |
| `POST /v1/runs/{id}/delegations` | Delegate to a sub-agent. | PF-05.04 | Child permissions and budget never exceed the parent. |
| `POST /v1/browser-sessions` | Open a bounded browser or computer-use session. | PF-05.06 | No implicit credentials; external effects need exact-action approval. |
| `POST /v1/sources/{id}/files` | Upload a file for parsing. | PF-06.03 | Source permission; parsed text inherits the file ACL. |
| `GET/DELETE /v1/memory/{id}` | Inspect or delete a memory entry. | PF-06.04 | Scope owner; deletion removes derived projections. |
| `GET/PUT /v1/spend-limits` | Read or set quotas and alerts. | PF-07.06 | Administrator; the limit is enforced in the model gateway. |
| `POST /v1/model-routes` | Register a customer-supplied model. | PF-07.05 | Administrator; evaluation and destination policy first. |
| `/mcp` (server interface) | Expose approved tools to external MCP clients. | PF-08.03 | Per-client scopes; same policy as internal calls. |
| `POST /v1/tools/import` | Import an OpenAPI description as a tool. | PF-08.04 | Administrator; tool is inactive until allowlisted. |
| `GET/PUT /v1/extension-allowlist` | Allow or block servers and tools. | PF-08.05 | Administrator; blocked entries are never called. |
| `GET/PUT /v1/extension-policy` | Set Off, Request or Self-serve per extension type. | PF-08.06 | Administrator; the server rejects an add action when the level is Off. |
| `POST /v1/extension-requests` | Request a connector, skill, plugin or MCP server. | PF-08.06 | Authenticated user; unusable until an administrator approves. |
| `GET/PUT /v1/me/preferences` | Read or set the user's default model route and notification choices. | PF-07.03, PF-01.09 | The user; a preference never overrides administrator policy. |
| `POST /v1/workflows/{id}/shadow-runs` | Run a candidate beside the live version. | PF-09.04 | Outputs are not delivered; no external writes. |
| `POST /v1/artifacts/{id}/feedback` | Record a reviewer correction or rating. | PF-09.05 | Reviewer access; dataset use needs authorization and redaction. |
| `GET /v1/reports/outcomes` | Read completion, review time and cost per task. | PF-09.06 | Tenant-scoped aggregates. |
| `GET /v1/usage-exports` | Export metered usage. | PF-09.07 | Administrator; metering only, no prices. |
| `PUT /v1/tenant/keys` | Set a customer-managed key and residency region. | PF-10.04 | Tenant owner; revocation stops reads. |
| `POST /v1/hybrid/enrollments` | Enroll a customer-side data plane. | PF-10.05 | Mutual authentication; local policy holds offline. |

Contract tests to add for these: a withheld item never appears in the inbox or an alert; a child run is denied anything its parent lacks; a call above its autonomy tier is blocked and approval cannot override a policy block; redaction and injection suites pass before activation; a blocked extension is never called; shadow runs deliver nothing; a revoked key stops reads.
