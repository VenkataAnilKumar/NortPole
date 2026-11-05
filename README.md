# EvolvXSI

Enterprise agentic AI workspace with a shared horizontal platform and versioned vertical packs.

This monorepo contains the product documents and module skeletons. The product is at the design stage. The first customer workflow, technology choices and deployment acceptance targets remain open.

- [Product definition](docs/02-product/EvolvXSI_Product-Definition.md)
- [System architecture](docs/06-technical/EvolvXSI_System-Architecture.md)
- [Repository structure](docs/06-technical/EvolvXSI_Repo-Structure.md)
- [Module inventory](modules.json)
- [Document index](docs/README.md)

Downloaded source references are maintained outside this product tree. Their provenance and design mappings are recorded in the reference documents. EvolvXSI owns its product code, contracts and runtime decisions.

## Repository validation

Run `python tools/validate_structure.py` to check layout and document links. The inventory separates existing skeletons from future modules. See the [accepted structure decision](docs/decisions/0001-modular-monorepo.md). Application implementation remains pending.
