# EvolvXSI — phased implementation plan

Prepared: 2026-11-02 · Status: planning only; implementation and builds remain paused

## Baseline and implementation rules

The workspace contains 12 independent repository skeletons under src/, a vertical-pack template, product/architecture documents, and downloaded source references. Repository structure exists; application logic, dependency manifests, CI pipelines, deployment configuration and working features do not yet exist.

EvolvXSI owns the platform implementation. Use official provider SDKs behind internal adapters; downloaded agent/application platforms remain references. The [provider SDK decision](EvolvXSI_Provider-SDK-Decision.md) supersedes older fork/runtime-reuse suggestions. Ordinary infrastructure and language dependencies remain necessary. This plan neither installs packages nor authorizes a live API test or production release.

The [first-workflow PRD](../04-specs/EvolvXSI_First-Workflow-PRD.md) owns acceptance; [repository structure](../06-technical/EvolvXSI_Repo-Structure.md) owns code boundaries; [deployment architecture](../06-technical/EvolvXSI_Deployment-Architecture.md) owns service/data responsibilities. Keep exact SDK/library versions and implementation selections in the reference/decision documents rather than product positioning.

No delivery dates or effort estimates are committed. Estimate after P00 selects the workflow, language, deployment and initial inference path. Each phase requires a named accountable owner when implementation is scheduled; do not mark a phase complete because folders exist.

## Phase overview

| Phase | Outcome | Main gate |
| --- | --- | --- |
| P00 | Confirm scope and technical decisions | Decision records, first-workflow scope, initial backlog and acceptance worksheet. |
| P01 | Contracts, identity and development foundation | Versioned contracts, authenticated task API, reproducible local environment and functioning CI for active repositories. |
| P02 | Minimal execution and direct provider integration | First working thin slice: authenticated task submission -> worker -> approved model route -> persisted result -> workspace. |
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

**Repositories:** `apps/workspace`, `apps/control-plane`, `platform/execution`, `platform/hybrid`, `infra/deployment`.

**Prerequisites:** None. Architecture and repository skeletons already exist.

1. Confirm one practitioner, workflow owner, first workflow, source type and output format. Keep research report production as an example until selected.
2. Select the implementation language/framework, initial deployment profile, model/provider and API-client SDK. Decide whether the agent loop is EvolvXSI-owned directly or uses an explicitly selected official agent-loop SDK.
3. Record tenant model, identity provider, data destination restrictions, retention, budget and review requirements. Select one approved inference route initially.
4. Agree on a representative test set and baseline process. Record numeric quality, latency, cost and recovery targets before pilot use; do not invent customer targets.

**Deliverable:** Decision records, first-workflow scope, initial backlog and acceptance worksheet.

**Exit evidence:** Workflow owner and technical owner resolve the decisions needed for the next phase. Missing customer evidence remains marked; generic contract work may proceed without presenting a launch vertical as confirmed.

## P01 — Contracts, identity and development foundation

**Repositories:** `packages/contracts`, `apps/control-plane`, `infra/deployment`.

**Prerequisites:** P00 technical decisions; domain-independent contracts can proceed while discovery continues.

1. Define versioned task, run, event, error, approval, inference, artifact and manifest schemas. Keep provider response objects out of public contracts.
2. Create service authentication and tenant/user authorization primitives. Implement minimal tenant, membership, project and task records with service-owned migrations.
3. Create the local database, dispatch queue, cache, object-storage and secret-reference configuration. Use separate service credentials and queues/cache boundaries.
4. Add per-repository dependency pinning, formatting, type checks and CI. Publish initial contract packages and a deployment manifest pinning compatible versions plus the reviewed documentation commit and approval record.

**Deliverable:** Versioned contracts, authenticated task API, reproducible local environment and functioning CI for active repositories.

**Exit evidence:** A developer can provision the local environment, migrate storage and call an authorized task endpoint. Negative tenant/access cases fail correctly. Contract consumers use released versions rather than cross-repository imports.

## P02 — Minimal execution and direct provider integration

**Repositories:** `platform/execution`, `platform/hybrid`, `apps/control-plane`, `apps/workspace`, `packages/contracts`, `infra/deployment`.

**Prerequisites:** P01.

