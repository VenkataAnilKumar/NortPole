# EvolvXSI — data model

Status: **conceptual model; PostgreSQL proposed for authoritative state; final selection in P00** · Updated: 2026-11-05

## Core entities

| Entity | Key fields | Relationship and invariant |
| --- | --- | --- |
| Tenant | ID, name, policy version, retention policy. | Owns all customer data and configuration. |
| User | ID, tenant ID, identity reference, status. | Belongs to a tenant; access comes from roles and source permissions. |
| Role assignment | User ID, role, scope, effective dates. | Grants specific actions; changes are audited. |
| Source connection | ID, tenant ID, type, owner, status, refresh time. | Credentials are referenced, never stored in task records. |
| Source document | ID, source ID, external ID, version, permission metadata. | Preserves source identity and access mapping. |
| Evidence passage | ID, document version, location, content reference. | Citation resolves to a precise source version and location. |
| Workflow | ID, tenant ID, name, status. | Has one or more immutable published versions. |
| Workflow version | Workflow ID, version, input/output schemas, policy reference. | Past runs retain their original version. |
| Task | ID, tenant ID, project ID, creator, owner, workflow ID, version, status. | Represents the user's request and current outcome. |
| Run | ID, task ID, workflow version, attempt, status, timestamps. | One execution attempt; can have many steps and events. |
| Run step | ID, run ID, type, state, timing, error category. | Makes recovery and status visible. |
| Artifact version | ID, task ID, run ID, creator type, content reference. | Approval points to one exact immutable version. |
| Citation | Artifact version, claim location, evidence passage ID. | Supports navigation and provenance checks. |
| Decision | ID, run ID, actor, decision type, target version, time. | Records plan acceptance, rejection, revision, or approval. |
| Tool invocation | ID, run step, tool, side-effect class, deduplication key. | External writes cannot be silently repeated. |
| Evaluation run | ID, workflow version, suite version, result, time. | Enables before/after comparison. |
| Audit event | ID, actor, action, resource, time, outcome. | Append-only logical record for sensitive operations. |

## Relationship sketch

```mermaid
erDiagram
  TENANT ||--o{ USER : contains
  TENANT ||--o{ WORKFLOW : owns
  TENANT ||--o{ SOURCE_CONNECTION : owns
  WORKFLOW ||--o{ WORKFLOW_VERSION : publishes
  WORKFLOW ||--o{ TASK : used_by
  TASK ||--o{ RUN : executes
  RUN ||--o{ RUN_STEP : records
  TASK ||--o{ ARTIFACT_VERSION : produces
  ARTIFACT_VERSION ||--o{ CITATION : contains
  SOURCE_CONNECTION ||--o{ SOURCE_DOCUMENT : indexes
  SOURCE_DOCUMENT ||--o{ EVIDENCE_PASSAGE : exposes
  EVIDENCE_PASSAGE ||--o{ CITATION : supports
  RUN ||--o{ DECISION : receives
  WORKFLOW_VERSION ||--o{ EVALUATION_RUN : tested_by
```

## Invariants

1. Every customer-owned row has a tenant boundary; queries enforce it server-side.
2. A citation cannot disclose a passage after access is revoked; provenance metadata may remain according to retention policy without exposing content.
3. Published workflow versions and approved artifact versions are immutable. Edits create new versions.
4. A decision records the actor and exact run or artifact version it applies to.
5. Secrets are held in a dedicated credential store and referenced by identifier.
6. Audit and run records have an explicit retention and deletion policy defined with the customer.
7. A tool invocation's deduplication key is unique within its side-effect scope.

## Data lifecycle questions

Define document refresh and deletion behavior, source version retention, task export format, customer deletion rights, legal hold needs, backup and restore objectives, and whether evaluation cases may contain customer data. These must be resolved before a production deployment.


## Additional records and approval bindings

Persist Run event (run, sequence, type, safe payload), Model invocation (run step, destination, policy decision, usage, estimated cost), Export job (artifact version, requester, status, expiry), and versioned Evaluation suite (cases, rubric, thresholds). Link generated artifacts to source dependencies so revocation can restrict derived content.

A decision binds to a pending step, artifact version, or immutable tool action and payload digest. Record resolution and consumption state. Tool invocations reference their approval. Concurrent decisions check expected state/version. Changed payloads and artifact edits require fresh approval.

