# EvolvXSI pack SDK

Validate, build and sign workflow packs from source. It does not need the server: it validates against
[the generated manifest schema](../contracts/README.md) and the `packs/` folder rules, and signs the same canonical bytes
the server verifies, so a pack that passes here installs (the server still runs its full checks).

```bash
pip install pyyaml jsonschema cryptography          # or: pip install ./packages/pack-sdk
cd packages/pack-sdk
python -m evolvxsi_pack_sdk validate ../../packs/horizontal/everyday-brief ../../packs/vertical/finance/finance-policy-review
python -m evolvxsi_pack_sdk keygen my-signer > ~/my-signer.json      # keep this file out of the repository
python -m evolvxsi_pack_sdk sign ../../packs/vertical/finance/finance-policy-review --key-file ~/my-signer.json --out dist
```

Register the key's **public** key as a trusted signer in the admin console (**Packs**), then install the
`dist/<id>-<version>.signed.json` package there. `make packs` validates every pack in the repository.

Tests: `python -m pytest packages/pack-sdk/tests` (standalone), and in `services/core`
`tests/unit/evolvxsi/packs/test_pack_sdk_matches_server.py` (same digest, a signature the server verifies, the same
verdict on broken manifests) and `tests/evolvxsi_integration/test_pack_sdk_install.py` (an SDK-signed pack installs).
