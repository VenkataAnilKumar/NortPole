# EvolvXSI — document review

Reviewed: 2026-11-02 · Scope: product documents, architecture, phased plan and 12 source repository boundaries

## Assessment

The set provides a coherent working definition of a horizontal agent platform with vertical solutions. It is suitable for discovery and a technical spike. It is not yet an implementation baseline: the first customer, workflow, acceptance thresholds, source, deployment model, and visual identity are undecided. The research report is an illustrative workflow, not an owner-approved launch vertical.

## Findings corrected

| Finding | Correction |
| --- | --- |
| Required revision and cost capabilities were P1 stories. | US-12 and US-16 now match first-release priority. |
| API lacked required pause, resume, cancellation, retry, editing, publication, disable, and export retrieval controls. | Added lifecycle contracts and clarified draft creation versus execution. |
| Approval did not specify what happens after edits or changed action arguments. | Bind approvals to exact versions/payloads; require fresh approval after changes and recheck policy at execution. |
| Revocation rules protected source passages but left generated text, previews, and exports ambiguous. | Added source dependencies and conservative withholding/regeneration rules across the PRD, feature, UI, architecture, and data documents. |
| Quality gates could leave authorization failures subject to an unspecified aggregate threshold. | Explicitly block rollout for unauthorized disclosure, prohibited transmission, and unapproved writes. |
| Metrics had no denominator or required decision record. | Added claim/citation metric definitions and a required suite, sample, threshold, and approver record. |
| Task progress, run states, approval, and export were mixed together. | Distinguished execution states, artifact approval states, and export records. |
| Checklist stage numbers diverged from roadmap. | Plan and checklist now follow P00-P11 with matching tasks and phase gates. |
| Renamed overview and implementation files retained old titles. | Aligned titles with filenames. |

## First-release traceability

| PRD requirement | Feature | Stories |
| --- | --- | --- |
| FR-01 Task intake | F-01 | US-01, US-02 |
| FR-02 Ingestion | F-02 | US-04 |
| FR-03 Access | F-02, F-09 | US-05 |
| FR-04 Evidence | F-04 | US-06 |
| FR-05 Workflow | F-03, F-07 | US-08, US-09 |
| FR-06 Human control | F-03, F-05, F-06 | US-08, US-10, US-11, US-12 |
| FR-07 Recovery | F-07 | US-14 |
| FR-08 Model policy | F-06 | US-13 |
| FR-09 History and cost | F-07 | US-09, US-14, US-16 |
| FR-10 Evaluation | F-08 | US-17 |
| FR-11 Export | F-05, F-09 | US-18 |
| FR-12 Administration | F-06, F-09; lifecycle API | US-15 |

## Decisions that remain open

1. **Owner and discovery:** confirm first segment, workflow, buyer, source system, and artifact format.
2. **Workflow owner:** set numeric quality, latency, cost, and reliability targets with a representative test set before pilot rollout.
3. **Product and engineering:** choose the deployment and tenancy model, retention periods, recovery objectives, and credential model.
4. **Engineering:** validate the proposed storage and EvolvXSI-owned runtime through the selected workflow; confirm language, provider and deployment choices in P00.
5. **Product and design:** approve visual tokens, accessibility target, and practitioner prototype; the product name is now EvolvXSI.
6. **Commercial owner:** validate willingness to pay and select pricing, support scope, and procurement terms.

These decisions require customer evidence or owner judgment; the review does not invent answers. The reference document retains its dated official-source review. External sites and licenses were not re-audited during this consistency review, and no application behavior was tested because the workspace has no implementation.

## Follow-up review resolution

All five documentation/repository findings from the follow-up review are addressed in this planning baseline:

| Finding | Resolution | Implementation evidence still required |
| --- | --- | --- |
| Old foundation-extraction direction contradicted the provider decision. | System, deployment and repository documents now specify EvolvXSI-owned implementation and reference-only checkouts. | P00 selects language/provider; P02 verifies the adapter. |
| Task creation could implicitly dispatch execution. | Draft creation creates no job. Explicit run start belongs to execution and atomically records run/job/outbox/idempotency result. API and topology agree. | P02 duplicate, concurrent, timeout and draft-without-job tests. |
| Evaluation publication gate was scheduled too late. | P05 now includes the shared runner, immutable evidence bindings and passing/failing/stale publication tests. P09 extends it for the domain. | P05 enforced gate; P09 domain results. |
| Data model omitted architecture records. | Added explicit owners and contracts for projects/membership, registry/activation, publication evidence, memory, jobs/outbox/inbox and start idempotency. | P01 schema contracts and owning-service migrations in delivery phases. |
| Canonical documents lacked version-control ownership. | Independent evolvxsi-docs repository, ownership rules and release commit/approval pinning specified. | P01 manifest integration and P10 accepted release evidence. |

Also corrected the outdated workspace-name statement, storage status and prior review stage labels. Customer segment, source, deployment, provider, visual identity and numeric targets remain explicit P00 decisions; documentation fixes do not invent those choices. No application implementation, dependency install or build was performed.

## Learning-environment proposal

Added the requested offline learning-environment proposal, environment contracts, repository ownership, held-out evaluation and approval-bound promotion gates. External project details stay in the reference document. Plan and checklist contain matching delivery additions. No training, dependency installation or new source repository was started.