Runs use queued, running, waiting_for_review, paused, succeeded, failed, or cancelled. Artifacts use draft, in_review, approved, or rejected. Exports are separate records. Retries create linked run attempts; transient step retries remain inside the current attempt.

## Ownership and additional implementation records

Control and registry records belong to services/control-plane. Execution, Knowledge and Hybrid map to services/execution, services/knowledge and services/model-gateway. Connector and evaluation contracts map to packages/integrations and evaluations. Physical data ownership follows these boundaries even when processes share infrastructure.

These are conceptual contracts for P01 schema design, not implemented migrations. Relationships across owners are tenant-scoped IDs validated through APIs/events; they are not cross-schema joins or foreign keys. Existing User records represent tenant-local identities; membership binds that identity to the external identity-provider subject.

| Record | Owner | Key fields and invariant |
| --- | --- | --- |
| Tenant, User, Role assignment | Control | Tenant-scoped identity and authorization; roles cannot grant access beyond current source permissions. |
| Membership | Control | Tenant, user, identity issuer/subject, status, role references, version. Unique identity mapping within tenant; suspension invalidates new protected actions. |
| Project | Control | ID, tenant, name, owner, access policy, version, status. Tasks belong to a project in the same tenant; sharing does not grant source access. |
| Task, Workflow/version, Decision | Control | Task drafts are independent of run creation. Workflow versions are immutable when published; decisions bind exact targets. |
| Package version | Control registry | Kind (agent/skill/pack), ID/version, content digest, manifest, immutable dependency digests, compatibility, requested permissions. Published contents cannot be overwritten. |
| Package activation | Control registry | Tenant, package/version/digest, effective grants, state, policy version. Activation requires passing evaluation and compatible dependencies; a manifest does not grant authority. |
| Publication evidence | Control registry | Candidate and dependency digests, suite/rubric version, thresholds, evaluation result digest, approver, decision time. Changed inputs invalidate prior evidence. |
| Run, Run step, Artifact version, Citation, Export job | Execution | Store pinned definition versions and logical task/evidence IDs. Export binds approved artifact version and rechecks access. |
| Start request | Execution | Tenant/task/operation, idempotency key, request digest, run ID, result. Unique scope/key; changed digest conflicts. Committed with run/job/outbox. |
| Durable job | Execution | ID, run/step, state, attempt, available time, lease owner/expiry, fencing version, checkpoint reference. Lease fencing prevents a stale worker committing a transition. |
| Run event | Execution | Run, sequence, event ID, safe payload. Unique run/sequence for ordered replay. |
| Outbox event | Each producing service | Event ID, aggregate/version, safe payload, available time, delivery attempts. Written with its owner's state change; duplicate delivery expected. |
| Inbox receipt | Each consuming service | Producer/event ID, result and processed time. Unique producer/event; commit receipt with local effect. External effects still require reconciliation. |
| Tool invocation | Execution | Run/step, immutable action digest, approval ID, deduplication key and outcome. Integrations owns the corresponding remote receipt/reconciliation state. |
| Source connection/document/passage | Knowledge | Versions and current ACL metadata. Integration credential references are opaque IDs; knowledge owns ingestion/access state. |
| Memory entry | Knowledge | Tenant, scope kind (session/project/tenant), scope ID, content reference, source dependencies, creator, version, expiry, access policy. Explicit grants and current source access apply on every read. |
| Source dependency | Owning derived-content service | Derived record/version, source document/version, access status. Execution owns artifact dependencies; knowledge owns memory dependencies. Revocation events invalidate projections, and reads verify current authority. |
| Model invocation | Hybrid | Run/step, destination, policy version, usage, estimated cost/status. Execution references the invocation through contracts. |
| Evaluation suite/result | Evaluations | Immutable suite/rubric, candidate/dependency digests, thresholds, per-case outcomes and report digest. Control consumes results to enforce publication. |
| Audit event | Producing service; restricted operational projection | Actor, tenant, resource, action, outcome, time and event ID. No sensitive source text; explicit retention and access policy. |

Control-to-execution task and decision links are logical references. Registry packages reference released definitions authored in agent/skill/pack modules; the registry does not own their source code. Jobs and outbox records become durable in P02, scoped memory in P04, and registry/evaluation records in P05, using the contracts designed in P01.

## Layer boundary checks

Keep registry state (L03), approval decisions (L04), run state (L05), source versions (L06), model usage (L07), and evaluation results (L09) under their designated owners. Link records through tenant-scoped identifiers and versioned contracts.
