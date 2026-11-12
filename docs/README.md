# EvolvXSI — document list

Updated: 2026-11-05 · Status: working product definition

The document names and numbered areas follow the convention used by the Qvora document set. Every listed file now exists. **Draft** means the content is written for review; it does not mean the product decision or implementation is complete.

| Area | Document | Status | Purpose |
| --- | --- | --- | --- |
| 01 Brand | [EvolvXSI_Brand-Identity.md](01-brand/EvolvXSI_Brand-Identity.md) | Draft | Confirmed product name; proposed positioning, voice, and visual direction. |
| 02 Product | [EvolvXSI_Product-Overview.md](02-product/EvolvXSI_Product-Overview.md) | Draft | Product thesis, users, value, and boundaries. |
| 02 Product | [EvolvXSI_Product-Definition.md](02-product/EvolvXSI_Product-Definition.md) | Draft | Working customer, use case, offer, and product scope. |
| 03 Market | [EvolvXSI_Market-Assessment.md](03-market/EvolvXSI_Market-Assessment.md) | Draft | Target segment criteria, alternatives, buying process, and demand evidence plan. |
| 03 Market | [EvolvXSI_Competitive-Analysis.md](03-market/EvolvXSI_Competitive-Analysis.md) | Draft | Initial landscape and pilot comparison rubric. |
| 04 Specs | [EvolvXSI_First-Workflow-PRD.md](04-specs/EvolvXSI_First-Workflow-PRD.md) | Draft | First workflow, requirements, acceptance criteria, and release gates. |
| 04 Specs | [EvolvXSI_User-Journey.md](04-specs/EvolvXSI_User-Journey.md) | Draft | Candidate practitioner and administrator journeys. |
| 04 Specs | [EvolvXSI_User-Stories.md](04-specs/EvolvXSI_User-Stories.md) | Draft | First-workflow stories and phased platform capability epics. |
| 04 Specs | [EvolvXSI_Feature-Spec.md](04-specs/EvolvXSI_Feature-Spec.md) | Draft | Ten-layer platform feature catalog and detailed first-workflow behavior. |
| 04 Specs | [EvolvXSI_North-Feature-Mapping.md](04-specs/EvolvXSI_North-Feature-Mapping.md) | Draft | Cohere North capabilities mapped to the PF catalog, with gaps and suggested sequence; secondary sources only. |
| 05 Design | [EvolvXSI_UI-Spec.md](05-design/EvolvXSI_UI-Spec.md) | Draft | Screens, states, interactions, and accessibility details. |
| 05 Design | [EvolvXSI_Design-System.md](05-design/EvolvXSI_Design-System.md) | Draft | Interaction rules and visual token categories; final brand pending. |
| 06 Technical | [EvolvXSI_System-Architecture.md](06-technical/EvolvXSI_System-Architecture.md) | Draft | Capability boundaries, contracts, execution flow, and risks. |
| 06 Technical | [EvolvXSI_Tech-Stack.md](06-technical/EvolvXSI_Tech-Stack.md) | Current | Frameworks, services and versions in use, EvolvXSI-owned parts, and choices still open. |
| 06 Technical | [EvolvXSI_Deployment-Architecture.md](06-technical/EvolvXSI_Deployment-Architecture.md) | Draft | Deployable services, persistence, queues, network boundaries and scaling. |
| 06 Technical | [EvolvXSI_Repo-Structure.md](06-technical/EvolvXSI_Repo-Structure.md) | Draft | Monorepo layout, module ownership and release rules. |
| 06 Technical | [EvolvXSI_Feature-Architecture-Mapping.md](06-technical/EvolvXSI_Feature-Architecture-Mapping.md) | Draft | Complete PF module/phase mapping and first-workflow PRD traceability. |
| 06 Technical | [EvolvXSI_API-Design.md](06-technical/EvolvXSI_API-Design.md) | Draft | Proposed public and internal API contracts. |
| 06 Technical | [EvolvXSI_Data-Model.md](06-technical/EvolvXSI_Data-Model.md) | Draft | Conceptual task, run, evidence, approval, and tenant records. |
| 07 Implementation | [EvolvXSI_Open-Decisions.md](07-implementation/EvolvXSI_Open-Decisions.md) | For decision | Nine open decisions with a recommendation for each, and what each unblocks. |
| 07 Implementation | [EvolvXSI_Implementation-Phases.md](07-implementation/EvolvXSI_Implementation-Phases.md) | Draft | P00-P11 delivery plan, M0-M6 milestones, first-slice batches, P11A-P11F expansion, dependencies and acceptance evidence. |
| 07 Implementation | [EvolvXSI_Adopted-Core-Delivery-Plan.md](07-implementation/EvolvXSI_Adopted-Core-Delivery-Plan.md) | Proposed | Phases A0-A12 on the adopted core: what is done, what remains, exit evidence, dependencies and decisions. |
| 07 Implementation | [EvolvXSI_Implementation-Checklist.md](07-implementation/EvolvXSI_Implementation-Checklist.md) | Draft | Phase-aligned execution tasks and release evidence checklist. |
| 07 Implementation | [EvolvXSI_Documentation-Governance.md](07-implementation/EvolvXSI_Documentation-Governance.md) | Planning baseline | Documentation ownership, version control and release commit pinning. |
| 07 Implementation | [EvolvXSI_Provider-SDK-Decision.md](07-implementation/EvolvXSI_Provider-SDK-Decision.md) | Owner direction | Official provider SDKs with EvolvXSI-owned logic; downloaded platforms remain references. |
| 07 Implementation | [EvolvXSI_Source-Repository-Mapping.md](07-implementation/EvolvXSI_Source-Repository-Mapping.md) | Draft | Local source evidence, reuse candidates, gaps and source identity correction. |
| 07 Implementation | [EvolvXSI_Open-Source-References.md](07-implementation/EvolvXSI_Open-Source-References.md) | Draft | External project shortlist, eight-platform review, and due diligence; kept outside the product definition. |
| 07 Implementation | [Commercial reference research](07-implementation/EvolvXSI_Commercial_Reference_Research.md) | Reference | Commercial evidence, module mappings and license boundaries. |
| 07 Implementation | [EvolvXSI_Pack-Signing-Runbook.md](07-implementation/EvolvXSI_Pack-Signing-Runbook.md) | Current | Create, trust and rotate pack signing keys; what revoking does. |
| 07 Implementation | [EvolvXSI_A4-A7-A9-Pending-Work-Plan.md](07-implementation/EvolvXSI_A4-A7-A9-Pending-Work-Plan.md) | Plan | Order, scope and exit evidence for the pending work in A4, A7 and A9. |

