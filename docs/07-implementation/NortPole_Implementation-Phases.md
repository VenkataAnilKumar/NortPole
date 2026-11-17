# NortPole — phased implementation plan

> **Where this lives in code (2026-11-14).** Service and package names here (`services/control-plane`, `services/execution`, `services/knowledge`, `packages/*`, `evaluations`) are logical owners from the design stage. [Decision 0006](../decisions/0006-scalable-repository-structure.md) maps them to the code: the three services are implemented inside `services/core`, and the packages and evaluations are planned modules in `modules.json`, created when their first code arrives.

Updated: 2026-11-05 · Status: phased delivery proposal; application implementation has not started

## Baseline and implementation rules

The workspace contains module skeletons in the NortPole monorepo, a vertical-pack template, product/architecture documents, and a separate external collection of downloaded source references. Repository structure and its tested validation tooling exist; application logic, dependency manifests, CI pipelines, deployment configuration and working product features do not yet exist.

NortPole owns the platform implementation. Use official provider SDKs behind internal adapters; downloaded agent/application platforms remain references. The [provider SDK decision](NortPole_Provider-SDK-Decision.md) supersedes older fork/runtime-reuse suggestions. Ordinary infrastructure and language dependencies remain necessary. This plan neither installs packages nor authorizes a live API test or production release.

The [first-workflow PRD](../04-specs/NortPole_First-Workflow-PRD.md) owns acceptance; [repository structure](../06-technical/NortPole_Repo-Structure.md) owns code boundaries; [deployment architecture](../06-technical/NortPole_Deployment-Architecture.md) owns service/data responsibilities. Keep exact SDK/library versions and implementation selections in the reference/decision documents rather than product positioning.

No delivery dates or effort estimates are committed. Estimate after P00 selects the workflow, language, deployment and initial inference path. Each phase requires a named accountable owner when implementation is scheduled; do not mark a phase complete because folders exist.

## Delivery milestones

This plan delivers the complete ten-layer NortPole direction through gated increments. Cohere North remains a product benchmark; these phases are NortPole engineering decisions, not a claim about North internals. All application phases below are planned. The completed repository/documentation work is a starting baseline, not completion of P00 or P01.

| Milestone | Phases | Demonstrable outcome | Accountable role |
| --- | --- | --- | --- |
| M0: Decisions ready | P00 | Fixture stack and pilot decision register with owners and measurable gates | Product owner and technical lead |
| M1: Working foundation | P01, P02 fixture gate | Authorized draft, explicit start, durable worker and persisted synthetic result in the workspace | Platform lead |
| M2: Governed execution | P02 live-route gate, P03 | Approved inference plus exact-action approval, isolation and recovery controls | Runtime lead with security reviewer |
| M3: Evidence workflow | P04–P06 | One source, evaluated definitions, cited artifact, review and authorized export | Knowledge and workspace leads |
| M4: Validated vertical | Required P07/P08 subsets, P09 | Selected domain pack passes representative evaluation against a manual baseline | Domain workflow owner |
| M5: Controlled release | P10 | Accepted pilot, tested restore/rollback and operational support | Release owner |
| M6: Broader platform | P11A–P11G | Self-service Studio, reusable packs, enterprise surfaces and measured scale | Product and platform leads |

Roles are responsibilities to assign in P00, not invented staff assignments. Each milestone requires recorded evidence and an acceptance decision. No calendar dates or staffing estimates are committed before the technical spike and customer scope are known.

## Decision gates and work that can proceed

| Gate | Decisions required | Work unlocked |
| --- | --- | --- |
| P00 fixture gate | Language/framework, local persistence/dispatch, identity test strategy, contract tooling, owners | P01 and P02 synthetic slice |
| P00 live-route gate | Selected provider/model, credential mechanism, processing policy, budget and authorized test access | P02 live verification with synthetic inputs |
| P00 pilot gate | Customer/workflow, source, artifact, review roles, deployment, retention, quality/cost/latency/recovery targets | Customer-specific P04/P09 scope and acceptance |
| P03 safety gate | Working authorization, tool approval and required isolation | Protected data processing only with source grants and destination checks; external actions only after action-specific tests |
| P10 release gate | Accepted quality, security, recovery, support and commercial evidence | Controlled production rollout |

P03 can be developed and verified against the P02 fixture while live-route decisions are pending. P04/P05 can use synthetic data during that period. Their live customer acceptance still requires an approved route and the relevant pilot decisions. A delayed provider selection must not force a false P02 completion claim.

## Delivery coverage by engineering layer

| Layer | Initial proof | Expansion |
| --- | --- | --- |
| L01 | P02 task and result; P06 review and export | P07 authoring and operations; P11 wider portals and embedded surfaces |
| L02 | P05 versioned definitions | P09 first vertical pack; P11 prove reuse with a second |
| L03 | P01 draft and identity contracts; P02 explicit start | P05 registry and publication; P07 developer access |
| L04 | P01 tenant isolation; P03 approvals and tool policy | P10 deployment-specific enterprise controls and audit |
| L05 | P02 durable run and fixture | P03 isolated tools; P07 schedules, triggers and recovery |
| L06 | P04 one authorized source and citations | P06 artifact provenance; P11 broaden libraries and retrieval |
| L07 | P02 deterministic adapter first, then one approved live route | P08 additional routes and policy-preserving fallback |
| L08 | P04 one source connector | P07 external tools and triggers; P11 broader ecosystem |
| L09 | P02 events and diagnostics; P05 evaluation gate | P09 domain quality and cost; P10 operating evidence |
| L10 | P01 reproducible local profile | P10 selected production profile, backup and rollback |

P00 separates choices needed for the fixture slice from choices needed for a customer pilot. A fixture run verifies execution and policy boundaries. Live provider integration has its own acceptance evidence.

