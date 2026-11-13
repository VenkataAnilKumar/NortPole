# EvolvXSI — Pack signing and key rotation runbook

Status: Current (checked in a sandbox against the real database; no production key ceremony has been run).

A vertical pack is installed only if its signature verifies against a signer an administrator has trusted. This runbook covers creating a signer, signing a pack, and rotating the key.

## 1. Create a signer key

Run where the private key will live (an authoring machine, not the server):

```bash
python services/core/scripts/sign_pack.py keygen acme-2026 > acme-2026.key.json
```

The output holds `key_id`, `public_key` and `private_key`. Keep the private key out of the repository and out of chat. Only the public key goes to the server.

## 2. Trust the signer

In the admin console, open **Packs**, enter the key id and the public key, and choose **Trust this signer**. A signer is not a person's permission: it only lets packs signed by that key be installed.

## 3. Sign and install a pack

```bash
python services/core/scripts/sign_pack.py sign pack.json <private-key> acme-2026 > pack.pkg.json
```

Paste the package into **Install**. A tampered package, an unknown signer, an invalid manifest, or a version that already exists is refused with the reason. An installed version is inactive until an administrator activates it. If the pack lists evaluation cases, **Evaluate on current model** must pass before the pack runs.

Before activating, read what the pack will put in front of the model: each template's house style, its review rules, and its **guides** (open "Guides in this version" on the Packs page; every guide is shown in full, with the workflows that use it). A guide is text the signer wrote; it shapes how plans and drafts are written and cannot add a source, run anything or change the citation rules, but it is instruction text all the same, so treat it like any other content you approve.

## 4. Rotate a key

Rotation has to keep packs available, because revoking a signer stops every version it signed, everywhere, at once.

1. Create a new key (step 1) and trust it (step 2).
2. Re-sign each pack you still use with the new key, **bumping the version** (the same version cannot be installed twice), and install it.
3. Activate the new versions and, for packs with evaluation cases, run **Evaluate on current model**.
4. Only when the new versions are active, revoke the old signer. Versions it signed stop being offered, and a task from one of them cannot be started or run (a task still in draft or review is blocked at the next step); drafts already finished keep their recorded pack version.

If a key is lost or exposed, skip waiting: revoke it first. People lose the packs until step 2 and 3 are done, which is the intended safe side.

## Limits
- There is no automatic expiry of signers and no hardware-key support.
- Revocation cannot be undone from the console; trust a new key instead.
