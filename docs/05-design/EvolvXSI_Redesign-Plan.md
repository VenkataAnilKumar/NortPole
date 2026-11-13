# EvolvXSI — UI and admin console redesign

Agreed with the owner on 2026-11-13. This plan follows UI plan U1–U6 (`EvolvXSI_UI-Plan.md`) and replaces its navigation. Every stage ends with the quality pass: light and dark, 1280 and 390 pixels wide, axe WCAG 2.1 A/AA, keyboard.

## The rule behind the split

The user side is for using things and asking for them. The admin console is for owning them. Each user tab has a matching admin section, and every request lands in one admin **Approvals** queue. Nothing changes unless an administrator approves it.

## User side

| # | Tab | Features | Status |
|---|---|---|---|
| 1 | **New** | Chat box and assistant picker, attachments, choose which knowledge to use, a badge for where the message goes (local, private, cloud), and "Make it a draft". | Exists; knowledge picker new |
| 2 | **Inbox** | Filters **To approve** (second-approver sends, scheduled plans), **To review** (drafts ready), **Updates**. A count on the tab. A newer scheduled plan replaces the older one. | Exists; filters R5 |
| 3 | **Search** | One search over company knowledge and the person's uploads, filtered by domain, source and date. Each result shows its source and who can see it. | Exists; domain filter R7 |
| 4 | **Agent** | Chat assistants only, each card showing what it reads and which tools it may use. Workflow agents live in Workflows. | Exists (sidebar Agents section); cleanup R3 |
| 5 | **Workflows** | Tabs **Start** (packs; a "Run by" card shows the agent's plan), **Scheduled** (each run stops at the plan and waits in Inbox; a schedule pauses after 3 plans in a row go unaccepted), **My drafts**. | **R1 done** (tabs, addresses); scheduler R6 |
| 6 | **Knowledge** | **Company knowledge** by domain (read-only; source and freshness) and **Uploaded data** by domain (projects become optional folders), with "Request to add to company knowledge". | **R1 done** (renamed, company knowledge); domains and uploads R7 |
| 7 | **Sources** | Tabs **Skills** (what installed packs know: guides, review rules, house style, workflow agents), **Connectors** (connected systems), **Plugins** (tools assistants may use and whether each is allowed). Request buttons come later. | **R1 done** (read-only); requests R4 |
| 8 | **Recent** | Chats, drafts and workflows opened recently. Pin, rename, delete. | Exists |
| 9 | **Settings** | Profile, theme, language, memory, personal tools, notifications; Admin link for administrators. | Exists |

The group keeps the owner's name **Sources**, although Skills and Plugins are not strictly sources.

## Admin console

| # | Section | Features |
|---|---|---|
| 1 | **Overview** | Health, usage and cost, approvals waiting, audit chain status, sync problems. |
| 2 | **Approvals** | One queue: second-approver sends, two-administrator changes, knowledge, connector, tool and assistant requests, outside-tool definitions. |
| 3 | **Knowledge** | Domains, connectors (setup, sync, permission sync), company knowledge, upload requests, index status. |
| 4 | **Agents & tools** | Chat assistants, workflow agents, packs and signers, Studio, tool catalog, outside tools with pinned definitions, action targets. |
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
| `/app/sources` | `/app/sources/skills` |

The old addresses redirect (HTTP 307, set in `next.config.js`) because home cards, bookmarks and audit records use them. `/app/plugins` (a person's own plugins, and its OAuth callback) is unchanged and shows under Sources.

## Stages

| Stage | Work | Size | State |
|---|---|---|---|
| R1 | Sidebar order and names, Workflows and Sources tabs, Knowledge rename, redirects, read-only Skills, Connectors and Plugins | Small | Done |
| R2 | Admin console regroup, merged Approvals queue, hide inherited screens | Small to medium | Done |
| R3 | Workflows Start cleanup ("Run by" card), Agent tab for chat assistants only | Medium | Next |
| R4 | Request buttons on Sources (skill, connector, plugin), landing in Approvals | Medium | |
| R5 | Inbox filters | Small | |
| R6 | Scheduled workflows: scheduler, stop at the plan, auto-pause, cost on Quality | Medium | |
| R7 | Knowledge domains, uploads by domain, request and approve, domain filter in search | Large | After the Google Drive connector |
| R8 | Quality pass of each stage | Small per stage | Ongoing |

New page text is in English first; sidebar labels are translated into all nine languages in the same stage.