## Phase overview

| Phase | Outcome | Main gate |
| --- | --- | --- |
| P00 | Confirm scope and technical decisions | Decision records, first-workflow scope, initial backlog and acceptance worksheet. |
| P01 | Contracts, identity and development foundation | Versioned contracts, authenticated task API, reproducible local environment and functioning CI for active modules. |
| P02 | Minimal execution and direct provider integration | Two recorded gates: synthetic draft -> explicit start -> durable worker -> deterministic adapter -> persisted result -> workspace; then separate verification of one approved live route. |
| P03 | Policy, approvals and execution isolation | Working human approval boundary, policy enforcement, audit records and isolation controls for enabled tools. |
| P04 | Knowledge, evidence and scoped memory | Authorized evidence retrieval and inspectable citations from one selected source, with documented memory scopes. |
| P05 | Agents, skills and vertical-package contracts | Versioned definitions, registry activation and a validated package consumed by the execution runtime. |
| P06 | Complete the reviewed artifact workflow | First complete evidence-based workflow: intake -> plan -> evidence -> draft -> human review -> approved export. |
| P07 | Broaden orchestration and enterprise integrations | Selected multi-step business workflows and integrations with visible ownership and recovery behavior. |
| P08 | Expand hybrid intelligence routes | Verified route matrix and policy-aware placement across the inference paths chosen for the customer. |
| P09 | Build and validate the first vertical pack | One validated vertical package and a reviewed pilot evaluation report. |
| P10 | Production hardening and controlled release | Pinned release set, deployment/rollback runbooks, recovery evidence and a controlled customer release. |
| P11 | Expand verticals and horizontal product capabilities | Validated expansion with measured reuse and an updated product roadmap. |

## Dependency and release sequence

P00 -> P01 -> P02 -> P03 -> P04/P05 -> P06. P04 and P05 may proceed in parallel after their prerequisites. P07 and P08 add the capabilities actually required by the first vertical. P09 needs P06, the selected domain and any required P07/P08 work. P10 is the controlled release gate. P11 follows real adoption evidence.

Domain discovery may continue alongside domain-independent foundation work. Protected customer data and external side effects are gated by P03. A second provider, private GPU route, multi-agent collaboration, voice and advanced visual builders are not blanket prerequisites for a one-workflow pilot.

## P00 — Confirm scope and technical decisions

**Modules:** `apps/workspace`, `services/control-plane`, `services/execution`, `services/model-gateway`, `infrastructure`.

**Prerequisites:** None. Architecture and repository skeletons already exist.

1. Confirm one practitioner, workflow owner, first workflow, source type and output format. Keep research report production as an example until selected.
2. Select the implementation language/framework, initial deployment profile, model/provider and API-client SDK. Decide whether the agent loop is NortPole-owned directly or uses an explicitly selected official agent-loop SDK.
3. Record tenant model, identity provider, data destination restrictions, retention, budget and review requirements. Select one approved inference route initially.
4. Agree on a representative test set and baseline process. Record numeric quality, latency, cost and recovery targets before pilot use; do not invent customer targets.

**Deliverable:** Decision records, first-workflow scope, initial backlog and acceptance worksheet.

**Exit evidence:** Workflow owner and technical owner resolve the decisions needed for the next phase. Missing customer evidence remains marked; generic contract work may proceed without presenting a launch vertical as confirmed.

## P01 — Contracts, identity and development foundation

**Modules:** `packages/contracts`, `services/control-plane`, `infrastructure`.

**Prerequisites:** P00 technical decisions; domain-independent contracts can proceed while discovery continues.

1. Define the task, run, event, error and inference contracts needed by the fixture. Extend approval, artifact and manifest contracts in their owning phases. Keep provider response objects out of public contracts.
2. Create service authentication and tenant/user authorization primitives. Implement minimal tenant, membership, project and task records with service-owned migrations.
3. Configure the selected durable local persistence/dispatch and secret-reference mechanism. Add a separate broker, cache or object store only when the active slice requires it. Preserve service-owned state and separate credentials.
4. Add per-module dependency pinning, formatting, type checks and CI. Publish initial contract packages and a deployment manifest pinning compatible versions plus the reviewed documentation commit and approval record.

**Deliverable:** Versioned contracts, authenticated task API, reproducible local environment and functioning CI for active modules.

**Exit evidence:** A developer can provision the local environment, migrate storage and call an authorized task endpoint. Negative tenant/access cases fail correctly. Contract consumers use the versioned interfaces from packages/contracts.

## P02 — Minimal execution and direct provider integration

**Modules:** `services/execution`, `services/model-gateway`, `services/control-plane`, `apps/workspace`, `packages/contracts`, `infrastructure`.

**Prerequisites:** P01.

1. Implement draft saving with zero jobs and a separate authorized start. Atomically persist the run, job, outbox and idempotency result in execution-owned storage. Add worker leases, persisted events and basic status streaming. Start with one sequential agent loop.
2. Implement a deterministic adapter first and record the fixture gate independently. Then implement one official provider-client adapter behind the NortPole inference contract. Preserve provider-specific streaming/tool behavior behind capability checks; do not assume protocol parity.
3. Enforce destination allowlists and run budgets before model calls. Record usage, request IDs, errors and safe diagnostic metadata.
4. Add a minimal workspace screen for submitting a task and seeing run status/text output. Support cancellation at safe boundaries and bounded retries.
5. Use controlled fixtures for most integration checks. Configure authorized credentials securely before any live provider test; do not place secrets in source or logs.

**Deliverable:** Two recorded gates: synthetic draft -> explicit start -> durable worker -> deterministic adapter -> persisted result -> workspace; then separate verification of one approved live route.

