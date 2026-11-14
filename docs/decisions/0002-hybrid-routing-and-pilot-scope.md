# Decision 0002: user-selectable hybrid routing and pilot scope

Date: 2026-11-10. Status: **proposed**, recorded from the product owner's stated direction in this chat; pending owner confirmation of the open items below.

## Direction

NortPole is a North-like whole product with hybrid intelligence: a user can choose a local, private or cloud model route, and vertical packs run on top. This extends the existing statement in the [product definition](../02-product/NortPole_Product-Definition.md) that users choose among local, private and cloud routes within the same policy.

## Decision

1. **User choice is a preference inside administrator policy.** The route picker offers Auto, Local, Private and Cloud. A route that policy blocks for the task's data class stays visible but disabled, with the reason. A blocked route fails before any content is sent. Fallback never leaves the allowed set. User choice never overrides policy.
2. **Evaluation is per route.** Publication evidence stays bound to the exact candidate and dependencies, and now includes the route. A pack that passes on one route is offered only on routes where it has passed. A pack manifest declares its model requirements.
3. **Packs get user and admin surfaces.** Apps & Packs for users; Skills & Packs for administrators covering install, version, route compatibility and tenant activation. Installation and access grants stay separate.
4. **Pilot scope.** The smallest demonstration of the differentiator is one vertical pack with two routes, one local and one cloud. This pulls a slice of P08 (hybrid routing, PF-07.03) forward and does not change the first-release PRD: FR-08 still requires destination policy enforcement before transmission. The full North-like product remains P11.

## Open items for the owner

- Where local models run: on the user's device or on customer-hosted servers. This changes the Admin Console and the security model.
- Whether users choose a route per task or only per workspace.
- The first vertical and the specific models and providers (P00 decisions).
- Whether the P08 slice moves ahead of P06 or follows it.

## Consequences

Applied 2026-11-10: PF-07.03 and PF-02.02 acceptance now cover per-route evaluation and manifest model requirements (Feature-Spec); the route picker and tab changes are in the UI specification; route evaluation results are in the data model; and `GET/PUT /v1/me/preferences` is in the API draft. Still open: the pack manifest schema itself, which is defined when contracts are implemented in P05.

This record selects no provider or stack, approves no vertical, adds no dependencies and claims no implementation.
