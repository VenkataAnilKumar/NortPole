# EvolvXSI — feature specification

Status: **platform catalog and first-workflow specification** · Updated: 2026-11-05

This specification translates the [PRD](EvolvXSI_First-Workflow-PRD.md) into feature behavior. It is intentionally independent of implementation projects. The selected customer workflow may change field names, source types, and output format.

## F-01 Task intake and status

**Inputs:** title, question, scope, desired output, optional source constraints. **Behavior:** validate inputs, save a draft owned by the initiating user without creating a job, assign a run ID on explicit start, and show status transitions. **Errors:** missing required fields, unavailable workflow, denied access. **Acceptance:** a user can save, start, find and reopen authorized tasks, and cancel an active run without losing the request.

## F-02 Source connection and retrieval

An administrator configures one approved source, credentials, refresh behavior, and access mapping. Ingestion reports success, partial failure, and last successful update. Retrieval uses the effective permissions of the task initiator. Results include source identity, passage, location, and retrieval timestamp. A denied source must be absent from search, generated answer, and export.

## F-03 Plan review

Before drafting, show a proposed outline, evidence coverage, and unresolved questions. The practitioner may continue, change scope, or cancel. Continuing records the accepted plan version. A timeout or disconnected client must leave the run in a recoverable waiting state.

## F-04 Evidence-linked draft

Create the agreed artifact structure. Link material factual claims to evidence passages. Mark unsupported or conflicting claims in the draft rather than hiding them. The interface lets the reviewer open the source from a claim. The system records which source set and workflow version produced each draft.

## F-05 Review, approval, and export

The reviewer may edit, request targeted revision, reject, or approve. Only an authorized approver can finalize. Approval stores the artifact version, actor, and timestamp. An edit creates a new version requiring fresh approval. Export uses that approved version and includes its citation list. An unapproved draft must not be labeled final.

## F-06 Tool and model policy

Every tool declares its allowed actions, credential scope, and whether it has a side effect. The platform checks permissions before invocation. Every model request checks tenant data classification and destination policy before sending content. A blocked route returns a clear error; it must not silently fall back to an unapproved destination.

## F-07 Run history and recovery

Show each run's steps, status, timings, evidence references, model and tool identifiers, cost estimate, error category, approvals, and output versions. Failed steps may be retried when safe. Side-effecting actions require deduplication or a recorded manual recovery path.

## F-08 Evaluation and publication

A workflow version has a representative test set with expected properties. The owner can compare citation quality, unsupported claims, task completeness, policy violations, and completion rate against a previous version. Publication records who approved the version and when. Publication requires passing agreed quality thresholds. Unauthorized disclosure, prohibited transmission, and unapproved external writes block rollout regardless of aggregate scores.

## Cross-feature acceptance example

Use F-01 to save a draft without starting execution. After explicit start, F-02 and F-04 must produce a finding linked to an accessible passage or mark it unsupported. Under F-05 and F-09, editing approved content requires fresh approval and losing source access blocks the affected export. F-07 must show the review history without disclosing restricted passages. Under F-08, replay the same cases before publishing a changed workflow.

## Shared rules

- Authorization applies at every read, write, export, and tool boundary.
- User-facing errors state what failed and what the user can do next without exposing secrets.
- A workflow update never changes the recorded version of a past run.
- Deletion and retention behavior follow the customer's agreed policy; exact periods are undecided.
- Accessibility, performance, and cost targets are set from the first pilot baseline.


## F-09 Access changes and approval bindings

Verify access before displaying generated content or downloading exports. Withhold affected artifacts after source access revocation until safe redaction or regeneration. Apply the same restriction to previews, traces, and cached exports. External writes require approval bound to immutable action arguments, target, and run; changed payloads require fresh approval and policy checks at execution.

## Layer ownership

Use the [feature architecture mapping](../06-technical/EvolvXSI_Feature-Architecture-Mapping.md) to connect feature behavior with owning modules and acceptance.

## Full platform feature catalog

**Fixture** proves the engineering foundation using synthetic inputs. **Pilot** proves a governed workflow with one customer, source and approved model route. **Expansion** describes the broader EvolvXSI product target informed by the North benchmark; it does not claim verified feature parity or knowledge of North internals. Each entry states an observable outcome. The F-01–F-09 sections retain detailed behavior for the first workflow.