**Exit evidence:** Fixture gate: saving a draft creates no job; identical concurrent starts return one run; duplicate dispatch does not duplicate execution; worker interruption recovers or exposes a clear failure; cancellation, tenant denial and prohibited routing are verified using synthetic data. Live-route gate: separately verify the approved adapter with authorized credentials and synthetic inputs. Fixture success does not complete the live-route gate or permit customer-data use before P03.

## P03 — Policy, approvals and execution isolation

**Modules:** `services/control-plane`, `services/execution`, `services/model-gateway`, `packages/integrations`, `apps/workspace`, `infrastructure`.

**Prerequisites:** P02 fixture gate; live-route controls must also pass before live processing. Required before customer documents or side-effecting tools are enabled.

1. Implement approval requests/decisions bound to tenant, run, step and immutable payload/artifact version. Reject stale, conflicting or changed-payload approvals.
2. Recheck actor permissions and current policy when consuming approvals, resuming work and invoking tools. Add workflow/connector disable controls.
3. Implement scoped credential references and isolated execution for scripts/browser work when those capabilities are enabled. Apply network/resource limits and run cancellation.
4. Expose pending decisions and safe errors in the workspace. Record audit events without leaking source text or secret values.
5. Test duplicate decisions, policy changes, permission revocation and timeouts with a controlled test tool before any real external write.
6. Add sensitive-data detection with block/mask/allow actions before any model, tool, export or log destination, and treat retrieved content, tool results and files as untrusted data that cannot grant permissions or select tools (PF-04.04, PF-04.05). Add per-agent autonomy tiers enforced at tool invocation, where approval never overrides a policy block (PF-04.07). Build the fixed redaction and adversarial suites; P04 extends the adversarial suite to retrieved passages.

**Deliverable:** Working human approval boundary, policy enforcement, audit records, isolation controls for enabled tools, redaction, untrusted-content handling and autonomy tiers.

**Exit evidence:** No protected test action executes without the required authority and exact approval. Changed arguments require a new decision. Disabled resources cannot start new work. Interrupted or timed-out actions have an explicit reconciliation path. Seeded sensitive values never reach a forbidden destination; the fixed adversarial suite causes no unapproved call or transmission; a call above its autonomy tier is blocked and approval cannot override a policy block.

## P04 — Knowledge, evidence and scoped memory

**Modules:** `services/knowledge`, `packages/integrations`, `services/model-gateway`, `services/execution`, `apps/workspace`, `infrastructure`.

**Prerequisites:** P01, P02 fixture gate and P03; synthetic development can proceed before the live-route gate. Customer acceptance requires P02 live verification and the selected source grants.

1. Implement one source-ingestion path with connection status, versioned documents, parsing, passages, access metadata and refresh/error reporting.
2. Build permission-filtered text/vector retrieval with stable source identifiers and citation locations. Route any embedding/reranking request through approved processing destinations.
3. Define explicit session/project/tenant memory scopes and retention. Persist only permitted information and provenance; do not enable uncontrolled cross-user memory.
4. Link generated content to source dependencies. Block affected previews, reports, traces and new export downloads after access revocation until safe redaction/regeneration.
5. Provide source and passage inspection in the workspace; show missing or stale evidence clearly.

**Deliverable:** Authorized evidence retrieval and inspectable citations from one selected source, with documented memory scopes.

**Exit evidence:** Allowed documents are retrievable and denied documents are absent from search and generated content. Revocation blocks source and derived-content access. Unsupported claims are flagged. Source refresh/deletion behavior is demonstrable.

## P05 — Agents, skills and vertical-package contracts

**Modules:** `packages/agents`, `packages/skills`, `packages/contracts`, `packages/pack-sdk`, `services/execution`, `services/control-plane`, `evaluations`, `packs/_template`.

**Prerequisites:** P01, P02 fixture gate and P03; uses the inference and run contracts from P02. Live evaluation requires the live-route gate.

1. Implement schema validation and immutable version identifiers for agent, skill and pack definitions. Pin dependencies and record content digests.
2. Implement the registry lifecycle: draft, validate, evaluate, publish, activate and disable. Tenant grants remain separate from permissions requested by a manifest.
3. Create one shared agent definition and one artifact-oriented skill with input/output schemas, declared dependencies and evaluation cases.
4. Implement pack authoring/validation helpers consuming canonical contract schemas. Validate compatibility, required tools and permissions before activation.
5. Implement a shared evaluation runner in evaluations and a control-plane publication gate. Bind results to immutable candidate, dependency and suite digests, rubric version and configured thresholds. Missing, failed or mismatched evidence blocks publication; unauthorized disclosure, prohibited transmission and unapproved writes always fail. Verify passing, failing and stale-evidence cases before P05 exit.
6. Complete the domain-neutral template. Initialize an active domain pack only after P00 selects the first vertical; never treat the template as an installed pack.

**Deliverable:** Versioned definitions, registry activation and a validated package consumed by the execution runtime.

**Exit evidence:** Invalid manifests, unsupported versions and missing permissions are rejected. A run records exact agent/skill/pack versions. Republishing or editing definitions does not change past runs. A skill cannot grant its own permissions. The P05 evaluation runner blocks publication for missing, failed or stale evidence and permits an authorized publication with matching passing evidence.

## P06 — Complete the reviewed artifact workflow

**Modules:** `apps/workspace`, `services/control-plane`, `services/execution`, `services/knowledge`, `packages/skills`, `packages/contracts`.

**Prerequisites:** P03-P05; live end-to-end acceptance also requires the P02 live-route gate.

