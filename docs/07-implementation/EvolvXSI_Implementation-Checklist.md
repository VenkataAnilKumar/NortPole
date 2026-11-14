# NortPole — implementation checklist

> **Where this lives in code (2026-11-14).** Service and package names here (`services/control-plane`, `services/execution`, `services/knowledge`, `packages/*`, `evaluations`) are logical owners from the design stage. [Decision 0006](../decisions/0006-scalable-repository-structure.md) maps them to the code: the three services are implemented inside `services/core`, and the packages and evaluations are planned modules in `modules.json`, created when their first code arrives.

Updated: 2026-11-05 · Status: execution checklist; phases not started

The monorepo module skeletons and vertical template are in place. Those completed setup actions do not satisfy any implementation gate below. Builds and dependency installation remain paused. This checklist follows the [phased plan](EvolvXSI_Implementation-Phases.md).

## P00 — Confirm scope and technical decisions

- [ ] Confirm one practitioner, workflow owner, first workflow, source type and output format. Keep research report production as an example until selected.
- [ ] Select the implementation language/framework, initial deployment profile, model/provider and API-client SDK. Decide whether the agent loop is NortPole-owned directly or uses an explicitly selected official agent-loop SDK.
- [ ] Record tenant model, identity provider, data destination restrictions, retention, budget and review requirements. Select one approved inference route initially.
- [ ] Agree on a representative test set and baseline process. Record numeric quality, latency, cost and recovery targets before pilot use; do not invent customer targets.
- [ ] Publish deliverable: Decision records, first-workflow scope, initial backlog and acceptance worksheet.
- [ ] Record accountable owner and exit evidence: Workflow owner and technical owner resolve the decisions needed for the next phase. Missing customer evidence remains marked; generic contract work may proceed without presenting a launch vertical as confirmed.

## P01 — Contracts, identity and development foundation

- [ ] Define the task, run, event, error and inference contracts needed by the fixture. Extend approval, artifact and manifest contracts in their owning phases. Keep provider response objects out of public contracts.
- [ ] Create service authentication and tenant/user authorization primitives. Implement minimal tenant, membership, project and task records with service-owned migrations.
- [ ] Configure the selected durable local persistence/dispatch and secret-reference mechanism. Add a separate broker, cache or object store only when the active slice requires it. Preserve service-owned state and separate credentials.
- [ ] Add per-module dependency pinning, formatting, type checks and CI. Publish initial contract packages and a deployment manifest pinning compatible versions plus the reviewed documentation commit and approval record.
- [ ] Publish deliverable: Versioned contracts, authenticated task API, reproducible local environment and functioning CI for active modules.
- [ ] Record accountable owner and exit evidence: A developer can provision the local environment, migrate storage and call an authorized task endpoint. Negative tenant/access cases fail correctly. Contract consumers use the versioned interfaces from packages/contracts.

## P02 — Minimal execution and direct provider integration

- [ ] Implement draft saving with zero jobs and a separate authorized start. Atomically persist the run, job, outbox and idempotency result in execution-owned storage. Add worker leases, persisted events and basic status streaming. Start with one sequential agent loop.
- [ ] Implement a deterministic adapter first and record the fixture gate independently. Then implement one official provider-client adapter behind the NortPole inference contract. Preserve provider-specific streaming/tool behavior behind capability checks; do not assume protocol parity.
- [ ] Enforce destination allowlists and run budgets before model calls. Record usage, request IDs, errors and safe diagnostic metadata.
- [ ] Add a minimal workspace screen for submitting a task and seeing run status/text output. Support cancellation at safe boundaries and bounded retries.
- [ ] Use controlled fixtures for most integration checks. Configure authorized credentials securely before any live provider test; do not place secrets in source or logs.
- [ ] Publish deliverable: Two recorded gates: synthetic draft -> explicit start -> durable worker -> deterministic adapter -> persisted result -> workspace; then separate verification of one approved live route.
- [ ] Record accountable owner and exit evidence: Fixture gate: saving a draft creates no job; identical concurrent starts return one run; duplicate dispatch does not duplicate execution; worker interruption recovers or exposes a clear failure; cancellation, tenant denial and prohibited routing are verified using synthetic data. Live-route gate: separately verify the approved adapter with authorized credentials and synthetic inputs. Fixture success does not complete the live-route gate or permit customer-data use before P03.

