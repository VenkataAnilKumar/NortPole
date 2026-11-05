# EvolvXSI — packages/integrations

Connector and tool contracts, credential references and remote receipt/reconciliation adapters.

This is a module in the EvolvXSI monorepo. Its implementation is pending. Module ownership and acceptance criteria are recorded in docs/06-technical/EvolvXSI_Repo-Structure.md and docs/06-technical/EvolvXSI_Feature-Architecture-Mapping.md at the repository root.

Use explicit contracts across business boundaries. Each state owner keeps its migrations and tests. Shared packages contain reusable code or definitions and receive no authority from their location. Downloaded source projects serve as references only.

## State ownership

This package owns adapter code and contracts, not a database or independent service. services/execution persists action receipts, deduplication and reconciliation; services/knowledge persists source sync cursors, ingestion health and ACL state. services/control-plane owns tenant integration configuration and grants. Hosting workers use their owning service's persistence boundary.
