# Pack template

Copy this folder to start a pack:

- `packs/horizontal/<pack-id>/` for a domain-neutral pack (`vertical: general`), or
- `packs/vertical/<industry>/<pack-id>/` for an industry pack (`vertical: <industry>`).

The folder name must equal the manifest's `id`. Add the new folder to `packs.active` in `modules.json` and, if it belongs
to an edition, to `packs/editions/<industry>.json`. The pack tests in `services/core` validate every manifest against the
server's own model, so a pack that passes them installs.