## P03 — Policy, approvals and execution isolation

- [ ] Implement approval requests/decisions bound to tenant, run, step and immutable payload/artifact version. Reject stale, conflicting or changed-payload approvals.
- [ ] Recheck actor permissions and current policy when consuming approvals, resuming work and invoking tools. Add workflow/connector disable controls.
- [ ] Implement scoped credential references and isolated execution for scripts/browser work when those capabilities are enabled. Apply network/resource limits and run cancellation.
- [ ] Expose pending decisions and safe errors in the workspace. Record audit events without leaking source text or secret values.
- [ ] Test duplicate decisions, policy changes, permission revocation and timeouts with a controlled test tool before any real external write.
- [ ] Add sensitive-data detection with block/mask/allow before any model, tool, export or log destination; treat retrieved content, tool results and files as untrusted data that cannot grant permissions or select tools.
- [ ] Enforce per-agent autonomy tiers at tool invocation; approval never overrides a policy block. Build and pass the fixed redaction and adversarial suites.
- [ ] Publish deliverable: Working human approval boundary, policy enforcement, audit records, isolation controls, redaction, untrusted-content handling and autonomy tiers.
- [ ] Record accountable owner and exit evidence: No protected test action executes without the required authority and exact approval. Changed arguments require a new decision. Disabled resources cannot start new work. Interrupted or timed-out actions have an explicit reconciliation path.

## P04 — Knowledge, evidence and scoped memory

- [ ] Implement one source-ingestion path with connection status, versioned documents, parsing, passages, access metadata and refresh/error reporting.
- [ ] Build permission-filtered text/vector retrieval with stable source identifiers and citation locations. Route any embedding/reranking request through approved processing destinations.
- [ ] Define explicit session/project/tenant memory scopes and retention. Persist only permitted information and provenance; do not enable uncontrolled cross-user memory.
- [ ] Link generated content to source dependencies. Block affected previews, reports, traces and new export downloads after access revocation until safe redaction/regeneration.
- [ ] Provide source and passage inspection in the workspace; show missing or stale evidence clearly.
- [ ] Publish deliverable: Authorized evidence retrieval and inspectable citations from one selected source, with documented memory scopes.
- [ ] Record accountable owner and exit evidence: Allowed documents are retrievable and denied documents are absent from search and generated content. Revocation blocks source and derived-content access. Unsupported claims are flagged. Source refresh/deletion behavior is demonstrable.

## P05 — Agents, skills and vertical-package contracts

- [ ] Implement schema validation and immutable version identifiers for agent, skill and pack definitions. Pin dependencies and record content digests.
- [ ] Implement the registry lifecycle: draft, validate, evaluate, publish, activate and disable. Tenant grants remain separate from permissions requested by a manifest.
- [ ] Create one shared agent definition and one artifact-oriented skill with input/output schemas, declared dependencies and evaluation cases.
- [ ] Implement pack authoring/validation helpers consuming canonical contract schemas. Validate compatibility, required tools and permissions before activation.
- [ ] Implement a shared evaluation runner in evaluations and a control-plane publication gate. Bind results to immutable candidate, dependency and suite digests, rubric version and configured thresholds. Missing, failed or mismatched evidence blocks publication; unauthorized disclosure, prohibited transmission and unapproved writes always fail. Verify passing, failing and stale-evidence cases before P05 exit.
- [ ] Complete the domain-neutral template. Initialize an active domain pack only after P00 selects the first vertical; never treat the template as an installed pack.
- [ ] Publish deliverable: Versioned definitions, registry activation and a validated package consumed by the execution runtime.
- [ ] Record accountable owner and exit evidence: Invalid manifests, unsupported versions and missing permissions are rejected. A run records exact agent/skill/pack versions. Republishing or editing definitions does not change past runs. A skill cannot grant its own permissions. The P05 evaluation runner blocks publication for missing, failed or stale evidence and permits an authorized publication with matching passing evidence.

