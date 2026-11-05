# Horizontal and vertical packs

`_template/` is an authoring template, not an installed pack. Future domain-neutral bundles belong in `horizontal/<name>/`; selected domain bundles belong in `vertical/<name>/`. These namespaces have no active packs yet.

Both use the same versioned contract and a schema-valid `manifest.yaml` once that schema is defined. Horizontal packs reuse platform agents and skills; vertical packs compose those capabilities with domain rules and evaluation cases. Pack permissions are requests subject to tenant grants. Customer data remains in authorized services.

Register an active pack and its owner in modules.json only when selected and implemented. See the [repository structure](../docs/06-technical/EvolvXSI_Repo-Structure.md).
