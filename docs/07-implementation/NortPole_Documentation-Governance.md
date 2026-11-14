# NortPole — documentation governance

Status: documentation tracked in the product monorepo; release approval remains pending · Updated: 2026-11-05

## Repository and ownership

The NortPole monorepo tracks docs/ alongside the product modules. Pin release documentation to the exact product Git commit.

The product owner owns product scope and the PRD; the technical owner owns architecture, API/data contracts and technical decisions; the delivery owner owns phase evidence; the release owner records acceptance of the combined baseline. Named individuals are assigned in P00. Reference research stays in reference documents and cannot silently select a production dependency.

## Change and release procedure

1. Change the authoritative document and update its affected feature, API, data, phase and checklist references together.
2. Record the reason, responsible reviewer, affected requirements and unresolved decisions in the review/change record. Validate local links and schema/requirement mappings.
3. Commit the reviewed change. Use the full immutable Git commit ID as the documentation baseline; a mutable branch name is insufficient.
4. Each deployment release manifest records product repository identity, full commit ID, approval-record location/digest, approver and approval time alongside tested service/package versions. P01 implements this manifest contract; P10 verifies it before rollout.
5. A rollback restores the matching service and documentation baseline. Later documentation fixes create new commits and retain the original release record.

No deployment release manifest or approval record is fabricated before implementation and owner acceptance. The product has an existing Git history and origin. P01 must verify repository access and implement CI; these are separate from documentation approval. Keep customer data, credentials and generated temporary artifacts out of this repository.

## Architecture traceability

Use the [canonical engineering map](../06-technical/NortPole_System-Architecture.md#ten-engineering-layers). For a layer change, review product coverage, portal behavior, module ownership and delivery acceptance together.
