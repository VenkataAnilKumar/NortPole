# Decision 0004: adopt community source as the pilot core

Date: 2026-11-10. Status: **proposed**, recorded from the product owner's direction to copy and rebrand the upstream open-source core and not use its deployment files. It amends the reference-only direction in [decision 0001](0001-modular-monorepo.md) and the [provider SDK decision](../07-implementation/EvolvXSI_Provider-SDK-Decision.md), and it records a layout exception.

## Decision

1. **Adopt, don't fork.** A shallow copy of the upstream open-source core (MIT outside its `ee` directories), commit `919578e`, is adapted in this repository: the backend in `services/core` and the web app in `apps/workspace`. No `ee` code was copied. The MIT notice is kept in each folder's `NOTICE`; provenance and gaps are in `services/core/UPSTREAM.md`.
2. **Temporary combined service.** `services/core` combines retrieval, chat, agents, connectors and model routing. It stands in for the control-plane, execution, knowledge and model-gateway owners during the pilot. Carve those owners out as the code allows; new NortPole modules (policy, approvals, packs, evaluation) are added as separate modules and call into `services/core` through adapters, so upstream merges stay possible.
3. **Rebrand by script.** A one-time rebrand script (removed; in git history at 7cabc08) renamed the upstream product name to NortPole in every letter case, protecting license text, the upstream repository slug and external upstream domains. Recover and re-run it on a fresh copy when taking a newer upstream commit.
4. **No deployment files.** Upstream Docker, Helm, Terraform and CI files were not copied. Run and deployment scripts are written for NortPole under `infrastructure`.
5. **Telemetry off.** Upstream telemetry to an upstream domain is disabled by default in this copy.

## Known gaps

- Per-user external permission sync and the search results view and API are upstream `ee` features. NortPole must build its own for the pilot source; the web app currently stubs them (`src/lib/community`, `src/sections/SearchUI.tsx`).
- Lock files still name the upstream project; regenerate them. Nothing has been installed, built or run: only a Python compile check passed.
- A lawyer should check trademark and notice obligations before release.
- Logos and other brand assets are still upstream's.

## Consequences

Update [`modules.json`](../../modules.json) (done: `services/core`, maturity skeleton) and the repository structure doc when the carve-out starts. This record selects no provider or vertical and claims no working product.
