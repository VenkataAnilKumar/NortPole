# Workflow packs

First-party workflow packs, kept as source. A pack is a signed, versioned bundle of workflow templates, review rules,
guides, agents and evaluation cases that the server installs (admin console, **Packs**).

```text
packs/
├── horizontal/<pack-id>/manifest.yaml            domain-neutral work any team does (vertical: general)
├── vertical/<industry>/<pack-id>/manifest.yaml   industry packs (vertical: <industry>)
├── editions/<industry>.json                      what an industry customer gets: horizontal + that industry's packs
└── _template/                                    copy this to start a pack
```

| Pack | Kind | What it does |
|---|---|---|
| [everyday-brief](horizontal/everyday-brief/README.md) | horizontal | Cited brief, find the policy, compare two documents |
| [finance-policy-review](vertical/finance/finance-policy-review/README.md) | vertical: finance | Receipt rules, approval limits, policy changes |

**Rules** (checked by `services/core/tests/unit/evolvxsi/packs/test_pack_sources.py` and `tools/validate_structure.py`):

- Every manifest validates against the server's own manifest model, so a pack that passes installs.
- The folder name equals the pack `id`; horizontal packs have `vertical: general`; vertical packs sit in their
  industry's folder.
- Pack ids are unique, every pack is listed in `modules.json` (`packs.active`), and editions name only existing packs
  of their own industry or horizontal ones.
- Horizontal packs never depend on vertical ones. Packs never contain customer data or secrets.

To install a pack, build and sign it (pack SDK, decision 0006 phase 4) and upload the signed package in the admin console.
