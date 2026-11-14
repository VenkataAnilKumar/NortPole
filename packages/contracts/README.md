# EvolvXSI contracts

Generated from the code by `services/core/scripts/generate_contracts.py`; do not edit by hand. A unit test
(`services/core/tests/unit/evolvxsi/test_contracts_current.py`) fails when a file is out of date.

| File | What it describes |
|---|---|
| `schemas/pack-manifest.schema.json` | The workflow pack manifest the server accepts (JSON Schema 2020-12). The server also runs cross-field checks the schema cannot express, such as unique template ids and guides that exist. |
| `openapi/evolvxsi-api.json` | The HTTP routes implemented by EvolvXSI's own modules (OpenAPI 3.1), with unique operation ids so typed clients can be generated. Inherited platform routes are not included. |

Regenerate after changing a manifest model or an EvolvXSI route:

```bash
cd services/core && PYTHONPATH=. python scripts/generate_contracts.py
```

Typed clients (TypeScript for the web app, an SDK for customers) are generated from `openapi/evolvxsi-api.json` when
they are adopted; see `modules.json` (`packages/sdk`).