1. Build task history, plan review, evidence navigation, structured draft display, user edits, revision requests, rejection and final approval.
2. Persist artifact versions and claim-to-source links. Edits to approved content create a new version requiring fresh approval.
3. Implement one agreed export format with citations, export status and authorization at download time.
4. Show waiting/running/failed/cancelled states, safe recovery actions, actor identity, model/tool usage and cost estimates. Mark unavailable cost as unknown.
5. Verify keyboard navigation and the selected accessibility target for the complete task/review/export flow.
6. Add a review inbox listing the decisions the user may act on, and notifications that name the event without protected text; recheck current access when an item is opened (PF-01.08, PF-01.09).

**Deliverable:** First complete evidence-based workflow: intake -> plan -> evidence -> draft -> human review -> approved export, with a review inbox and alerts.

**Exit evidence:** A representative practitioner completes the journey with inspectable evidence and versioned approval. Stale approvals and revoked-source exports fail. History remains understandable after revisions and workflow updates. After source access is revoked, the inbox item and its alert reveal no protected text.

## P07 — Broaden orchestration and enterprise integrations

**Modules:** `services/execution`, `packages/integrations`, `packages/agents`, `services/control-plane`, `apps/workspace`, `evaluations`.

**Prerequisites:** P03, P05 and the P06 working workflow. Only capabilities needed by the selected pilot are mandatory before P09.

1. Add bounded delegation, parallel steps and handoffs where the selected workflow benefits. Preserve one execution-state owner and parent/child run linkage.
2. Add schedules, event triggers and scoped external connectors with bounded concurrency and provider rate-limit handling.
3. Implement remote-action idempotency, timeout reconciliation, cancellation propagation and operator/manual-resolution states.
4. Expose scheduler and connector administration and run diagnostics. Keep advanced visual workflow authoring outside this phase unless required by the first customer.

**Deliverable:** Selected multi-step business workflows and integrations with visible ownership and recovery behavior.

**Exit evidence:** Duplicate events do not repeat completed writes. Parent cancellation and worker restarts resolve predictably. Operators can reconcile an unknown remote outcome; permission and approval checks apply across delegated work.

## P08 — Expand hybrid intelligence routes

**Modules:** `services/model-gateway`, `services/execution`, `services/knowledge`, `services/control-plane`, `infrastructure`, `evaluations`.

**Prerequisites:** P02-P03. Additional routes can be implemented alongside P07; required before pilot only when its deployment/data policy needs them.

1. Add a second provider or local/private route only against a real capability or privacy need. Keep deterministic work in code/tools and human decisions at explicit review points.
2. Declare route capabilities and test streaming, tool calls, structured outputs, usage accounting and errors for each selected adapter.
3. Implement policy-preserving fallback, capacity limits, admission control, budget accounting and route-level observability.
4. Apply the same destination rules to ingestion processing, embeddings, evaluation and telemetry. Configure local customer connectivity or GPU capacity only if selected.

**Deliverable:** Verified route matrix and policy-aware placement across the inference paths chosen for the customer.

**Exit evidence:** A prohibited fallback is rejected. No route is selected solely because it is cheaper when policy denies it. Per-route quality, latency, cost and failure behavior are measured on representative tasks.

## P09 — Build and validate the first vertical pack

**Modules:** `packs/vertical/<selected-domain>`, `packages/pack-sdk`, `packages/agents`, `packages/skills`, `evaluations`, `apps/workspace`, `services/knowledge`.

**Prerequisites:** Confirmed P00 domain and P06; complete P07/P08 capabilities specifically required by that domain.

1. Initialize the selected domain pack and implement domain agents, skills, workflows, tool adapters, schemas, templates, review views and evaluation cases.
2. Package the complete domain workflow with compatibility, dependency, permission and review requirements. Reuse shared services through contracts.
3. Extend the P05 runner with the domain-specific representative evaluation suite, review rubric and manual baseline agreed with a workflow owner.
4. Run the pilot workflow end to end, measure practitioner effort, evidence quality, completion, latency and cost, and classify failure modes.
5. Fix blocking quality/policy failures and demonstrate repeat use with representative users before release.

**Deliverable:** One validated vertical package and a reviewed pilot evaluation report.

**Exit evidence:** The agreed numeric quality, cost and latency targets pass on the recorded sample. Unauthorized disclosure, prohibited transmission and unapproved writes are hard failures. Domain experts validate the output and review process.

## P10 — Production hardening and controlled release

**Modules:** `infrastructure`, `services/control-plane`, `apps/workspace`, `services/execution`, `services/model-gateway`, `services/knowledge`, `packages/integrations`, `evaluations`.

**Prerequisites:** P09 and all pilot-required P07/P08 work.

1. Provision the selected production environment with least-privilege identities, private data services, tenant quotas, backups, retention/deletion controls and tested restore.
2. Load-test the chosen workload and set capacity/alerts. Scale worker pools by queue age and resource class; document API/data availability and recovery objectives.
3. Run failure/recovery drills, migration and rollback checks, cross-service compatibility checks, and the permission/approval regression suite.
4. Define support ownership, incident procedures, operating costs, release approval, commercial terms and a staged rollout plan.
5. Capture pilot acceptance and a go/no-go decision. Start limited production use and measure outcomes before increasing rollout scope.

**Deliverable:** Pinned release set, deployment/rollback runbooks, recovery evidence and a controlled customer release.

**Exit evidence:** Backup restore and agreed recovery objectives are demonstrated. Critical policy/security failures are resolved. The workflow owner accepts quality and operations evidence; a release owner authorizes rollout.

## P11 — Expand verticals and horizontal product capabilities

**Modules:** `packs/vertical/<next-domain>`, `apps/workspace`, `services/control-plane`, `services/execution`, `services/knowledge`, `services/model-gateway`, `packages/integrations`, `packages/skills`, `evaluations`.

**Prerequisites:** P10 and evidence of repeat use and sustainable operating economics.