1. Implement task submission, durable run/job records, database outbox, worker leases, persisted events and basic status streaming. Start with one sequential agent loop.
2. Implement one official provider-client adapter behind the EvolvXSI inference contract. Preserve provider-specific streaming/tool behavior behind capability checks; do not assume protocol parity.
3. Enforce destination allowlists and run budgets before model calls. Record usage, request IDs, errors and safe diagnostic metadata.
4. Add a minimal workspace screen for submitting a task and seeing run status/text output. Support cancellation at safe boundaries and bounded retries.
5. Use controlled fixtures for most integration checks. Configure authorized credentials securely before any live provider test; do not place secrets in source or logs.

**Deliverable:** First working thin slice: authenticated task submission -> worker -> approved model route -> persisted result -> workspace.

**Exit evidence:** A controlled task completes through real service boundaries. Duplicate dispatch does not create duplicate jobs; worker interruption recovers or exposes a clear failure. A prohibited provider route is blocked. Live verification uses only configured authorized access.

## P03 — Policy, approvals and execution isolation

**Repositories:** `apps/control-plane`, `platform/execution`, `platform/hybrid`, `platform/integrations`, `apps/workspace`, `infra/deployment`.

**Prerequisites:** P02; required before customer documents or side-effecting tools are enabled.

1. Implement approval requests/decisions bound to tenant, run, step and immutable payload/artifact version. Reject stale, conflicting or changed-payload approvals.
2. Recheck actor permissions and current policy when consuming approvals, resuming work and invoking tools. Add workflow/connector disable controls.
3. Implement scoped credential references and isolated execution for scripts/browser work when those capabilities are enabled. Apply network/resource limits and run cancellation.
4. Expose pending decisions and safe errors in the workspace. Record audit events without leaking source text or secret values.
5. Test duplicate decisions, policy changes, permission revocation and timeouts with a controlled test tool before any real external write.

**Deliverable:** Working human approval boundary, policy enforcement, audit records and isolation controls for enabled tools.

**Exit evidence:** No protected test action executes without the required authority and exact approval. Changed arguments require a new decision. Disabled resources cannot start new work. Interrupted or timed-out actions have an explicit reconciliation path.

## P04 — Knowledge, evidence and scoped memory

**Repositories:** `platform/knowledge`, `platform/integrations`, `platform/hybrid`, `platform/execution`, `apps/workspace`, `infra/deployment`.

**Prerequisites:** P01-P03.

1. Implement one source-ingestion path with connection status, versioned documents, parsing, passages, access metadata and refresh/error reporting.
2. Build permission-filtered text/vector retrieval with stable source identifiers and citation locations. Route any embedding/reranking request through approved processing destinations.
3. Define explicit session/project/tenant memory scopes and retention. Persist only permitted information and provenance; do not enable uncontrolled cross-user memory.
4. Link generated content to source dependencies. Block affected previews, reports, traces and new export downloads after access revocation until safe redaction/regeneration.
5. Provide source and passage inspection in the workspace; show missing or stale evidence clearly.

**Deliverable:** Authorized evidence retrieval and inspectable citations from one selected source, with documented memory scopes.

**Exit evidence:** Allowed documents are retrievable and denied documents are absent from search and generated content. Revocation blocks source and derived-content access. Unsupported claims are flagged. Source refresh/deletion behavior is demonstrable.

## P05 — Agents, skills and vertical-package contracts

**Repositories:** `platform/agents`, `platform/skills`, `packages/contracts`, `packages/pack-sdk`, `platform/execution`, `apps/control-plane`, `platform/evaluations`, `packs/_template`.

**Prerequisites:** P01-P03; uses the provider and run contracts from P02.

1. Implement schema validation and immutable version identifiers for agent, skill and pack definitions. Pin dependencies and record content digests.
2. Implement the registry lifecycle: draft, validate, evaluate, publish, activate and disable. Tenant grants remain separate from permissions requested by a manifest.
3. Create one shared agent definition and one artifact-oriented skill with input/output schemas, declared dependencies and evaluation cases.
4. Implement pack authoring/validation helpers consuming canonical contract schemas. Validate compatibility, required tools and permissions before activation.
5. Implement a shared evaluation runner in platform/evaluations and a control-plane publication gate. Bind results to immutable candidate, dependency and suite digests, rubric version and configured thresholds. Missing, failed or mismatched evidence blocks publication; unauthorized disclosure, prohibited transmission and unapproved writes always fail. Verify passing, failing and stale-evidence cases before P05 exit.
6. Complete the domain-neutral template. Initialize an active domain repository only after P00 selects the first vertical; never treat the template as an installed pack.

**Deliverable:** Versioned definitions, registry activation and a validated package consumed by the execution runtime.

