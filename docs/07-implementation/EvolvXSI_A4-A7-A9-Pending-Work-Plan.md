# EvolvXSI — plan for the pending work in A4, A7 and A9

Status: Plan, written 2026-11-12, before any of this is built. It rests on what is built and checked today (see [REVIEW.md](../REVIEW.md) and the [delivery plan](EvolvXSI_Adopted-Core-Delivery-Plan.md)); all of that was checked in a sandbox only.

## Rules for every item
- Each item ends with tests, a check in the running product, a note in REVIEW.md that says what was and was not checked, then commit, push, pull request and merge.
- Declarative before executable: where a pack, plugin or rule could carry code, build the declarative form first and leave code to Craft-style sandboxes, which are not available.
- Nothing here needs a customer or a cloud model unless marked **needs you**.

## Order and why

| # | Phase | Item | Size | Why this position |
|---|---|---|---|---|
| 1 | A9 | Sensitive-data redaction before model calls, traces and exports | M | The main trust claim of a governed product; no dependencies. |
| 2 | A9 | Autonomy tiers per destination and pack | S | Small, builds on the action layer; gives A7 a control to inherit. |
| 3 | A9 | Retention, audit pruning, legal hold, audit export | M | Needed for any pilot's records policy; periods are placeholders until **you** set them. |
| 4 | A7 | Agent and tool inventory (admin, read-only) | S | Gives A7 and A9 one place to see what is active. |
| 5 | A7 | Extension levels and MCP/plugin allowlists, signed plugin packages | L | Reuses the pack signing built already. |
| 6 | A7 | Pack review rules (declarative checks on drafts) | M | The safe stand-in for pack-supplied agents. |
| 7 | A4 | Interface quality pass: dark and narrow widths, keyboard, contrast, axe checks | M | Better done once the new pages from 1 to 6 exist. |
| 8 | A9 | Prompt-injection suite against the real local model | M | Needs the stable drafting path; reports a measured rate. |
| 9 | A9 | Threat model, dependency and license scan, upstream-link cleanup | M | Closes the A9 review work. |
| 10 | A4 | Settings and admin tab audit against the UI spec | S | Settings already has General, Chat preferences, Accounts, Connectors, Models, Notifications, Usage and a Memory component; this checks each works and fills gaps. |

## Items in detail

**1. Redaction (A9).** Patterns for email addresses, phone numbers, card numbers (Luhn-checked), national-ID-like numbers, API keys and bearer tokens. A per-route-kind setting (default: redact for cloud routes, off for local) replaces matches with typed placeholders before the prompt is sent, and before text is stored in audit details or exports. A fixed, labelled synthetic set reports precision and recall. *Exit:* the report, tests that the original text never reaches the model client or the audit table, and a plain statement that only the listed patterns are caught (names and free-text secrets are not).

**2. Autonomy tiers (A9).** Each destination and pack carries a tier: draft only, or act with approval (today's behaviour); read-only blocks proposing. Enforced in the API, not the screen. *Exit:* a draft-only destination refuses a proposal and the refusal is audited.

**3. Retention and export (A9).** A scheduled prune of audit events and old route-usage rows after a configurable period, a legal-hold switch that stops pruning, and an audit export (JSON and CSV, admin only, itself audited). *Needs you:* the real periods and who may place a hold.

**4. Inventory (A7).** One admin page listing active packs (version, signer), skills, plugins, MCP servers, send destinations and their tiers, with the last use where it is recorded.

**5. Extension levels, allowlists, signed plugins (A7).** An admin setting per extension type (connectors, skills, plugins, MCP servers): Off, Request or Self-serve; personal items stay private to their owner; plugins and MCP servers are request-only. An allowlist of MCP servers (and optionally tools). Plugin packages are accepted only if signed by a trusted signer, using the pack signing already built. Calls are written to the audit log. *Exit:* an unsigned or tampered plugin is refused; a blocked server cannot be called.

**6. Pack review rules (A7).** A pack template can list declarative rules on its drafts (for example "must cite at least two sources", "must not contain these phrases"), checked before the draft can be approved. No code runs. Pack-supplied agents or tools that run code stay out of scope until a sandbox exists.

**7. Interface quality pass (A4).** Light, dark and 390-pixel screenshots of every EvolvXSI page, a keyboard-only path, contrast and axe accessibility checks, with findings fixed.

**8. Injection suite (A9).** A fixed set of hostile source passages run through the real drafter on the local model; the report states how many produced an injected citation, an obeyed instruction or a leaked prompt. Small models fail such tests, so the number may be poor; it is recorded as measured.

**9. Review work (A9).** A written threat model, a dependency and license scan (if the sandbox can reach the advisory sources), and replacement of upstream documentation links.

**10. Tab audit (A4).** Compare Settings and admin tabs with the UI spec and fix gaps.

## Not in this plan (needs you or is deferred)
- SSO, service identities, secrets store, customer-managed keys: need your identity provider and hosting target.
- Trademark review of the name.
- Translations of the new pages: deferred until a customer's language is known.
- Composer chips, My Files, Apps page: judged covered by Libraries and Plugins; reopen if you disagree.
- Craft (sandboxed tasks) and pack-supplied code agents.