1. Choose a second workflow or vertical and measure how much platform code and operating infrastructure it reuses.
2. Add advanced Agent/Workflow Studio, richer collaboration, voice, embedding, or broader artifacts only where customer demand justifies them.
3. Expand skill/connector catalogs with versioned compatibility, owner assignment and outcome evaluations.
4. Extract independently deployed services or infrastructure only for observed load, trust or ownership boundaries. Maintain upgrade and rollback compatibility.

**Deliverable:** Validated expansion with measured reuse and an updated product roadmap.

**Exit evidence:** The next pack operates through existing shared contracts without duplicating identity, checkpoint or routing services. Added capabilities have customers, owners, evaluations and operating-cost evidence.

## First working slice: implementation batches

These batches are sequential reviewable changes within P01/P02. They are the proposed first coding scope once P00 fixture decisions are accepted. Each batch preserves the prior working path and includes its own relevant tests.

| Batch | Change | Modules | Required verification |
| --- | --- | --- | --- |
| B01 | Toolchain, local profile, module commands and root CI for active modules | infrastructure/profiles/local, tools, root CI | Fresh setup, structure validation and reproducible check commands |
| B02 | Task/run/error contracts, tenant and actor primitives, owned migrations | packages/contracts, packages/identity-policy, services/control-plane | Contract compatibility, invalid inputs and cross-tenant denial |
| B03 | Save/list/reopen task drafts through authenticated API | services/control-plane, apps/workspace | Draft persists across restart and creates zero jobs; unauthorized reads/writes fail |
| B04 | Explicit start with atomic run/job/outbox and idempotency | services/execution, packages/contracts | Same tenant/task/key returns one run; conflicting reuse rejects; crash between commit and dispatch loses no accepted run |
| B05 | Durable worker with deterministic inference adapter and persisted events/results | services/execution, services/model-gateway | Duplicate dispatch, lease expiry, worker restart, bounded retries, cancellation and prohibited route tests |
| B06 | Workspace progress/result view and fixture evidence report | apps/workspace, services/control-plane, services/execution | User completes draft-to-result flow; refresh/reconnect and tenant-denial cases pass |
| B07 | Separate official provider adapter and live evidence report | services/model-gateway, evaluations | Real protocol behavior, allowed destination, budget/error handling and safe diagnostics with synthetic input |

M1 ends at B06. B07 completes the live-route portion of P02; it is not required to demonstrate the synthetic fixture. Initial schema scope should cover the active slice; extend contracts with their owning feature rather than inventing every future API upfront. Select the simplest durable local topology that satisfies the acceptance cases. Separate cache, broker or object-store processes are introduced when the selected implementation actually needs them.

## P11 expansion delivery stages

P11 remains the canonical expansion phase in feature mappings. The following subphases make the full product direction deliverable. Entry requires P10 and adoption evidence; later capabilities are not removed from product scope because their delivery is staged. Sequence independent subphases according to customer demand after their prerequisites pass.

| Stage | Scope and feature coverage | Primary modules | Dependencies | Exit evidence |
| --- | --- | --- | --- | --- |
| P11A: Agent and Automation Studio | Self-service agent/workflow configuration, candidate comparison, publication, schedules and disable controls, prompt-to-agent drafting, slash commands, signed packages and an agent/tool inventory; PF-01.05, PF-01.11, PF-01.12, PF-02.01, PF-02.05, PF-03.02, PF-03.05, PF-05.03, PF-09.02 | apps/workspace, services/control-plane, services/execution, evaluations | P05 publication gate, P07 selected automation, P10 | Author creates a version, compares evidence and activates it; stale/failed evidence and unauthorized changes fail; running work retains pinned versions |
| P11B: Horizontal and vertical pack reuse | Horizontal bundles, second vertical, catalog, compatibility, upgrades and partner publishing; PF-02.03, PF-02.04, PF-02.06 | packages/agents, packages/skills, packages/pack-sdk, packs/horizontal, packs/vertical | P05, P09, P10; self-service Studio optional | Two verticals reuse one evaluated horizontal bundle; upgrade and rollback preserve existing runs and grants; report actual shared code/configuration reuse |
| P11C: Collaborative workspace and creation | Chat-to-task, libraries, scoped shared context, handoffs, generated applications, mobile review, escalation queues, file parsing, memory controls and freshness handling; PF-01.03, PF-01.06, PF-01.10, PF-05.05, PF-06.02–06.05 | apps/workspace, services/knowledge, services/execution | P04, P06, P10; isolation before generated code runs | Recipient access/revocation works across content and notifications; citations retain permissions; generated apps are isolated, versioned and can be unpublished |
| P11D: Developer and embedded ecosystem | Developer portal, selected SDK, versioned examples, MCP/tools/webhooks, developer sandbox, MCP server and agent-to-agent interfaces, custom tool builder, extension allowlists and extension levels for personal items, and embedded surfaces; PF-01.04, PF-03.03, PF-03.04, PF-08.02–08.06 | apps/developer-portal, sdks, packages/contracts, packages/integrations, services/control-plane | P07 contracts, P10; create planned modules when this work starts | External developer completes a documented integration; scopes, duplicate/replayed events, credential rotation and channel authorization pass |
| P11E: Enterprise and commercial surfaces | Selected enterprise provisioning and delegated administration, trust and support controls, compliance evidence, outcome reporting and metering export; PF-04.03, PF-04.06, PF-01.07, PF-09.06, PF-09.07 | apps/workspace, apps/public-site, services/control-plane, packages/identity-policy, infrastructure | P10 deployment/retention/support baseline | Provisioning and revocation work end to end; support access is scoped/time-bound/audited; public commitments match verified evidence |
| P11F: Scale and deployment breadth | Quality/spend analytics, alerts, additional inference and deployment profiles, inference caching, customer-supplied models, spend controls, shadow-mode evaluation, feedback capture, customer-managed keys and hybrid control/data planes; PF-07.03–07.06, PF-09.03–09.05, PF-10.03–10.05 | infrastructure, services/model-gateway, evaluations, apps/workspace; all service owners | P08 selected route controls, P10; selected expansion workload | Measured load and tenant-fairness targets pass; overload is bounded; policy survives fallback; each new profile separately demonstrates upgrade, restore and rollback |
| P11G: Delegation and browser actions | Bounded multi-agent delegation and browser or computer-use actions, building on the pilot safety controls; PF-05.04, PF-05.06 | services/control-plane, services/execution, services/model-gateway, services/knowledge, packages/identity-policy, evaluations | P03 isolation, policy, redaction and autonomy tiers; P08 selected routes; P10 | A sub-agent never exceeds its parent permissions or budget; delegated calls are checked against the same autonomy tier and redaction rules; browser sessions use no implicit credentials and external effects need exact-action approval; the adversarial suite is replayed with browser content |