**Exit evidence:** Invalid manifests, unsupported versions and missing permissions are rejected. A run records exact agent/skill/pack versions. Republishing or editing definitions does not change past runs. A skill cannot grant its own permissions. The P05 evaluation runner blocks publication for missing, failed or stale evidence and permits an authorized publication with matching passing evidence.

## P06 — Complete the reviewed artifact workflow

**Repositories:** `apps/workspace`, `apps/control-plane`, `platform/execution`, `platform/knowledge`, `platform/skills`, `packages/contracts`.

**Prerequisites:** P03-P05.

1. Build task history, plan review, evidence navigation, structured draft display, user edits, revision requests, rejection and final approval.
2. Persist artifact versions and claim-to-source links. Edits to approved content create a new version requiring fresh approval.
3. Implement one agreed export format with citations, export status and authorization at download time.
4. Show waiting/running/failed/cancelled states, safe recovery actions, actor identity, model/tool usage and cost estimates. Mark unavailable cost as unknown.
5. Verify keyboard navigation and the selected accessibility target for the complete task/review/export flow.

**Deliverable:** First complete evidence-based workflow: intake -> plan -> evidence -> draft -> human review -> approved export.

**Exit evidence:** A representative practitioner completes the journey with inspectable evidence and versioned approval. Stale approvals and revoked-source exports fail. History remains understandable after revisions and workflow updates.

## P07 — Broaden orchestration and enterprise integrations

**Repositories:** `platform/execution`, `platform/integrations`, `platform/agents`, `apps/control-plane`, `apps/workspace`, `platform/evaluations`.

**Prerequisites:** P03, P05 and the P06 working workflow. Only capabilities needed by the selected pilot are mandatory before P09.

1. Add bounded delegation, parallel steps and handoffs where the selected workflow benefits. Preserve one execution-state owner and parent/child run linkage.
2. Add schedules, event triggers and scoped external connectors with bounded concurrency and provider rate-limit handling.
3. Implement remote-action idempotency, timeout reconciliation, cancellation propagation and operator/manual-resolution states.
4. Expose scheduler and connector administration and run diagnostics. Keep advanced visual workflow authoring outside this phase unless required by the first customer.

**Deliverable:** Selected multi-step business workflows and integrations with visible ownership and recovery behavior.

**Exit evidence:** Duplicate events do not repeat completed writes. Parent cancellation and worker restarts resolve predictably. Operators can reconcile an unknown remote outcome; permission and approval checks apply across delegated work.

## P08 — Expand hybrid intelligence routes

**Repositories:** `platform/hybrid`, `platform/execution`, `platform/knowledge`, `apps/control-plane`, `infra/deployment`, `platform/evaluations`.

**Prerequisites:** P02-P03. Additional routes can be implemented alongside P07; required before pilot only when its deployment/data policy needs them.

1. Add a second provider or local/private route only against a real capability or privacy need. Keep deterministic work in code/tools and human decisions at explicit review points.
2. Declare route capabilities and test streaming, tool calls, structured outputs, usage accounting and errors for each selected adapter.
3. Implement policy-preserving fallback, capacity limits, admission control, budget accounting and route-level observability.
4. Apply the same destination rules to ingestion processing, embeddings, evaluation and telemetry. Configure local customer connectivity or GPU capacity only if selected.

**Deliverable:** Verified route matrix and policy-aware placement across the inference paths chosen for the customer.

**Exit evidence:** A prohibited fallback is rejected. No route is selected solely because it is cheaper when policy denies it. Per-route quality, latency, cost and failure behavior are measured on representative tasks.

## P09 — Build and validate the first vertical pack

**Repositories:** `packs/<selected-domain>`, `packages/pack-sdk`, `platform/agents`, `platform/skills`, `platform/evaluations`, `apps/workspace`, `platform/knowledge`.

**Prerequisites:** Confirmed P00 domain and P06; complete P07/P08 capabilities specifically required by that domain.

1. Initialize the selected domain repository and implement domain agents, skills, workflows, tool adapters, schemas, templates, review views and evaluation cases.
2. Package the complete domain workflow with compatibility, dependency, permission and review requirements. Reuse shared services through contracts.
3. Extend the P05 runner with the domain-specific representative evaluation suite, review rubric and manual baseline agreed with a workflow owner.
4. Run the pilot workflow end to end, measure practitioner effort, evidence quality, completion, latency and cost, and classify failure modes.
5. Fix blocking quality/policy failures and demonstrate repeat use with representative users before release.

**Deliverable:** One validated vertical package and a reviewed pilot evaluation report.

