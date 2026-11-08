# EvolvXSI — feature specification

Status: **platform catalog and first-workflow specification** · Updated: 2026-11-08

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

## F-10 Review inbox and notifications (proposed; PF-01.08, PF-01.09)

**Status:** proposed expansion; becomes pilot scope only if the owner promotes it. **Inputs:** a pending decision, escalation or completed run for a recipient. **Behavior:** one inbox lists the items the user may act on now, with task, step, due time and state. A notification names the event and links to the item; it carries no source text, artifact text or citation. Opening an item rechecks the recipient's role and current source access. Users choose channels and quiet hours; administrators can require a channel for approvals. Duplicate events produce one item and one alert. **Errors:** item already resolved (show the outcome), access lost (item disappears and the link shows a generic denial), channel failure (retry, then leave the inbox item as the source of truth). **Acceptance:** an approver finds and resolves a pending approval from the inbox; after source access is revoked, the item and its alert link reveal no protected text; a replayed event creates no second item.

## F-11 Sensitive-data redaction (proposed; PF-04.04)

**Inputs:** content bound for a model, tool, export or log, and the tenant's detection rules. **Behavior:** detect configured kinds (such as personal identifiers and credentials) before transmission and apply the rule action: block, mask, or allow with a recorded reason. The decision is made by the policy engine, not the model. Detection events store the kind, location and rule version, never the value. A rule set activates only after a fixed test suite passes. **Errors:** detector unavailable (fail closed for protected classifications), rule conflict (the stricter action wins). **Acceptance:** seeded sensitive values never reach a model or tool destination that policy forbids; traces and exports show masked values; a changed rule set is not active until its suite passes; false-positive and false-negative rates are reported against a fixed corpus.

## F-12 Prompt-injection and exfiltration defense (proposed; PF-04.05)

**Inputs:** retrieved passages, tool results, files and web content treated as untrusted data. **Behavior:** untrusted content is separated from instructions and cannot grant permissions, change the plan, or select a tool. Tool calls are checked against the run's declared tools and the autonomy tier regardless of what the content says. Outbound content is checked against destination policy and the sensitivity of its sources. A suspected injection is recorded as a finding and the run continues without acting on it, or pauses for review per policy. **Errors:** policy block (no override by approval), ambiguous finding (pause for review). **Acceptance:** a fixed adversarial suite of hostile documents, tool results and pages produces no unapproved tool call, no prohibited transmission and no permission change; the suite is replayed before any model, prompt or tool change is published. Passing the suite is evidence, not a guarantee.

## F-13 Per-agent guardrails and autonomy tiers (proposed; PF-04.07)

**Inputs:** an agent, its tier and its limits. **Behavior:** tiers are draft-only, act-with-approval and act-within-limits. Limits cover allowed tools and actions, call count, run duration and cost. The platform enforces the tier at tool invocation, so a prompt cannot raise it. Approval satisfies an approval requirement but never overrides a policy block. Tier or limit changes are versioned, audited and apply to new runs; a run keeps the version it started with. **Errors:** call above tier (blocked with a clear reason and a path to request a change), limit reached (pause and notify). **Acceptance:** a draft-only agent cannot invoke a side-effecting tool; an act-with-approval call without a bound approval is blocked; an administrator change does not alter an in-flight run; every block appears in the run history.

## F-14 Spend controls (proposed; PF-07.06)

