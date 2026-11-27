# NortPole — UI plan (tabs, names and order)

Status: Plan, 2026-11-13. Builds on the [UI specification](NortPole_UI-Spec.md). Pack dependency work (horizontal packs building on others) is **not** part of this plan; it waits for the concept decision and a second domain pack.

## Earlier design decisions
- Users see **Everyday** (horizontal packs) and domain names (for example **Finance**); "horizontal" and "vertical" stay author and admin terms.
- "Reviewed tasks" becomes **Tasks**; the inherited conversation list becomes **Chats**; **Packs** becomes **Workflows**.
- **Plugins** (and Skills) are hidden from users unless sandboxed tasks are switched on.
- The admin console is regrouped by tab in a later stage; links move, logic does not.

## Concept words
**Chat**: a quick cited conversation; nothing is approved or sent. **Task**: reviewed work (plan, run, cited draft, checks, approval, optional send). **Workflow**: a ready-made task from a pack. **Pack**: a signed bundle of workflows and rules (Everyday or a domain). **Agent**: a chat assistant. **Library**: sources a person may read.

## Current workspace order

**New → Search → Inbox → Agents → Workflows → Projects → Knowledge → Sources**

**Agent Catalog** sits inside **Agents**. **Projects** opens the project list directly. **Recents** is below the main navigation. See the [current workspace specification](NortPole_UI-Spec.md#user-portal) for the member flows and sub-tabs.

The original admin plan grouped pages under Overview, Governance, People, Models, Packs, Agents & tools, Knowledge, and Platform. The original settings plan covered Profile, Appearance, Models, Notifications, Memory, Accounts, and Prompts, with Privacy and Security as later additions.

## Earlier delivery stages
| Stage | Scope | Size |
| --- | --- | --- |
| U1 | Sidebar order and names; Plugins hidden unless sandboxed tasks are on; page titles follow the new names (done 2026-11-13) | Small |
| U2 | Workflows page grouped Everyday then domains; a pack detail view (workflows, routes and data classes, models passed, autonomy, review rules, version and signer); a reason on every unavailable pack (done 2026-11-13) | Medium |
| U3 | Admin console regrouped into the eight tabs; Governance gathers its pages (done 2026-11-13) | Medium |
| U4 | Admin Overview: failed runs, refusals, packs that lost readiness, audit chain status (done 2026-11-13) | Medium |
| U5 | "Turn into task" from a chat answer; Everyday workflows as the home start cards (built as cards above the composer rather than chips inside it), with built-in fallbacks (done 2026-11-13) | Medium |
| U6 | Quality pass on every changed screen (light and dark, 1280 and 390 wide, axe at 0 violations, keyboard) (done 2026-11-13) | Small, per stage |

Each stage ends with a browser check and a note in [REVIEW.md](../REVIEW.md).