**Exit evidence:** The agreed numeric quality, cost and latency targets pass on the recorded sample. Unauthorized disclosure, prohibited transmission and unapproved writes are hard failures. Domain experts validate the output and review process.

## P10 — Production hardening and controlled release

**Repositories:** `infra/deployment`, `apps/control-plane`, `apps/workspace`, `platform/execution`, `platform/hybrid`, `platform/knowledge`, `platform/integrations`, `platform/evaluations`.

**Prerequisites:** P09 and all pilot-required P07/P08 work.

1. Provision the selected production environment with least-privilege identities, private data services, tenant quotas, backups, retention/deletion controls and tested restore.
2. Load-test the chosen workload and set capacity/alerts. Scale worker pools by queue age and resource class; document API/data availability and recovery objectives.
3. Run failure/recovery drills, migration and rollback checks, cross-service compatibility checks, and the permission/approval regression suite.
4. Define support ownership, incident procedures, operating costs, release approval, commercial terms and a staged rollout plan.
5. Capture pilot acceptance and a go/no-go decision. Start limited production use and measure outcomes before increasing rollout scope.

**Deliverable:** Pinned release set, deployment/rollback runbooks, recovery evidence and a controlled customer release.

**Exit evidence:** Backup restore and agreed recovery objectives are demonstrated. Critical policy/security failures are resolved. The workflow owner accepts quality and operations evidence; a release owner authorizes rollout.

## P11 — Expand verticals and horizontal product capabilities

**Repositories:** `packs/<next-domain>`, `apps/workspace`, `apps/control-plane`, `platform/execution`, `platform/knowledge`, `platform/hybrid`, `platform/integrations`, `platform/skills`, `platform/evaluations`.

**Prerequisites:** P10 and evidence of repeat use and sustainable operating economics.

1. Choose a second workflow or vertical and measure how much platform code and operating infrastructure it reuses.
2. Add advanced Agent/Workflow Studio, richer collaboration, voice, embedding, or broader artifacts only where customer demand justifies them.
3. Expand skill/connector catalogs with versioned compatibility, owner assignment and outcome evaluations.
4. Extract independently deployed services or infrastructure only for observed load, trust or ownership boundaries. Maintain upgrade and rollback compatibility.

**Deliverable:** Validated expansion with measured reuse and an updated product roadmap.

**Exit evidence:** The next pack operates through existing shared contracts without duplicating identity, checkpoint or routing services. Added capabilities have customers, owners, evaluations and operating-cost evidence.

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

## Phase completion record

For each phase record the accountable owner, selected scope, repository commit/package versions, contract versions, verification commands/reports, observed failures, unresolved risks and exit decision. Keep a single report per gate with reproducible evidence. Cross-service tests run against the exact deployment release manifest. Skill and domain-specific cases remain with their owning packages; shared evaluation tooling aggregates results.

Do not broaden testing without a remaining risk or release gate. Start with contract checks and real boundary/integration tests appropriate to each change, then run the required end-to-end workflow and policy checks. Mocks do not establish provider compatibility, cross-tenant safety or production recovery.

## Risk controls

| Risk | Mitigation |
| --- | --- |
| Scope grows across every vertical before one outcome works | Gate expansion at P11; first paid workflow drives priorities. |
| Provider compatibility is assumed | Capability-based adapters and per-route integration checks in P02/P08. |
| Services diverge across repositories | Versioned contracts, consumer checks and pinned deployment sets from P01. |
| Too many services are deployed before demand | Keep owned boundaries explicit; colocate process images when appropriate and scale workers separately. |
| Model retries duplicate tool side effects | Track invocation identity and approval binding; reconcile remote outcomes before retry. |
| Data leaks through generated content or telemetry | Enforce provenance dependencies, revocation and redaction gates in P03/P04. |
| A skeleton or successful demo is presented as production readiness | Require recorded phase exit evidence and controlled release acceptance in P10. |

## Learning-environment extension

See [learning environments](../06-technical/EvolvXSI_Learning-Environments.md). This proposal adds evaluation detail without making model training a first-release requirement.

- P05-P06: Define environment reset/step/verify contracts, isolated fixtures, recorded trajectories and candidate comparisons with the shared evaluation runner.
- P09: Validate one domain environment with expert-reviewed criteria, baseline and separated training/validation/held-out tasks.
- P11 (optional): Compare instruction/skill/workflow optimization first; authorize model RL separately only with a trainable model/interface, approved data, compute budget and an accountable owner.
- Promotion: Require held-out gains, policy/regression gates, digest-bound approval, controlled rollout and rollback before activating an improved candidate.