## P06 — Complete the reviewed artifact workflow

- [ ] Build task history, plan review, evidence navigation, structured draft display, user edits, revision requests, rejection and final approval.
- [ ] Persist artifact versions and claim-to-source links. Edits to approved content create a new version requiring fresh approval.
- [ ] Implement one agreed export format with citations, export status and authorization at download time.
- [ ] Show waiting/running/failed/cancelled states, safe recovery actions, actor identity, model/tool usage and cost estimates. Mark unavailable cost as unknown.
- [ ] Verify keyboard navigation and the selected accessibility target for the complete task/review/export flow.
- [ ] Add the review inbox and notifications; alerts carry no protected text and opening an item rechecks current access.
- [ ] Publish deliverable: First complete evidence-based workflow: intake -> plan -> evidence -> draft -> human review -> approved export.
- [ ] Record accountable owner and exit evidence: A representative practitioner completes the journey with inspectable evidence and versioned approval. Stale approvals and revoked-source exports fail. History remains understandable after revisions and workflow updates.

## P07 — Broaden orchestration and enterprise integrations

- [ ] Add bounded delegation, parallel steps and handoffs where the selected workflow benefits. Preserve one execution-state owner and parent/child run linkage.
- [ ] Add schedules, event triggers and scoped external connectors with bounded concurrency and provider rate-limit handling.
- [ ] Implement remote-action idempotency, timeout reconciliation, cancellation propagation and operator/manual-resolution states.
- [ ] Expose scheduler and connector administration and run diagnostics. Keep advanced visual workflow authoring outside this phase unless required by the first customer.
- [ ] Publish deliverable: Selected multi-step business workflows and integrations with visible ownership and recovery behavior.
- [ ] Record accountable owner and exit evidence: Duplicate events do not repeat completed writes. Parent cancellation and worker restarts resolve predictably. Operators can reconcile an unknown remote outcome; permission and approval checks apply across delegated work.

## P08 — Expand hybrid intelligence routes

- [ ] Add a second provider or local/private route only against a real capability or privacy need. Keep deterministic work in code/tools and human decisions at explicit review points.
- [ ] Declare route capabilities and test streaming, tool calls, structured outputs, usage accounting and errors for each selected adapter.
- [ ] Implement policy-preserving fallback, capacity limits, admission control, budget accounting and route-level observability.
- [ ] Apply the same destination rules to ingestion processing, embeddings, evaluation and telemetry. Configure local customer connectivity or GPU capacity only if selected.
- [ ] Publish deliverable: Verified route matrix and policy-aware placement across the inference paths chosen for the customer.
- [ ] Record accountable owner and exit evidence: A prohibited fallback is rejected. No route is selected solely because it is cheaper when policy denies it. Per-route quality, latency, cost and failure behavior are measured on representative tasks.

## P09 — Build and validate the first vertical pack

- [ ] Initialize the selected domain pack and implement domain agents, skills, workflows, tool adapters, schemas, templates, review views and evaluation cases.
- [ ] Package the complete domain workflow with compatibility, dependency, permission and review requirements. Reuse shared services through contracts.
- [ ] Extend the P05 runner with the domain-specific representative evaluation suite, review rubric and manual baseline agreed with a workflow owner.
- [ ] Run the pilot workflow end to end, measure practitioner effort, evidence quality, completion, latency and cost, and classify failure modes.
- [ ] Fix blocking quality/policy failures and demonstrate repeat use with representative users before release.
- [ ] Publish deliverable: One validated vertical package and a reviewed pilot evaluation report.
- [ ] Record accountable owner and exit evidence: The agreed numeric quality, cost and latency targets pass on the recorded sample. Unauthorized disclosure, prohibited transmission and unapproved writes are hard failures. Domain experts validate the output and review process.

## P10 — Production hardening and controlled release