## Source context

The [document review](REVIEW.md) records consistency fixes, requirement traceability, and decisions still needed before implementation. The product definition owns scope; the PRD owns first-release acceptance; the feature, UI, API, and data documents elaborate those requirements. Reference research does not select a dependency or alter scope.

The owner's earlier chats establish two related ideas: a horizontal super intelligent agent platform and a vertical super intelligent agent platform. These are planning inputs. This workspace has no application implementation or customer validation. External project research and chat provenance are kept in [EvolvXSI_Open-Source-References.md](07-implementation/EvolvXSI_Open-Source-References.md).

## Working decisions

1. Build one reusable horizontal platform that supports separately packaged vertical solutions.
2. Prove one complete, governed vertical workflow before expanding the platform catalog.
3. Choose a single implementation owner for each platform capability.
4. Treat model choice, data handling, approvals, evaluation, and auditability as product requirements from the start.

## Decisions still needed

- Select the first customer segment and vertical workflow through discovery interviews.
- Finalize visual identity for the confirmed product name, EvolvXSI.
- Validate the proposed technical foundation with a spike.
- Decide initial deployment model, buyer, pricing metric, and launch geography.

## Documentation version control

The EvolvXSI monorepo versions canonical documentation alongside product modules. See [documentation governance](07-implementation/EvolvXSI_Documentation-Governance.md) for ownership, review and release-baseline rules. The initial local commit records planning changes; it does not approve an implementation or release.

## Learning environments

[Learning environments and controlled improvement](06-technical/EvolvXSI_Learning-Environments.md) records the proposed architecture, ownership and delivery gates. The [external reference document](07-implementation/EvolvXSI_Open-Source-References.md) contains the supporting research review.

## Architecture entry points

Start with the [ten engineering layers](06-technical/EvolvXSI_System-Architecture.md#ten-engineering-layers), [product coverage map](02-product/EvolvXSI_Product-Definition.md#product-coverage-and-engineering-ownership), [portal inventory](05-design/EvolvXSI_UI-Spec.md#portal-and-surface-inventory-l01), and [delivery coverage](07-implementation/EvolvXSI_Implementation-Phases.md#delivery-coverage-by-engineering-layer).

## Platform feature index

The [feature catalog](04-specs/EvolvXSI_Feature-Spec.md#full-platform-feature-catalog) covers all ten engineering layers. The first-workflow PRD retains pilot requirements. The user stories, UI specification and implementation phases link the catalog to delivery.

## Reference-only delivery plan

The [reference-only implementation workstream](07-implementation/EvolvXSI_Implementation-Phases.md#reference-only-implementation-workstream) maps local and web studies to P00–P11, defines provenance/commercial-evidence gates and records the per-phase design/test workflow. The selected direction is EvolvXSI-owned implementation; application-platform copying and rebranding are not selected. Use the aligned [implementation checklist](07-implementation/EvolvXSI_Implementation-Checklist.md#reference-only-workstream-gates).

## Decisions

[0001 modular monorepo](decisions/0001-modular-monorepo.md) · [0002 hybrid routing and pilot scope](decisions/0002-hybrid-routing-and-pilot-scope.md) (proposed) · [0003 extension levels and terminology](decisions/0003-extension-levels-and-terminology.md) (proposed) · [0004 adopt community source as pilot core](decisions/0004-adopt-community-source-as-pilot-core.md) (proposed).