**Inputs:** a quota scope (tenant, project, user, agent or workflow), period, limit and alert thresholds. **Behavior:** the model gateway checks the remaining budget before each invocation and again before a retry. Alerts fire at configured thresholds. At the limit the policy is block, pause for approval, or downgrade to an allowed cheaper route; the downgrade never uses a destination the tenant policy forbids. When usage is unknown it is marked unknown and handled by the configured policy. **Errors:** limit reached (state the scope and how to request more), usage feed delayed (apply the unknown-usage policy). **Acceptance:** a run that would exceed its limit is stopped or paused per policy; the threshold alert fires once; a retry cannot bypass the limit; no fallback uses a prohibited route. Quotas count estimated usage, not invoiced price.

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
| PF-01.08 | L01 | Review inbox | Expansion | A reviewer sees pending plan, tool-approval and final-approval requests across authorized tasks; a request is withheld once the reviewer loses task or source access. |
| PF-01.09 | L01 | User notifications | Expansion | Approval, failure and completion alerts reach the right user by email or chat; delivery rechecks current access and omits protected titles and text for recipients without it. |
| PF-01.10 | L01 | Mobile review and approval | Expansion | A reviewer can open a claim source, request revision or approve the exact version on a narrow screen without the approval control hiding report content. |
| PF-01.11 | L01 | Prompt-to-agent drafting | Expansion | An author describes a workflow in natural language and receives a draft definition that must pass the same evaluation and publication gate; nothing is published or activated automatically. |
| PF-01.12 | L01 | Slash commands and saved prompts | Expansion | A user starts a permitted skill or saved task template from the workspace; a command for a skill the user cannot access is absent and also rejected by the server. |
| PF-01.13 | L01 | Voice channel | Expansion | A voice session starts the same authorized task and approval flow as the workspace. This needs a separately scoped decision and is excluded from the first release. |
| PF-02.01 | L02 | Agents and skills | Pilot | A configured workflow pins its agent and skill versions; later edits leave past run definitions and evidence unchanged. Exact model-output replay is not guaranteed. |
| PF-02.02 | L02 | Vertical pack lifecycle | Pilot | Validate and activate a pack with a domain workflow, template, reviewer rule and evaluation cases. |
| PF-02.03 | L02 | Catalog and pack upgrades | Expansion | Compare pack versions, check compatibility and activate a tested upgrade for one tenant. |
| PF-02.04 | L02 | Horizontal capability packs | Expansion | Reuse a versioned domain-neutral workflow and skill bundle in two verticals without duplicating identity, execution, routing or audit. |
| PF-02.05 | L02 | Signed skill and plugin packages | Expansion | An administrator installs a signed, versioned package after review; unsigned, tampered or unapproved packages are rejected, and declared permissions grant nothing by themselves. |
| PF-02.06 | L02 | Partner publishing and marketplace | Expansion | A third party submits a package that passes manifest validation, evaluation and security review before tenant administrators can see it. A public marketplace stays outside the first release. |
| PF-03.01 | L03 | Task and run contracts | Fixture | Public contracts separate draft from start; concurrent identical starts return one run. |
| PF-03.02 | L03 | Registry and publication | Pilot | Publish the exact evaluated definition and activate it only for authorized tenants. |
| PF-03.03 | L03 | Developer and event contracts | Expansion | An integrator can start and inspect a run and handle duplicate events using versioned examples. |
| PF-03.04 | L03 | Developer sandbox | Expansion | A developer starts runs against a synthetic test tenant with test keys; sandbox keys and data cannot reach production tenants. |
| PF-03.05 | L03 | Agent and tool inventory | Expansion | An administrator lists each active agent, skill, connector and tool with owner, pinned version, last run and tenant activation, and can disable any of them. |
| PF-04.01 | L04 | Tenant and actor access | Fixture | A user from another tenant cannot read task status, results or run events. |
| PF-04.02 | L04 | Approval and source revocation | Pilot | Edits require new approval; revoked sources block affected previews and exports. |
| PF-04.03 | L04 | Enterprise governance | Expansion | Apply provisioning, delegated roles, retention and audit exports under the selected deployment policy. |
| PF-04.04 | L04 | Sensitive-data detection and redaction | Expansion | Configured sensitive fields are detected and redacted before model transmission, trace storage and export under tenant policy; miss rate on a fixed test set is reported, and unauthorized disclosure blocks rollout. |
| PF-04.05 | L04 | Prompt-injection and exfiltration defense | Expansion | Retrieved, tool and web content is treated as untrusted data; a fixed adversarial suite shows injected instructions cannot trigger an unapproved tool call or send content to a prohibited destination. |
| PF-04.06 | L04 | Compliance evidence and reports | Expansion | Audit exports and control evidence can be produced for selected frameworks such as SOC 2, ISO 27001 and ISO 42001. Certification itself is an organizational process outside product acceptance. |
| PF-04.07 | L04 | Per-agent guardrails and autonomy tiers | Expansion | An administrator sets read-only, draft-only or act-with-approval tiers per agent and tool; a call above the assigned tier is blocked, and approval never overrides a policy block. |
| PF-05.01 | L05 | Durable execution | Fixture | Recover or report an explicit failure after a worker stops; expose cancellation and persisted progress. |
| PF-05.02 | L05 | Human checkpoints | Pilot | Pause for a decision and recheck access and approval before resuming. |
| PF-05.03 | L05 | Automation and isolation | Expansion | Schedule and trigger runs, branch safely, isolate code and reconcile a timed-out external write before retry. |
| PF-05.04 | L05 | Bounded multi-agent delegation | Expansion | A parent run delegates to pinned sub-agents within a budget; a sub-agent never gains permissions the parent lacks, and the trace records each delegation. |
| PF-05.05 | L05 | Escalation routing and work queues | Expansion | Failures, low-evidence results and policy holds route to a named reviewer queue with run state preserved; an unavailable reviewer leaves the run in a recoverable waiting state. |
| PF-05.06 | L05 | Browser and computer-use actions | Expansion | An isolated session acts only on allowlisted sites or apps without implicit credentials; any external side effect needs approval bound to the exact action, and the session trace is reviewable. |
| PF-06.01 | L06 | Source ingestion and provenance | Pilot | Sync one approved source; each citation resolves to an accessible versioned passage. |
| PF-06.02 | L06 | Hybrid retrieval and shared context | Expansion | Compare keyword and semantic retrieval against a fixed set and enforce memory scope when sharing. |
| PF-06.03 | L06 | Document parsing and file ingestion | Expansion | Uploaded and synced files in selected formats become versioned passages with locations; unsupported or failed files show their status and are excluded from citations. |
| PF-06.04 | L06 | Memory controls | Expansion | A user can view, edit and delete scoped memory and an administrator can restrict memory scopes; a deleted item is not used by later runs. |
| PF-06.05 | L06 | Freshness and conflict handling | Expansion | Stale, superseded, duplicate and conflicting sources are flagged in retrieval and on the evidence view; a draft marks conflicts instead of choosing silently. |
| PF-07.01 | L07 | Deterministic model adapter | Fixture | Demonstrate routing and denial without a live inference request. |
| PF-07.02 | L07 | Approved inference | Pilot | Verify one live route; reject prohibited destinations before sending evidence. |
| PF-07.03 | L07 | Hybrid routing and budgets | Expansion | Choose per-step models and prevent retries and fallback from changing data destination policy. |
| PF-07.04 | L07 | Tenant-scoped inference caching | Expansion | Cached model responses are scoped to tenant and policy version, honor destination and retention rules and are invalidated on revocation; cross-tenant reads fail. |
| PF-07.05 | L07 | Customer-supplied and tuned models | Expansion | A tenant registers a private or fine-tuned model route that passes the same policy and evaluation checks. Training itself remains a separate decision (see learning environments). |
| PF-07.06 | L07 | Spend controls | Expansion | Administrators set user, group and organization quotas, rate limits and caps; alerts fire before a limit, and an exhausted limit stops new work without changing destination policy. |
| PF-08.01 | L08 | Source adapter contract | Pilot | Report sync health, source identity and permission changes for the pilot connector. |
| PF-08.02 | L08 | Tool ecosystem | Expansion | Add scoped tools, MCP and webhooks; rotate credentials and disable an integration without granting new access. |
| PF-08.03 | L08 | MCP server and agent-to-agent interfaces | Expansion | An authorized external client starts or inspects runs through versioned MCP or agent-to-agent interfaces that enforce the same tenant, scope and approval rules as the public API. |
| PF-08.04 | L08 | Custom tool builder and OpenAPI import | Expansion | An author imports an API description or writes a tool and declares its actions, credential scope and side-effect class; the tool is unusable until reviewed and activated. |
| PF-08.05 | L08 | Extension allowlists and per-tool permissions | Expansion | Administrators allow or block MCP servers and tools, separate read from write permission and review a call log; tool descriptions are treated as untrusted and a blocked server is never called. |
| PF-09.01 | L09 | Run diagnostics | Fixture | An authorized operator traces a run, its status and safe error through a correlation ID. |
| PF-09.02 | L09 | Evaluation and release evidence | Pilot | Compare fixed cases and bind results to the exact candidate and dependencies. |
| PF-09.03 | L09 | Analytics and alerting | Expansion | Inspect quality, latency, spend and failure trends by tenant and workflow with restricted telemetry access. |
| PF-09.04 | L09 | Simulation and shadow-mode evaluation | Expansion | A candidate runs on simulated tasks or beside the live version without external writes or user-visible output; results bind to the exact candidate and enter publication evidence. |
| PF-09.05 | L09 | Feedback capture | Expansion | Accept, edit, reject and correction signals are stored with the artifact version; production feedback enters evaluation datasets only with authorization, tenant isolation and redaction. |
| PF-09.06 | L09 | Outcome and ROI reporting | Expansion | A workflow owner sees completion rate, reviewer time, corrections and cost per completed task against the agreed manual baseline, with sample sizes. |
| PF-09.07 | L09 | Usage metering and billing export | Expansion | Usage by tenant, workflow and completed task exports to an external billing system. Pricing and invoicing stay outside this catalog until pricing is validated. |
| PF-10.01 | L10 | Reproducible local environment | Fixture | A developer can run the workspace, API and worker from a documented local profile. |
| PF-10.02 | L10 | Pilot deployment and recovery | Pilot | Verify placement, backup restoration and rollback for the customer’s selected profile. |
| PF-10.03 | L10 | Additional deployment profiles | Expansion | Validate hosted, dedicated, VPC or on-premises profiles separately as customers require them. |
| PF-10.04 | L10 | Customer-managed keys and data residency | Expansion | A tenant dataset is encrypted under a customer-managed key and stored in a selected region; revoking the key stops reads, and a restore shows key and region constraints still hold. |
| PF-10.05 | L10 | Hybrid control and data planes | Expansion | Customer-side runners keep documents, indexes and credentials local while a cloud control plane distributes signed definitions and policy over an outbound-only connection; the local side keeps enforcing policy offline. Align with the deployment architecture before selection. |

