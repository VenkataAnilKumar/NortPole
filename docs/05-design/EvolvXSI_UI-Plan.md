# EvolvXSI — UI plan (tabs, names and order)

Status: Plan, 2026-11-13. Builds on the [UI specification](EvolvXSI_UI-Spec.md). Pack dependency work (horizontal packs building on others) is **not** part of this plan; it waits for the concept decision and a second domain pack.

## Decisions taken (owner may change any of them)
- Users see **Everyday** (horizontal packs) and domain names (for example **Finance**); "horizontal" and "vertical" stay author and admin terms.
- "Reviewed tasks" becomes **Tasks**; the inherited conversation list becomes **Chats**; **Packs** becomes **Workflows**.
- **Plugins** (and Skills) are hidden from users unless sandboxed tasks are switched on.
- The admin console is regrouped by tab in a later stage; links move, logic does not.

## Concept words
**Chat**: a quick cited conversation; nothing is approved or sent. **Task**: reviewed work (plan, run, cited draft, checks, approval, optional send). **Workflow**: a ready-made task from a pack. **Pack**: a signed bundle of workflows and rules (Everyday or a domain). **Agent**: a chat assistant. **Library**: sources a person may read.

## Target order
User sidebar: New · Search · Tasks · Inbox · Workflows · Libraries · Automations, then the Agents, Projects and Chats lists; Settings and the admin console at the bottom.
Admin console: Overview · Governance · People · Models · Packs · Agents & tools · Knowledge · Platform.
Settings: Profile · Appearance · Models · Notifications · Memory · Accounts · Prompts · Privacy (later) · Security (later).

## Stages
| Stage | Scope | Size |
| --- | --- | --- |
| U1 | Sidebar order and names; Plugins hidden unless sandboxed tasks are on; page titles follow the new names (done 2026-11-13) | Small |
| U2 | Workflows page grouped Everyday then domains; a pack detail view (workflows, routes and data classes, models passed, autonomy, review rules, version and signer); a reason on every unavailable pack (done 2026-11-13) | Medium |
| U3 | Admin console regrouped into the eight tabs; Governance gathers its pages (done 2026-11-13) | Medium |
| U4 | Admin Overview: failed runs, refusals, packs that lost readiness, audit chain status (done 2026-11-13) | Medium |
| U5 | "Turn into task" from a chat answer; Everyday workflows as the home start cards (built as cards above the composer rather than chips inside it), with built-in fallbacks (done 2026-11-13) | Medium |
| U6 | Quality pass on every changed screen (light and dark, 1280 and 390 wide, axe at 0 violations, keyboard) | Small, per stage |

Each stage ends with a browser check and a note in [REVIEW.md](../REVIEW.md).