P11E extends P10's minimum support/trust controls; those baseline controls cannot be deferred for a production customer. P11F extends baseline monitoring and recovery already required by P02/P10. Voice and model-training experiments require separate scoped decisions and evidence; neither blocks these platform stages. PF-01.08, PF-01.09, PF-04.04, PF-04.05 and PF-04.07 were promoted to the pilot on 2026-11-08 and sit in P06 and P03; P11G builds on them. These additions come after B07 and do not change batches B01–B07. Voice (PF-01.13) and a public marketplace (PF-02.06) are not scheduled in any stage until separately scoped.

## Verification and release discipline

| Verification level | When required | Evidence |
| --- | --- | --- |
| Repository and contract checks | Every affected change | Layout, links, module checks and schema compatibility; update consumers with contracts |
| Service boundary tests | Every implemented state or policy boundary | Real persistence/dispatch where relevant, denied access, retries and failure handling |
| End-to-end acceptance | Each completed milestone | Exact user journey through deployed components; fixtures labeled separately from live processing |
| Quality evaluation | Definition publication and domain release | Immutable candidate/dependency/suite binding, recorded rubric and accepted thresholds |
| Operational acceptance | P10 and each new deployment profile | Load, restore, migration, rollback, alerts and incident ownership |

Tests must cover the risk of the change; passing repository checks alone never proves a service or product feature. Rollout stops for unauthorized disclosure, prohibited data transmission or an unapproved write regardless of average quality scores. External actions with uncertain outcomes require reconciliation before retry.

Each implementation change records phase/batch IDs, affected PF/FR IDs, owner, scope, tests and migration impact. Each gate records the exact revision/artifacts, environment, input/suite versions, observed results, unresolved defects, acceptance decision and rollback procedure where applicable. Keep customer data and secrets out of repository evidence; store approved evidence artifacts in an access-controlled location and commit only permitted references or synthetic summaries.

## Estimation and execution cadence

After the P00 fixture gate, estimate B01–B06 from the chosen stack and available team. Re-estimate pilot phases after source and workflow discovery; estimate P11 stages individually after adoption priorities are known. Track work as planned, in progress, blocked, in review or accepted. A deferred optional pilot capability is marked deferred with a reason, never complete.

At each milestone review, demonstrate the working behavior, compare evidence against the agreed gate, update the remaining dependencies and choose the next bounded scope. Parallel work is suitable for P04/P05 after shared contracts stabilize, and for selected P07/P08 work after their prerequisites. Assign explicit reviewers for cross-module changes.

## Requirement coverage and evidence

| PRD | Main phases | Required evidence |
| --- | --- | --- |
| FR-01 Task intake | P01, P02, P06 | Authorized create/search/reopen with tenant scoping. |
| FR-02 Ingestion | P04 | Source ingestion, status, failures and refresh. |
| FR-03 Access-aware retrieval | P03, P04, P10 | Denied source and derived-content cases pass. |
| FR-04 Evidence provenance | P04, P06, P09 | Claims resolve to permitted passages or are flagged unsupported. |
| FR-05 Workflow | P02, P05, P06 | Version-pinned execution with persisted review points. |
| FR-06 Human control | P03, P06 | Pause, revision, rejection and exact-version approval. |
| FR-07 Failure handling | P02, P03, P07, P10 | Recovery, duplicate dispatch and external-outcome reconciliation. |
| FR-08 Model policy | P02, P03, P08 | Destination blocks and policy-preserving fallback. |
| FR-09 Run history | P02, P06 | Authorized run events, versions, usage/cost and safe errors. |
| FR-10 Evaluation | P01, P05, P09, P10 | P05 runner and enforced publication gate; P09 domain suite; P10 release regression evidence. |
| FR-11 Export | P06 | Approved immutable version, citations and download access checks. |
| FR-12 Administration | P03, P06, P10 | Disable/revoke changes affect new and active work as specified. |
| FR-13 Agent safety controls | P03, P04 | Redaction and adversarial suites pass; autonomy tiers block calls above tier. |
| FR-14 Review inbox and notifications | P06 | Inbox and alerts work and reveal no protected text after revocation. |

## Phase completion record

For each phase record the accountable owner, selected scope, repository commit/package versions, contract versions, verification commands/reports, observed failures, unresolved risks and exit decision. Keep a single report per gate with reproducible evidence. Cross-service tests run against the exact deployment release manifest. Skill and domain-specific cases remain with their owning packages; shared evaluation tooling aggregates results.

Do not broaden testing without a remaining risk or release gate. Start with contract checks and real boundary/integration tests appropriate to each change, then run the required end-to-end workflow and policy checks. Mocks do not establish provider compatibility, cross-tenant safety or production recovery.

