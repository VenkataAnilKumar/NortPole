# EvolvXSI â€” document review

Reviewed: 2026-11-05 Â· Scope: product documents, architecture, phased plan and monorepo module boundaries

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
| Canonical documents lacked version-control ownership. | Canonical docs/ in the product monorepo, ownership rules and release commit/approval pinning specified. | P01 manifest integration and P10 accepted release evidence. |

Also corrected the outdated workspace-name statement, storage status and prior review stage labels. Customer segment, source, deployment, provider, visual identity and numeric targets remain explicit P00 decisions; documentation fixes do not invent those choices. No application implementation, dependency install or build was performed.

## Learning-environment proposal

Added the requested offline learning-environment proposal, environment contracts, repository ownership, held-out evaluation and approval-bound promotion gates. External project details stay in the reference document. Plan and checklist contain matching delivery additions. No training, dependency installation or new source repository was started.


## Monorepo alignment â€” 2026-11-05

The working tree now uses a single product layout with separate module owners. The first customer workflow and implementation stack remain open. The product retains separate draft and start actions. The execution module owns atomic run creation. The current repository structure supersedes the independent-repository proposal recorded above.

## Ten-layer documentation review

The system architecture now defines L01â€“L10. Product coverage, surfaces, requirement traceability and delivery phases point to that model. The pilot vertical, technology selections and deployment profile remain open.

## Product feature consistency review â€” 2026-11-05

| Finding | Correction |
| --- | --- |
| PF catalog lacked a complete module and delivery mapping. | Every PF entry now has a primary module, collaborators and phase mapping; the checklist requires evidence for selected IDs. |
| Studio, collaboration, horizontal packs and commercial/support surfaces lacked explicit feature acceptance. | Added PF-01.05â€“07 and PF-02.04; connected stories, surface coverage and product packaging. All remain proposed expansion scope. |
| P02 wording conflated a fixture with live inference and omitted atomic draft/start semantics from checklist tasks. | Defined separate fixture/live-route gates in both plan and checklist, with duplicate-start, recovery and authorization evidence. |
| Version pinning implied reproducible model output. | Replaced that promise with immutable definitions/evidence and explicit limits on replay. |
| Journey implied export happened as part of approval. | Separated explicit start, artifact approval and separately authorized export. |
| Ownership tables and governance retained old repository wording. | Corrected module paths, supporting-module terminology and monorepo documentation ownership. |

Validation covers local document links and anchors, catalog IDs against the ownership matrix, referenced module paths and matching P02 gates. This is a documentation consistency review: no application behavior, competitor capabilities or external licenses were re-audited. Product and technical owners still need to select the pilot workflow, stack, deployment and measurable release thresholds. No implementation or release approval is implied.

## Approved repository alignment â€” 2026-11-05

Applied the modular monorepo direction: relocated the control-plane skeleton, aligned backend interface/adapter folders, aligned evaluation and infrastructure names, and updated module references. Future applications and shared utilities remain explicitly planned. Original files and numbered documents are preserved. The structure validator checks module paths, local links and obsolete references; no application behavior is claimed.

## Repository follow-up review — 2026-11-05

- Corrected two remaining delivery-plan pack paths to the vertical namespace.
- Added responsibilities to planned inventory entries and documented existing local-profile and preserved scaffolding locations.
- Strengthened structure validation to reject duplicate existing/planned paths, unsafe paths, inconsistent maturity and invalid active-pack locations; exclude dependency/cache/generated directories from document scans.
- Added regression tests for valid and invalid inventories, obsolete references, missing links, encoded links, repeated heading anchors and dependency exclusion.
- Documented the checker's limits: layout and supported Markdown links do not establish application readiness, manifest schema validity or enforced dependency boundaries.

No source modules, original documents or legacy placeholders were removed. No stack, pilot, dependency or production deployment was selected.

## Multi-phase delivery plan — 2026-11-05

Expanded the existing P00-P11 plan with M0-M6 milestones, explicit fixture/live/pilot decision gates, B01-B07 first-slice batches and P11A-P11F expansion stages. Added accountable roles, module scope, dependencies, verification levels, acceptance evidence and estimation rules. Updated the matching checklist and document index. Synthetic policy/knowledge work can proceed after the fixture gate while live-route decisions remain open; live customer acceptance cannot bypass those decisions. Existing PF/FR mappings and phase IDs remain valid. No application phase is marked complete and no implementation stack or customer target is invented.

## Reference-only implementation plan — 2026-11-05

Recorded the owner's selection of the attached reference-only approach and superseded intervening fork/rebrand proposals. Added a P00–P11 source-study matrix, evidence selection, reference record template, original implementation/test sequence and dependency boundary to the existing plan. Aligned the checklist, provider decision, source mapping and index. Corrected stale base-candidate, extraction, alternate-runtime and imported-skill wording. Research sources are inputs rather than dependencies; no copying, installation or application implementation occurred. Existing commercial evidence is linked as research provenance, not re-audited by this planning edit.
