# EvolvXSI — services/control-plane

Public API routing and control-plane ownership of tenants, memberships, projects, task drafts, registry, policies and approval decisions.

This is a module in the EvolvXSI monorepo. Its implementation is pending. Module ownership and acceptance criteria are recorded in docs/06-technical/EvolvXSI_Repo-Structure.md and docs/06-technical/EvolvXSI_Feature-Architecture-Mapping.md at the repository root.

Use explicit contracts across business boundaries. Each state owner keeps its migrations and tests. Shared packages contain reusable code or definitions and receive no authority from their location. Downloaded source projects serve as references only.