| Feature ID | Layer | Capability | First target | Acceptance evidence |
| --- | --- | --- | --- | --- |
| PF-01.01 | L01 | Workspace tasks | Fixture | Save a draft without dispatch; start, reopen and inspect one authorized run. |
| PF-01.02 | L01 | Search and artifact review | Pilot | Inspect cited passages beside the draft and export the approved version. |
| PF-01.03 | L01 | Chat, libraries and generated applications | Expansion | Move from chat to a task and publish an authorized artifact or lightweight app. |
| PF-01.04 | L01 | Portals and embedded entry points | Expansion | Authors, admins, operators and developers each have role-specific views; embedded actions enforce the same policy. |
| PF-01.05 | L01 | Agent and Automation Studio | Expansion | An author edits, validates, evaluates and publishes a candidate; failed or stale evaluation evidence blocks publication. |
| PF-01.06 | L01 | Team collaboration | Expansion | Share a task, comment and hand off review within tenant grants; revoked collaborators lose access to content and notifications. |
| PF-01.07 | L01 | Commercial, trust and support surfaces | Expansion | Public claims link to approved evidence; support access is scoped, time-bound and audited, with tenant authorization for protected records. |
| PF-02.01 | L02 | Agents and skills | Pilot | A configured workflow pins its agent and skill versions; later edits leave past run definitions and evidence unchanged. Exact model-output replay is not guaranteed. |
| PF-02.02 | L02 | Vertical pack lifecycle | Pilot | Validate and activate a pack with a domain workflow, template, reviewer rule and evaluation cases. |
| PF-02.03 | L02 | Catalog and pack upgrades | Expansion | Compare pack versions, check compatibility and activate a tested upgrade for one tenant. |
| PF-02.04 | L02 | Horizontal capability packs | Expansion | Reuse a versioned domain-neutral workflow and skill bundle in two verticals without duplicating identity, execution, routing or audit. |
| PF-03.01 | L03 | Task and run contracts | Fixture | Public contracts separate draft from start; concurrent identical starts return one run. |
| PF-03.02 | L03 | Registry and publication | Pilot | Publish the exact evaluated definition and activate it only for authorized tenants. |
| PF-03.03 | L03 | Developer and event contracts | Expansion | An integrator can start and inspect a run and handle duplicate events using versioned examples. |
| PF-04.01 | L04 | Tenant and actor access | Fixture | A user from another tenant cannot read task status, results or run events. |
| PF-04.02 | L04 | Approval and source revocation | Pilot | Edits require new approval; revoked sources block affected previews and exports. |
| PF-04.03 | L04 | Enterprise governance | Expansion | Apply provisioning, delegated roles, retention and audit exports under the selected deployment policy. |
| PF-05.01 | L05 | Durable execution | Fixture | Recover or report an explicit failure after a worker stops; expose cancellation and persisted progress. |
| PF-05.02 | L05 | Human checkpoints | Pilot | Pause for a decision and recheck access and approval before resuming. |
| PF-05.03 | L05 | Automation and isolation | Expansion | Schedule and trigger runs, branch safely, isolate code and reconcile a timed-out external write before retry. |
| PF-06.01 | L06 | Source ingestion and provenance | Pilot | Sync one approved source; each citation resolves to an accessible versioned passage. |
| PF-06.02 | L06 | Hybrid retrieval and shared context | Expansion | Compare keyword and semantic retrieval against a fixed set and enforce memory scope when sharing. |
| PF-07.01 | L07 | Deterministic model adapter | Fixture | Demonstrate routing and denial without a live inference request. |
| PF-07.02 | L07 | Approved inference | Pilot | Verify one live route; reject prohibited destinations before sending evidence. |
| PF-07.03 | L07 | Hybrid routing and budgets | Expansion | Choose per-step models and prevent retries and fallback from changing data destination policy. |
| PF-08.01 | L08 | Source adapter contract | Pilot | Report sync health, source identity and permission changes for the pilot connector. |
| PF-08.02 | L08 | Tool ecosystem | Expansion | Add scoped tools, MCP and webhooks; rotate credentials and disable an integration without granting new access. |
| PF-09.01 | L09 | Run diagnostics | Fixture | An authorized operator traces a run, its status and safe error through a correlation ID. |
| PF-09.02 | L09 | Evaluation and release evidence | Pilot | Compare fixed cases and bind results to the exact candidate and dependencies. |
| PF-09.03 | L09 | Analytics and alerting | Expansion | Inspect quality, latency, spend and failure trends by tenant and workflow with restricted telemetry access. |
| PF-10.01 | L10 | Reproducible local environment | Fixture | A developer can run the workspace, API and worker from a documented local profile. |
| PF-10.02 | L10 | Pilot deployment and recovery | Pilot | Verify placement, backup restoration and rollback for the customer’s selected profile. |
| PF-10.03 | L10 | Additional deployment profiles | Expansion | Validate hosted, dedicated, VPC or on-premises profiles separately as customers require them. |

## Catalog interpretation and release evidence

All PF entries are proposed, not implemented. First target is the earliest planned acceptance stage, not a completion status or a promise that the entire capability ships in that stage. The [ownership and delivery matrix](../06-technical/EvolvXSI_Feature-Architecture-Mapping.md#platform-feature-ownership-and-delivery) maps every PF ID to modules and phases. F-01–F-09 and FR-01–FR-12 remain the detailed pilot contracts.

- Pin definitions, inputs, source versions and available inference metadata for audit. Model variability and later source-access changes can prevent identical replay; replay must enforce current access.
- PF-01.03 generated applications require isolated execution, restricted network/tool access, versioned publication and an authorized unpublish action. Generated code receives no implicit credentials or elevated permissions. This is expansion scope.
- PF-01.06 sharing and notifications must recheck the recipient's current authority and source dependencies. Sharing a task does not grant source access.
- PF-02.04 horizontal packs use the same manifest, evaluation, compatibility and tenant activation rules as vertical packs. Dependencies request permissions; they never grant them.
- PF-07.03 admission and retry checks enforce a configured run/tenant budget; unavailable usage is marked unknown and handled by explicit policy. No fallback bypasses destination restrictions.
- Each implemented feature requires positive evidence and applicable denial, revocation, duplicate-request and recovery cases. Record candidate, dependencies, suite, result, reviewer and release decision. An unchecked or unevaluated feature remains planned.