## Risk controls

| Risk | Mitigation |
| --- | --- |
| Scope grows across every vertical before one outcome works | Gate expansion at P11; first paid workflow drives priorities. |
| Provider compatibility is assumed | Capability-based adapters and per-route integration checks in P02/P08. |
| Modules and deployed versions diverge | Versioned contracts, consumer checks and pinned deployment sets from P01. |
| Too many services are deployed before demand | Keep owned boundaries explicit; colocate process images when appropriate and scale workers separately. |
| Model retries duplicate tool side effects | Track invocation identity and approval binding; reconcile remote outcomes before retry. |
| Data leaks through generated content or telemetry | Enforce provenance dependencies, revocation and redaction gates in P03/P04. |
| A skeleton or successful demo is presented as production readiness | Require recorded phase exit evidence and controlled release acceptance in P10. |

## Learning-environment extension

See [learning environments](../06-technical/NortPole_Learning-Environments.md). This proposal adds evaluation detail without making model training a first-release requirement.

- P05-P06: Define environment reset/step/verify contracts, isolated fixtures, recorded trajectories and candidate comparisons with the shared evaluation runner.
- P09: Validate one domain environment with expert-reviewed criteria, baseline and separated training/validation/held-out tasks.
- P11 (optional): Compare instruction/skill/workflow optimization first; authorize model RL separately only with a trainable model/interface, approved data, compute budget and an accountable owner.
- Promotion: Require held-out gains, policy/regression gates, digest-bound approval, controlled rollout and rollback before activating an improved candidate.

## Reference-only implementation workstream

**Owner direction confirmed: 2026-11-05.** The owner selected the attached local/web reference approach. This supersedes the intervening fork, copy and rebrand proposals. NortPole will study product behavior and source implementations, then implement its own contracts, modules, interfaces and tests. No build-versus-fork prototype is scheduled by this plan.

### Boundaries

- Product and source research are allowed. Downloaded application platforms stay outside the product build and Git tree.
- Do not copy or adapt upstream implementation files, snippets, prompts/skills, tests, frontend assets or deployment templates into NortPole under this workstream. Renaming symbols or branding does not change that boundary.
- Write original NortPole code and acceptance cases from our requirements and documented design decisions. Credit the references in the design record without claiming their code as ours.
- Ordinary libraries, databases and official provider clients remain separately selectable dependencies. Record purpose, version, license, maintenance and integration boundary before adoption. A reference-study entry never silently authorizes a dependency.
- No application-platform fork, runtime adoption, copied connector or enterprise component is selected. Any future departure requires a new explicit owner decision; it is outside the planned work below.
- Preserve the existing local collection and provenance manifests. Do not relabel all local projects commercially proven. NorthWritX remains outside NortPole scope.

### Evidence and reference selection

Use the [commercial research](NortPole_Commercial_Reference_Research.md) and [local source mapping](NortPole_Source-Repository-Mapping.md) as starting registers. The current collection has 15 recorded project snapshots; a workflow reference product and the upstream core are the primary local product references in the selected approach. Other local snapshots remain supplemental and must meet the commercial-evidence gate before they become primary phase references.

Temporal, LiteLLM, Langfuse, Qdrant, Infisical, E2B, Appsmith, Dify, n8n and Airbyte are web-reviewed references, not newly acquired local checkouts. Their roles below are design-study assignments, not dependencies. Dify, n8n and Airbyte must be labeled source-available/restricted rather than treated as unrestricted open-source foundations. Mixed-license projects require component/edition boundaries in the record.

For each selected study, verify official source availability and license at the exact revision, a commercial offering, named organizational adoption evidence, and a specific NortPole feature question. Prefer detailed customer accounts; label named-user lists as weaker evidence. A customer story does not establish which edition or public-code feature was used. If evidence cannot be verified, record the limitation and use a stronger primary reference; do not delay independent implementation waiting for optional research.

Local snapshots are historical evidence. Record the manifest revision separately from current upstream findings; do not claim a local checkout contains a feature shown on a newer website. Refresh official evidence at the relevant phase. Research conclusions are engineering judgments, not performance guarantees or license clearance for copying.

### Phase-by-phase study and implementation