- [ ] Provision the selected production environment with least-privilege identities, private data services, tenant quotas, backups, retention/deletion controls and tested restore.
- [ ] Load-test the chosen workload and set capacity/alerts. Scale worker pools by queue age and resource class; document API/data availability and recovery objectives.
- [ ] Run failure/recovery drills, migration and rollback checks, cross-service compatibility checks, and the permission/approval regression suite.
- [ ] Define support ownership, incident procedures, operating costs, release approval, commercial terms and a staged rollout plan.
- [ ] Capture pilot acceptance and a go/no-go decision. Start limited production use and measure outcomes before increasing rollout scope.
- [ ] Publish deliverable: Pinned release set, deployment/rollback runbooks, recovery evidence and a controlled customer release.
- [ ] Record accountable owner and exit evidence: Backup restore and agreed recovery objectives are demonstrated. Critical policy/security failures are resolved. The workflow owner accepts quality and operations evidence; a release owner authorizes rollout.

## P11 — Expand verticals and horizontal product capabilities

- [ ] Choose a second workflow or vertical and measure how much platform code and operating infrastructure it reuses.
- [ ] Add advanced Agent/Workflow Studio, richer collaboration, voice, embedding, or broader artifacts only where customer demand justifies them.
- [ ] Expand skill/connector catalogs with versioned compatibility, owner assignment and outcome evaluations.
- [ ] Extract independently deployed services or infrastructure only for observed load, trust or ownership boundaries. Maintain upgrade and rollback compatibility.
- [ ] Publish deliverable: Validated expansion with measured reuse and an updated product roadmap.
- [ ] Record accountable owner and exit evidence: The next pack operates through existing shared contracts without duplicating identity, checkpoint or routing services. Added capabilities have customers, owners, evaluations and operating-cost evidence.

## Release evidence record

- [ ] Every required phase has a named owner and accepted exit report.
- [ ] Release manifest pins tested service/package/pack versions, documentation commit and recorded approval.
- [ ] Numeric acceptance thresholds and sample sizes are recorded.
- [ ] Unauthorized disclosure, prohibited transmission and unapproved writes have no unresolved failures.
- [ ] Production rollout has an explicit go/no-go decision and rollback owner.

## Learning-environment evidence

- [ ] P05-P06: Define environment reset/step/verify contracts, isolated fixtures, recorded trajectories and candidate comparisons with the shared evaluation runner.
- [ ] P09: Validate one domain environment with expert-reviewed criteria, baseline and separated training/validation/held-out tasks.
- [ ] P11 (optional): Compare instruction/skill/workflow optimization first; authorize model RL separately only with a trainable model/interface, approved data, compute budget and an accountable owner.
- [ ] Promotion: Require held-out gains, policy/regression gates, digest-bound approval, controlled rollout and rollback before activating an improved candidate.

## Ten-layer delivery evidence

