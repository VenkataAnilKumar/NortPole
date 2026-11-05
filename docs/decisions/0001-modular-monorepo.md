# Decision 0001: modular monorepo

Date: 2026-11-05. Status: structural proposal accepted by the product owner in this chat; implementation choices remain pending.

Keep one product repository with independently deployable backend owners, shared packages, unified workspace features and versioned horizontal/vertical packs. Move the existing API skeleton to services/control-plane. Preserve all existing work and numbered product documents.

The motivation is independent workload scaling and clear state ownership while retaining atomic contract changes. Separate repositories would add coordination before there are working services; a single undifferentiated application would hide future deployment boundaries.

Consequences: enforce dependency direction and service-owned records; validate affected consumers; pin compatible releases. Add future portals and packages when they have implementation scope. Layer count does not prescribe process count. Tool isolation and tenant controls require runtime enforcement.

This decision approves layout only. It does not select a stack, approve a pilot vertical, add dependencies, authorize deployment, or make reference projects runtime dependencies.

The [repository specification](../06-technical/EvolvXSI_Repo-Structure.md) records the detailed layout and migration.