| Phase | Primary references to study | NortPole-owned output | Required acceptance |
| --- | --- | --- | --- |
| P00: Scope and decisions | a workflow reference product/upstream-core product journeys; commercial register | Selected fixture/pilot scope, reference shortlist, dependency decision register, owner assignments | Every primary reference has provenance, commercial-evidence grade and a concrete study question; unresolved decisions remain explicit |
| P01: Contracts and foundation | a workflow reference product authorization and API boundaries; Infisical identity concepts | Tenant/task/run contracts, state ownership, authentication primitives, local setup and root CI | Invalid contracts and cross-tenant access fail; dependencies are explicitly selected and pinned |
| P02: First working slice | Temporal recovery semantics; a workflow reference product task/run UX; LiteLLM adapter behavior; Langfuse trace concepts | NortPole atomic start, worker lifecycle, deterministic adapter, original workspace and run events | B01–B06 fixture tests pass, including zero-job draft, duplicate start and worker failure; B07 live evidence remains separate |
| P03: Secure actions | Temporal recovery; Infisical scoped credentials; E2B isolation lifecycle | Approval bindings, policy checks, isolated tool boundary and reconciliation states | Changed payload and revoked authority fail; cancellation/resource limits work; uncertain writes are reconciled before retry |
| P04: Knowledge fabric | Local upstream-core ingestion/indexing; Qdrant retrieval concepts; Airbyte sync lifecycle | Original connector contract, ingestion, access-aware retrieval, source versions and derived-content dependencies | Denied/revoked documents remain unavailable in passages, generated text, traces and exports; sync/deletion cases pass |
| P05: Definitions and quality gates | a workflow reference product/Dify publication journey; Langfuse datasets and evaluation flow | NortPole agent/skill/pack manifests, registry, runner and publication gate | Failed, stale or mismatched evidence blocks publication; manifest permissions never grant authority |
| P06: Complete workspace | a workflow reference product/upstream-core evidence interaction; Appsmith operational screen patterns | Original review/edit/approve/export experience and accessible components | User completes the evidence workflow; edits invalidate approval; export rechecks access; keyboard flow passes |
| P07: Automation and ecosystem | n8n trigger/operator journeys; Temporal durable scheduling; Airbyte connector failures | NortPole schedules, events, integration adapters and manual recovery controls | Duplicate/replayed events do not repeat completed writes; disabled resources cannot start work; expired credentials fail safely |
| P08: Hybrid inference | LiteLLM routing/capability concepts | NortPole policy-preserving routing, budget accounting and selected adapters | Prohibited fallback fails before transmission; unknown usage is explicit; each enabled route has real compatibility evidence |
| P09: First vertical pack | Relevant Dify workflow/Appsmith view patterns plus selected domain evidence | Original domain workflow, template, reviewer rules and evaluation suite | Domain owner accepts the recorded sample and agreed targets; generic reference products are not treated as complete vertical packs |
| P10: Controlled production | Selected references' official deployment/recovery documentation; Langfuse operational experience | NortPole release manifests, quotas, safe telemetry, runbooks and support controls | Tested restore, rollback, tenant isolation and release acceptance for the selected deployment |
| P11A–P11G: Expansion | a workflow reference product/Dify Studio; n8n automations; Appsmith views; upstream-core context; LiteLLM/Langfuse operations | Original self-service Studio, horizontal-pack reuse, collaboration, developer surfaces and scale controls | Apply each P11 subphase gate; prove reuse across verticals and validate every added deployment profile separately |

The existing phase specifications and PF/FR mappings remain authoritative for detailed acceptance. The study matrix adds research inputs, not new requirements to integrate those products. Study only the selected component behavior needed for the current phase.

### Work sequence within each phase

1. **Scope:** Select PF/FR IDs and a bounded design question. Assign a module owner and reviewer.
2. **Inspect:** Read the relevant official docs, pinned source paths and upstream tests; record what was actually inspected versus merely located.
3. **Decide:** Describe our required behavior, state owner, failure modes, differences from the references and any separate dependency proposal.
4. **Implement:** Write NortPole code against its own contracts, using the approved repository boundaries. Keep research checkouts out of imports, build contexts and deployment images.
5. **Verify:** Run original acceptance tests through the relevant persistence, authorization and service boundaries. A reference product's passing tests are not NortPole evidence.
6. **Review:** Check origin of added files/assets and dependency changes; reject unapproved upstream imports or copied platform material. Record the phase evidence and remaining gaps.

### Reference record template

Store a concise record alongside the affected architecture decision or reference document. Do not create a second competing product specification.

| Field | Required content |
| --- | --- |
| Study ID and status | Stable ID; planned, inspected, decision recorded or verified |
| Phase and features | Pxx/Bxx/P11x and relevant PF/FR IDs |
| Owner and reviewer | Assigned people before implementation |
| Question | Specific user behavior or engineering failure mode |
| Source provenance | Official repository URL, immutable revision, exact paths, local manifest entry if applicable and inspection date |
| Commercial evidence | Official offering and named adoption link; case study versus vendor list; edition uncertainty |
| License boundary | Relevant revision's license files, enterprise exceptions and source-available classification; reference-only disposition |
| Findings | Observed behavior and limitations; distinguish inspected code from documentation claims |
| NortPole decision | Original design, state owner, contracts, rejected alternatives and differences |
| Dependencies | None selected, or link to a separate approved dependency decision |
| Acceptance | Tests, suite/input versions, results and candidate commit; evidence location without customer data/secrets |

### Immediate next scope

Begin with P00 fixture decisions and four bounded studies: explicit task/run lifecycle in a workflow reference product, crash/retry semantics in Temporal, capability/destination boundaries in LiteLLM, and run correlation in Langfuse. Produce an NortPole contract sketch and B01–B06 backlog before coding. Live provider choice can remain separate until B07. Upstream-core/Qdrant studies become active with P04; do not study every reference exhaustively before delivering the fixture.

This strategy trades some initial implementation effort for direct control over NortPole behavior. Estimates must include research, original implementation, integration and verification; no fork-based time saving is assumed. Dates remain unset until stack, staffing and pilot decisions are accepted.

## Feature acceptance tracking

Use the [platform feature catalog](../04-specs/NortPole_Feature-Spec.md#full-platform-feature-catalog) alongside FR-01–FR-12. Track each implemented PF entry with a release target and acceptance evidence. Keep expansion entries in the roadmap until their prerequisites and rollout scope are agreed.

## Pre-implementation readiness gate

The documentation and skeleton are ready for P00 decisions, not yet a selected application stack. Before B01, assign the technical owner/reviewer and record language/framework, dependency tooling, durable local topology, development identity strategy and CI commands. No live provider or pilot vertical is required for B01–B06.

P02 must implement the [restricted fixture definition](../06-technical/NortPole_API-Design.md#development-fixture-definition-before-publication-exists) before P05 publication exists. Record the pinned definition and profile guard tests; customer/production profiles reject this bootstrap. P05 replaces it with evaluated registry resolution before customer release.

Before B07, select the provider/model, authorized credential setup, destination rules and test budget. Before customer-specific acceptance, select the workflow owner, source, review roles, deployment constraints and measurable quality/latency/cost/recovery targets. These remain unresolved decisions rather than implied choices from the topology diagram.