Use the [layer delivery map](EvolvXSI_Implementation-Phases.md#delivery-coverage-by-engineering-layer). Record fixture results separately from live provider verification. A passing fixture does not satisfy the live route gate.

## Platform feature traceability

- [ ] Use the [complete PF ownership and phase matrix](../06-technical/EvolvXSI_Feature-Architecture-Mapping.md#platform-feature-ownership-and-delivery) to select feature IDs for each release.
- [ ] Record each selected feature's accountable person, dependencies, acceptance cases and evidence; keep unselected expansion features planned.
- [ ] Record P02 fixture and live-route decisions separately; never mark the full phase complete from fixture evidence alone.
- [ ] For P11, verify self-service Studio, collaboration, horizontal-pack reuse and applicable public/support surfaces against their PF acceptance criteria.

## Milestone and batch tracking

- [ ] P00: Assign accountable people and record separate fixture, live-route and pilot decisions.
- [ ] M1: Complete B01–B06 with accepted fixture evidence; do not mark live inference complete.
- [ ] M2: Complete B07 and P03 with approved inference, policy and action-control evidence.
- [ ] M3: Complete P04–P06 with citations, publication evaluation and authorized export.
- [ ] M4: Complete P09 and only the P07/P08 subsets required by the selected vertical.
- [ ] M5: Accept P10 operational, commercial and release evidence before production rollout.
- [ ] M6: Schedule P11 subphases from adoption needs and record acceptance separately.

See [implementation batches](EvolvXSI_Implementation-Phases.md#first-working-slice-implementation-batches) and [decision gates](EvolvXSI_Implementation-Phases.md#decision-gates-and-work-that-can-proceed). P03 and synthetic P04/P05 work can proceed after the fixture gate; live customer acceptance still requires the live-route and pilot gates.

## P11 expansion acceptance

- [ ] P11A: Author, evaluate, publish and disable a workflow through Studio; deny stale/failed evidence and preserve running versions; confirm prompt-to-agent drafts cannot bypass the evaluation gate and only signed, approved packages install.
- [ ] P11B: Reuse a horizontal bundle in two verticals; verify compatibility, grants, upgrade and rollback; confirm partner packages pass manifest, evaluation and security review.
- [ ] P11C: Verify collaborative access, notifications, revocation and scoped context; isolate generated applications before execution; verify the review inbox, escalation queues, mobile approval, file parsing, memory controls and conflict handling.
- [ ] P11D: Complete an external integration through documented SDK/API contracts; test channel identity, scopes, duplicate events and credential rotation; verify sandbox isolation, MCP server and agent-to-agent scopes, and extension allowlists; verify extension levels (Off, Request, Self-serve) and that personal items never widen access or use a blocked route.
- [ ] P11E: Verify chosen enterprise provisioning, delegated roles, support access and evidence-backed public commitments; verify compliance evidence exports, outcome reports and metering exports.
- [ ] P11F: Meet agreed workload targets, bounded overload and tenant fairness; separately accept each added inference/deployment profile; verify spend controls, tenant-scoped caching, customer-supplied model routes, shadow-mode evaluation, feedback capture, customer-managed keys and any hybrid control/data-plane profile.
- [ ] P11G: Confirm sub-agents never exceed parent permissions or budget, delegated calls obey the same tiers and redaction, browser sessions hold no implicit credentials, and the adversarial suite passes with browser content.

Use the [expansion delivery stages](EvolvXSI_Implementation-Phases.md#p11-expansion-delivery-stages) for module owners and dependencies. Estimate only selected scope with an assigned team. Baseline security, support, monitoring and recovery remain required before expansion.

## Reference-only workstream gates

- [ ] P00: Assign owners and select bounded studies with commercial evidence; retain supplemental local projects without promoting them automatically.
- [ ] Each phase: Record official URL, immutable revision, inspected paths, local/web distinction, license boundaries and adoption evidence.
- [ ] Each phase: Write the NortPole design decision and original acceptance cases before implementing the selected behavior.
- [ ] Each phase: Keep downloaded application platforms outside imports, build contexts and deployment images; review new code/assets for unapproved copying.
- [ ] Each dependency change: Record a separate purpose/version/license/maintenance decision; reference selection is not dependency approval.
- [ ] P02: Complete the four initial studies and B01–B06 fixture evidence; keep B07 live verification separate.
- [ ] P04–P10: Apply the phase study matrix to knowledge, policy, quality and release work without adopting upstream runtime ownership.
- [ ] P11: Apply the same provenance and acceptance gates to Studio, packs, portals and scaling.

See the [reference-only implementation workstream](EvolvXSI_Implementation-Phases.md#reference-only-implementation-workstream). Application copying, forks and codebase rebranding are outside the selected plan.

## Final readiness checks before coding

- [ ] Before B01: record the fixture stack/toolchain, durable local topology, development identity strategy, accountable owner/reviewer and CI commands.
- [ ] P02: add a fixed synthetic definition with content digest and local allowlist; test mismatch/unlisted definitions and reject bootstrap in customer/production profiles.
- [ ] P05: replace fixture definition resolution with evaluated publication/activation before customer release.
- [ ] P03/P04: persist action receipts in Execution and source cursors in Knowledge; integrations remains adapter code with no independent database.
- [ ] P06: recheck current authority on every new protected download/range request; an old storage URL cannot bypass revocation.
- [ ] Before B07 and pilot acceptance: close the separately listed provider and customer decisions without marking fixture evidence as live acceptance.
