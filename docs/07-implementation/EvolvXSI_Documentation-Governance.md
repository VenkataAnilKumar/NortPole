# EvolvXSI — documentation governance

Status: local documentation repository established; release approval remains pending · Updated: 2026-11-02

## Repository and ownership

The workspace docs/ directory is an independent Git repository named evolvxsi-docs, on main. It is separate from the 12 source repositories, with no parent monorepo and no configured remote. The initial local commit records the reviewed planning baseline; a commit is not customer acceptance or production approval.

The product owner owns product scope and the PRD; the technical owner owns architecture, API/data contracts and technical decisions; the delivery owner owns phase evidence; the release owner records acceptance of the combined baseline. Named individuals are assigned in P00. Reference research stays in reference documents and cannot silently select a production dependency.

## Change and release procedure

1. Change the authoritative document and update its affected feature, API, data, phase and checklist references together.
2. Record the reason, responsible reviewer, affected requirements and unresolved decisions in the review/change record. Validate local links and schema/requirement mappings.
3. Commit the reviewed change. Use the full immutable Git commit ID as the documentation baseline; a mutable branch name is insufficient.
4. Each deployment release manifest records documentation repository identity, full commit ID, approval-record location/digest, approver and approval time alongside tested service/package versions. P01 implements this manifest contract; P10 verifies it before rollout.
5. A rollback restores the matching service and documentation baseline. Later documentation fixes create new commits and retain the original release record.

No deployment release manifest or approval record is fabricated before implementation and owner acceptance. Local history is established now; remote hosting and CI are configured with repository setup in P01. Keep customer data, credentials and generated temporary artifacts out of this repository.
