# EvolvXSI — first workflow PRD

Status: **draft for discovery** · Updated: 2026-11-05

## 1. Objective

Deliver one production-style, evidence-based agent workflow on a reusable platform. The initial scenario used here is **research report production**. The domain, user, and report type must be confirmed before customer-specific implementation and pilot acceptance. Domain-independent synthetic fixture work may proceed after P00 fixture decisions. This PRD gives a testable shape to the first release without treating the scenario as a settled market decision.

## Reference pilot scenario

Use a question such as “Which operating procedures changed, and what should the team review?” to exercise FR-01 through FR-12 with synthetic documents. Include two versions of a permitted procedure, a restricted passage, and one question the documents cannot answer. The reviewer should see a cited change and an explicit evidence gap, correct the draft, and export only the approved version. Revoking a source must also restrict subsequent views of dependent text. This example leaves the customer, source type, and final format open for discovery.

## 2. Primary user journey

1. An administrator connects an approved knowledge source, sets access policy, configures permitted models and tools, and publishes a versioned workflow.
2. A practitioner saves a task draft with a question, scope, and desired output, then explicitly starts a run. Saving the draft dispatches no work.
3. The system retrieves authorized evidence, records provenance, and produces a plan or outline.
4. The practitioner reviews the plan and can refine scope before execution continues.
5. The agent drafts a structured report with citations linked to source passages and flags missing or conflicting evidence.
6. The practitioner edits or rejects the draft and approves the final artifact.
7. The system preserves the task, sources, agent version, model and tool calls, feedback, approval, and final output for review.

## 3. Functional requirements

| ID | Requirement | First-release acceptance criterion |
| --- | --- | --- |
| FR-01 | Workspace and task intake | A permitted user can create, reopen, and search tasks with title, request, status, and owner. |
| FR-02 | Source ingestion | Admin can connect at least one selected source type; ingestion exposes status and failures. |
| FR-03 | Access-aware retrieval | A run uses only documents the initiating user may access; denied content is absent from responses and citations. |
| FR-04 | Evidence provenance | Every factual claim designated as evidence-based links to a retrievable source passage, or is explicitly marked unsupported. |
| FR-05 | Agent workflow | A versioned workflow executes intake, retrieval, drafting, review, and finalization with persisted state. |
| FR-06 | Human control | Practitioner can pause, revise scope, reject a draft, and approve the final artifact; external write actions require explicit approval. |
| FR-07 | Failure handling | Failed steps show a useful error and can be retried without duplicating completed external actions. |
| FR-08 | Model policy | Admin can restrict permitted model destinations by data class; a prohibited route is blocked before sending content. |
| FR-09 | Run history | Authorized users can see inputs, evidence, key decisions, tool calls, version, timing, cost estimate, and outcome. |
| FR-10 | Evaluation | Team can run a fixed test set against a workflow version and compare results before publication. |
| FR-11 | Export | Practitioner can export the approved report and its citation list in one agreed format. |
| FR-12 | Administration | Admin can disable a workflow or connector and revoke its tool access. |

## 4. Nonfunctional requirements

- **Security:** tenant and user authorization are enforced at ingestion, retrieval, tool invocation, export, and run-history access. Secrets stay outside prompts and logs.
- **Privacy:** data destination policy is explicit and tested; content does not fall back to an unapproved model provider.
- **Reliability:** runs persist state and recover predictably from worker restarts. Side-effecting tools use idempotency keys or equivalent protection.
- **Observability:** each run has a correlation ID, structured events, errors, and a visible status.
- **Quality:** the pilot has a reviewed evaluation set covering citation accuracy, unsupported claims, task completeness, and unsafe or unauthorized actions.
- **Accessibility:** the main task, review, and approval flow is keyboard usable and follows the team's chosen accessibility standard.
- **Performance and cost:** set thresholds after a pilot baseline; measure time to first useful draft, total completion time, model spend, and failure rate.

## 5. Explicit release exclusions

- General public agent marketplace.
- Multiple verticals at launch.
- Unsupervised publication or external business actions.
- Automatic agent self-rewriting in production.
- Claims that outputs are expert advice or independently verified research.

## 6. Release gates

1. **Discovery gate:** name the buyer, practitioner, workflow, baseline process, and measurable pain from interviews.
2. **Feasibility gate:** demonstrate source permissions, citations, approval, and an end-to-end run with the EvolvXSI-owned implementation.
3. **Pilot gate:** pass the agreed evaluation set and security review; document known failure modes and operator procedures.
4. **Release gate:** repeated pilot use, acceptable cost and latency, support owner, incident path, and commercial terms.

## 7. Measurements

Track workflow completion rate, practitioner time per completed artifact, citation verification rate, unsupported-claim rate, approval/revision rate, run failure rate, median and tail latency, model cost per completed task, and weekly active pilot users. Compare against a manual baseline and inspect errors by category.

## 8. Open questions

- Which vertical and workflow has an accessible design partner and budget owner?
- What source systems, data classification, retention, and deployment constraints apply?
- What artifact format and review standard does the practitioner use today?
- Which actions may an agent take automatically, and which require approval?
- What quality and operational thresholds constitute a paid pilot?


## 9. Approval and access invariants

First-release external writes require approval bound to the exact action, target, payload, run, and actor. Changed arguments require fresh approval. Recheck permissions and policy at execution; approval cannot override a policy block. Editing an approved artifact creates a new version requiring final approval.

Generated reports, task history, logs, and exports inherit restrictions from their sources. Sharing a task does not grant source access. After access revocation, withhold affected generated content on subsequent reads and exports until it can be redacted or regenerated from permitted evidence. Previously downloaded files cannot be recalled; make that limitation explicit in the pilot agreement.

## 10. Evaluation and release decision

Before rollout, the workflow owner records the suite version, rubric, baseline, numeric quality and latency targets, cost limit, sample size, and release approver. Pending targets block release. Unauthorized disclosure, prohibited transmission, and unapproved external writes block rollout regardless of aggregate scores.

Citation verification rate is supported citations divided by reviewed citations. Unsupported-claim rate is unsupported material factual claims divided by reviewed material factual claims, including claims without citations. Report sample size and review method. Define completion and failure from terminal run states and report cancellations separately.

## Layer acceptance

The first engineering slice proves authorized draft, explicit start, durable execution, a deterministic adapter and persisted status. The pilot adds real retrieval, inference, review and export. Use the [requirement-to-layer map](../06-technical/EvolvXSI_Feature-Architecture-Mapping.md#layer-traceability-for-the-first-release) to assign acceptance evidence.