## Catalog interpretation and release evidence

All PF entries are proposed, not implemented. First target is the earliest planned acceptance stage, not a completion status or a promise that the entire capability ships in that stage. The [ownership and delivery matrix](../06-technical/EvolvXSI_Feature-Architecture-Mapping.md#platform-feature-ownership-and-delivery) maps every PF ID to modules and phases. F-01–F-09 and FR-01–FR-12 remain the detailed pilot contracts.

- Pin definitions, inputs, source versions and available inference metadata for audit. Model variability and later source-access changes can prevent identical replay; replay must enforce current access.
- PF-01.03 generated applications require isolated execution, restricted network/tool access, versioned publication and an authorized unpublish action. Generated code receives no implicit credentials or elevated permissions. This is expansion scope.
- PF-01.06 sharing and notifications must recheck the recipient's current authority and source dependencies. Sharing a task does not grant source access.
- PF-02.04 horizontal packs use the same manifest, evaluation, compatibility and tenant activation rules as vertical packs. Dependencies request permissions; they never grant them.
- PF-07.03 admission and retry checks enforce a configured run/tenant budget; unavailable usage is marked unknown and handled by explicit policy. No fallback bypasses destination restrictions.
- PF-01.08–13, PF-02.05–06, PF-03.04–05, PF-04.04–07, PF-05.04–06, PF-06.03–05, PF-07.04–06, PF-08.03–05, PF-09.04–07 and PF-10.04–05 were added on 2026-11-08 from a comparison with common enterprise agent-platform capabilities. All are proposed expansion scope; none changes the first-release commitment in the PRD.
- The product owner should decide whether PF-01.08, PF-01.09, PF-04.04, PF-04.05, PF-04.07 and PF-07.06 move to the pilot target before the first customer deployment. Until then they remain expansion.
- PF-01.13 voice and any public marketplace under PF-02.06 need separate scoped decisions. PF-04.06 covers evidence for compliance work, not certification. PF-09.07 exports metering only and sets no price. PF-10.05 is a proposed topology that must be reconciled with the deployment architecture before it is selected.
- Each implemented feature requires positive evidence and applicable denial, revocation, duplicate-request and recovery cases. Record candidate, dependencies, suite, result, reviewer and release decision. An unchecked or unevaluated feature remains planned.
