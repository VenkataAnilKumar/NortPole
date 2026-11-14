# EvolvXSI — UI and admin console redesign

Agreed with the owner on 2026-11-13. This plan follows UI plan U1–U6 (`EvolvXSI_UI-Plan.md`) and replaces its navigation. Every stage ends with the quality pass: light and dark, 1280 and 390 pixels wide, axe WCAG 2.1 A/AA, keyboard.

## The rule behind the split

The user side is for using things and asking for them. The admin console is for owning them. Each user tab has a matching admin section, and every request lands in one admin **Approvals** queue. Nothing changes unless an administrator approves it.

## User side

| # | Tab | Features | Status |
|---|---|---|---|
| 1 | **New** | Chat box and assistant picker, attachments, choose which knowledge to use, a badge for where the message goes (local, private, cloud), and "Make it a draft". | Exists; knowledge picker new |
| 2 | **Inbox** | Filters **To approve** (the person's plans to accept, approvals asked of them, scheduled plans from R6, and for administrators one line pointing to admin Approvals), **To review** (drafts ready), **Updates** (runs, decisions on their Discover requests, announcements; dismissed items on request). The sidebar count includes the person's own plans and drafts. A newer scheduled plan replaces the older one (R6). | **R5 done** |
| 3 | **Search** | One search over company knowledge and the person's uploads, filtered by domain, source and date. Each result shows its source and who can see it. | Exists; domain filter R7 |
| 4 | **Agent** | Chat assistants only, each card showing what it reads and which tools it may use. Workflow agents live in Workflows. | Exists (sidebar Agents section); cleanup R3 |
| 5 | **Workflows** | Tabs **Start** (packs; a "Run by" card shows the agent's plan), **Scheduled** (each run stops at the plan and waits in Inbox; a schedule pauses after 3 plans in a row go unaccepted), **My drafts**. | **R1 done** (tabs, addresses); scheduler R6 |
| 6 | **Knowledge** | **Company knowledge** by domain (read-only; source and freshness) and **Uploaded data** by domain (projects become optional folders), with "Request to add to company knowledge". | **R1 done** (renamed, company knowledge); domains and uploads R7 |
| 7 | **Sources** | Tabs in this order (owner's decision): **Discover** (what is not on yet: supported connector types, uploaded but inactive packs, tools not allowed, each with a Request button and its status), **Connectors** (systems connected now), **Skills** (what installed packs know: guides, review rules, house style, workflow agents), **Plugins** (tools assistants may use and whether each is allowed). People request; only an administrator turns anything on. | Done (R1, R3, R4) |
| 8 | **Recent** | Chats, drafts and workflows opened recently. Pin, rename, delete. | Exists |
| 9 | **Settings** | Profile, theme, language, memory, personal tools, notifications; Admin link for administrators. | Exists |

The group keeps the owner's name **Sources**, although Skills and Plugins are not strictly sources. Connectors (knowledge coming in) and Plugins (tools an assistant calls during a chat) stay separate tabs rather than one "Integrations" tab: they answer different questions, carry different risks, and drafts use connectors but never plugins. "Libraries" is not used: that is Knowledge.

## Admin console

| # | Section | Features |
|---|---|---|
| 1 | **Overview** | Health, usage and cost, approvals waiting, audit chain status, sync problems. |
| 2 | **Approvals** | One queue: second-approver sends, two-administrator changes, knowledge, connector, tool and assistant requests, outside-tool definitions. |
| 3 | **Knowledge** | Domains, connectors (setup, sync, permission sync), company knowledge, upload requests, index status. |
| 4 | **Agents & tools** | Chat assistants, workflow agents, packs and signers, Studio, tool catalog, outside tools with pinned definitions, **Channels** (Slack now; where people ask the assistant from another app). Send destinations stay under Governance. |
| 5 | **Governance** | Route policy and redaction, retention and legal hold, audit log, saved head and export, two-administrator rules. |
| 6 | **People** | Users, groups, roles, invitations. |
| 7 | **Models** | Providers, default task model, prices, tokens and cost. |
| 8 | **Quality** | Evaluations per model, drafts accepted or rejected, review-rule hits, scheduled-run cost. |
| 9 | **Platform** | Workspace name and brand, API keys, version, release manifest, SBOM, backup status. |

Hidden for the pilot (R2): Discord bot, SCIM, Hooks, Billing and the "Upgrade plan" entry. They are left out of the sidebar only; their addresses still work. Moving tokens and cost from Route policy to Models is left for a later stage.

## Addresses

| Old | New |
|---|---|
| `/app/packs` | `/app/workflows` |
| `/app/automations` | `/app/workflows/scheduled` |
| `/app/reviewed-tasks` | `/app/workflows/drafts` (the `?task=` query is kept) |
| `/app/libraries` | `/app/knowledge` |
| `/app/sources` | `/app/sources/discover` |

The old addresses redirect (HTTP 307, set in `next.config.js`) because home cards, bookmarks and audit records use them. `/app/plugins` (a person's own plugins, and its OAuth callback) is unchanged and shows under Sources.

## Stages

| Stage | Work | Size | State |
|---|---|---|---|
| R1 | Sidebar order and names, Workflows and Sources tabs, Knowledge rename, redirects, read-only Skills, Connectors and Plugins | Small | Done |
| R2 | Admin console regroup, merged Approvals queue, hide inherited screens | Small to medium | Done |
| R3 | "Run by" line on Start, Agent tab for chat assistants, Channels rename, Sources order | Medium | Done |
| R4 | **Discover** (first tab of Sources) with requests for connectors, skills and plugins, landing in Approvals | Medium | Done |
| R5 | Inbox filters | Small | Done |
| R6 | Scheduled workflows (design: `EvolvXSI_Workflows-and-Knowledge-Design.md` §3): R6a runner and rules, R6b screens and sharing, R6c event triggers later | Medium | R6a and R6b done; R6c later |
| R7 | Knowledge (design §4): R7a domains, R7b My files and requests, R7c verification and freshness | Large | After the search index and the Google Drive connector |
| R8 | Quality pass of each stage | Small per stage | Ongoing |

New page text is in English first; sidebar labels are translated into all nine languages in the same stage.

## Discover and requests (R4)

- **What is offered:** a reviewed list of 17 common connector types not yet set up; packs an administrator uploaded with no active version; tools that exist but are not allowed (personal tools are never offered). Nothing unknown or outside the workspace is listed.
- **A request** records the kind, the item and an optional reason (up to 500 characters). One waiting request per person per item, and at most 20 waiting per person. A person can withdraw their own waiting request.
- **Deciding** happens in admin Approvals, with an optional note the person sees. **Approving turns nothing on**: it records the decision, and the administrator sets the item up on Connectors, Packs or Tools (each request links there).
- **Audit:** `source.request` (asked, withdrawn) and `source.request_decide`, with the kind and item only; the person's reason is not copied into the audit log.
- **The person is told** under Inbox Updates when their request is approved or declined, with the administrator's note (R5).
- **Not yet:** closing an approved request automatically once the item is on.
