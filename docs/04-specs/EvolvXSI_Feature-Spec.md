# EvolvXSI — feature specification

Status: **draft for the candidate first workflow** · Updated: 2026-11-04

This specification translates the [PRD](EvolvXSI_First-Workflow-PRD.md) into feature behavior. It is intentionally independent of implementation projects. The selected customer workflow may change field names, source types, and output format.

## F-01 Task intake and status

**Inputs:** title, question, scope, desired output, optional source constraints. **Behavior:** validate inputs, create a task owned by the initiating user, assign a run ID on execution, and show status transitions. **Errors:** missing required fields, unavailable workflow, denied access. **Acceptance:** a user can create, find, cancel, and reopen authorized tasks without losing the request.

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
