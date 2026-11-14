# NortPole — UI specification

Status: **platform surfaces and proposed first-workflow screens** · Updated: 2026-11-09

## Portal and surface inventory (L01)

| Surface | Audience and primary job | Delivery scope |
| --- | --- | --- |
| Unified Workspace | Practitioners start tasks, inspect evidence, and reopen results. | First workflow |
| Review & Approval | Reviewers request changes or approve the exact artifact version. | First workflow, within Workspace |
| Enterprise Admin | Admins grant workflow and source access, configure destinations and inspect audit records. | Basic controls first; enterprise provisioning later |
| Run Operations & Evaluation | Operators diagnose failures; authors compare candidates before publication. | Run history first; full diagnostics and evaluation views later |
| Agent & Automation Studio | Authors define, test, publish, schedule and disable workflows. | One configured workflow first; self-service authoring later |
| Developer Portal | Developers start authorized runs and inspect results using documented contracts. | API contract first; quickstarts, webhooks and SDK guides later |
| Deployment Console | Customer operators manage health, upgrades and recovery. | When the selected deployment needs customer operation |
| Public Website & Demo | Buyers discover capabilities and evaluate a governed workflow. | Commercial rollout |
| Trust & Legal Center | Buyers and security teams inspect deployment and data commitments. | Commercial rollout, with claims matched to verified evidence |
| Support Console | Authorized support staff manage entitlements, rollout and support cases. | Controlled customer rollout |
| Embedded Experiences | Users interact through Slack, Teams or customer applications. | Start with status and links; add actions after channel authorization is verified |

Use the same tenant policies and run contracts across these surfaces. Pack views use a controlled host interface and receive only authorized records and actions.

## User Portal

The employee workspace opens on a request composer with recent tasks and approved workflows nearby. Task detail keeps the request, current status, output, citations and run activity together. Reviewers see decisions only for the records and versions they are authorized to review.

Tab names are short. Each tab can have sub-tabs; sub-tabs are proposed and appear only when their capability is usable and authorized. Earlier drafts listed Knowledge, Skills and Connectors as tabs. Knowledge is now **Libraries**; Skills is a sub-tab of Agents; personal connectors sit under My Files and Settings, and plugins under Apps and Packs.

| Tab | Sub-tabs | User features | Earliest delivery |
| --- | --- | --- | --- |
| New task | Ask, Task, Model, Quick starts | Describe a request, choose an approved workflow and a model route, then get a cited answer (Ask) or save a draft (Task). An explicit Start shows the scope before anything runs. Slash commands run permitted skills. | Fixture composer, then pilot evidence |
| Tasks | Active, Drafts, Done, Detail | Open drafts, explicitly start a run, inspect progress, replay and retry steps, reopen results. | Fixture |
| Search | Answers, Sources, Filters | Cited answers over permitted sources with access state and versions; turn a result into a task. | Pilot |
| Agents | Approved, Mine, Shared, Skills, Studio | Discover and launch approved agents with visible permissions, tools and the routes each has passed evaluation on. Skills lists approved reusable capabilities. Studio is the authoring surface. | Pilot selected workflow, then catalog; Skills and Studio expansion |
| Libraries | Shared, Team, Status | Browse permitted shared knowledge, search it, and see indexing, freshness and conflicts. | Pilot one source, then expansion |
| Automations | Schedules, Triggers, History | View schedules, triggers and run history. Authorized users can pause or change schedules. | Expansion |
| Apps and Packs | Installed, Browse, Plugins | Open installed domain applications and workflows within granted permissions. Plugins are installed by an administrator. | Pilot selected pack, then catalog |
| My Files | Uploads, Connected, Memory | Uploaded files with parsing status; personal connected accounts where policy allows; view, edit and delete memory. | Pilot as required; Connected and Memory expansion |
| Projects | Overview, Tasks, People | Organize shared goals, files, instructions, tasks and deliverables. | Expansion |
| Inbox | Needs action, Resolved, Updates | Follow assignments, approvals and results. Authorized reviewers act on a specific version or action payload. | Pilot review, then unified inbox |
| Settings | Profile, Appearance, Models, Notifications, Memory, Accounts, Prompts, Privacy, Security | See User Settings below. | Pilot as required |

### Model route picker

The composer and Search show the current route (Auto, Local, Private or Cloud). Routes the administrator's policy blocks for the task's data class stay visible but disabled, with the reason. A pack or agent offers only the routes on which its exact version has passed evaluation. A blocked route fails before any content is sent, and fallback never leaves the allowed set. User choice is a preference inside administrator policy and never overrides it ([decision 0002](../decisions/0002-hybrid-routing-and-pilot-scope.md)).

### User Settings

User Settings are personal. They are separate from the Admin Console's Platform tab, which governs the organization. A setting an administrator locks appears read-only with the reason, and no user setting grants access to a source or workflow.

| Settings tab | Features | Earliest delivery |
| --- | --- | --- |
| Profile | Name and photo; workspace selection; role and approver status (read-only); language and time zone. | Pilot as required |
| Appearance | Theme (Light, Dark, System); increased contrast; reduced motion; density. | Pilot as required |
| Models | Default route; ask before switching; allowed routes with policy reasons; cost view where permitted. | Pilot |
| Notifications | Channels, events and quiet hours; administrator-required channels shown. Alerts never include source or report text. | Pilot |
| Memory | View, edit, delete and pause scoped memory; restricted scopes shown. | Expansion |
| Accounts | Connected personal accounts, their permissions, disconnect, and requests for access, subject to the extension level. | Expansion |
| Prompts | Saved prompts and task templates, slash commands, keyboard shortcuts. | Expansion |
| Privacy | Activity history, export and deletion within retention rules, sharing defaults. | Proposed; depends on retention decisions |
| Security | Sessions, sign-in and MFA status, developer sandbox tokens. | Proposed; depends on identity decisions |

## Admin Console

Provide a separate navigation context for authorized administrators and operators. Administrative permissions govern configuration and operations. Content reads still require the relevant resource and source grants.

Tab names are short; sub-tabs are proposed. Mapping from earlier names: Organization & Workspaces is **Workspaces**, People & Access is **People**, Security & Governance is **Security**, Models & Inference is **Models**, Agents & Deployments is **Agents**, Skills & Packs is **Packs**, Integrations & MCP is **Connectors**, Knowledge & Data is **Knowledge**, Observability & Evaluation is **Quality**, Usage & Billing is **Usage**, and Platform Settings is **Platform**.

| Tab | Sub-tabs | Admin features | Earliest delivery |
| --- | --- | --- | --- |
| Overview | Health, Alerts, Activity | See service and connector health, failed runs, policy alerts and recent admin changes. | Pilot diagnostics, then overview |
| Workspaces | Orgs, Environments, Retention | Configure workspace ownership, provisioning, environments, retention and residency. | Expansion |
| People | Users, Roles, Grants, Identity | Manage users, roles and source and workflow grants, with an effect preview before revoking. Add SSO, SCIM and service identities when selected. | Pilot basic roles |
| Security | Approvals, Tools, Data, Defense, Network, Extensions, Audit | Autonomy tiers and approvals; tool policy; sensitive-data redaction; prompt-injection policy; isolation and network rules; extension levels (Off, Request, Self-serve); audit history and export. | Pilot policy and audit |
| Models | Routes, Policy, Fallback, Test, Limits | Configure approved routes (Local, Private, Cloud, customer-supplied), allowed routes by data class, fallback order, a test of a request against policy, and usage limits. | Pilot one route; hybrid routing expansion |
| Agents | Versions, Publish, Rollout, Inventory | Inspect versions and owners, run the publish gate, activate per tenant, disable and roll back, and list every active agent, skill, connector and tool. | Pilot configured publication, then broader deployment |
| Packs | Catalog, Compatibility, Install, Signing | Check compatibility and per-route evaluation, approve versions, install, upgrade and roll back. Accept only signed packages. Access grants are separate from installation. | Pilot selected pack, then registry |
| Connectors | Sources, Tools, MCP, Webhooks | Register sources and tools, configure scopes and credentials, allow or block MCP servers, set read and write permission per tool, inspect health and the call log, and revoke access. | Pilot one connector, then MCP registry |
| Knowledge | Sources, Permissions, Memory, Quality | Manage source indexing, permission synchronization, memory scopes, retention and deletion; flag stale, superseded and conflicting sources. | Pilot one source |
| Quality | Runs, Evals, Feedback, Trends | Inspect authorized run diagnostics, evaluation evidence by version and route, reviewer feedback and quality regressions. | Pilot checks, then operational views |
| Usage | Spend, Quotas, Export | Track spend by user, group and agent; apply quotas, rate limits and cost alerts; export metering. | Expansion |
| Platform | Deploy, Keys, API, Backup | Manage the deployment profile, customer-managed keys and residency, API access, webhooks, feature flags, backups and recovery. | Pilot operational setup, then broader controls |

The fixture exposes New task and Tasks. Pilot navigation adds only working search, library, review and administration capabilities. Expand tabs when their workflows are usable and authorized. Agent Studio remains the authoring surface, and the Developer Portal remains the integration surface. These are proposed navigation and delivery scopes.

## Screen inventory

| Screen | Main content | Primary action | Required states |
| --- | --- | --- | --- |
| Task list | Owned and shared tasks, status, owner, update time, search. | Create draft. | Empty, loading, results, error. |
| New task | Question, scope, desired output, source constraints. | Save draft. | Valid, incomplete, denied, unavailable workflow. |
| Task detail | Progress, plan, evidence, drafts, comments, activity. | Continue current step. | Planning, waiting, running, failed, draft ready, approved. |
| Plan review | Outline, source coverage, gaps, editable scope. | Accept plan. | Pending, changed, accepted, rejected. |
| Evidence view | Claim, source title, passage, location, date, access state. | Open source. | Available, stale, missing, access removed. |
| Draft review | Structured artifact, claim links, revisions, comments. | Approve or request revision. | Draft, revision pending, rejected, approved. |
| Source admin | Connection status, permissions, last refresh, errors. | Connect or disable source. | Connected, syncing, partial, failed, disabled. |
| Workflow admin | Versions, policy, evaluation summary, publication. | Publish version. | Draft, evaluating, failed gate, published, disabled. |
| Run operations | Searchable run list, steps, error category, cost estimate. | Inspect or retry. | Healthy, waiting, failed, completed. |

## Task detail layout

Use a clear task header with status and owner, a main artifact area, and a side panel for evidence and run activity. Keep the current action visible. When a user selects a claim, show the exact linked passage and its source location. When source access has changed, withhold the affected artifact until its access can be revalidated or its content safely regenerated.

## Workspace review flow

A question becomes a saved draft. Show an explicit Start action before creating a run. In the result view, selecting a claim opens its source passage and version. Mark an unsupported finding in plain language. Keep revision and approval actions beside the version under review. On a later visit, show whether that version is approved and whether its sources are still accessible. A restricted item should expose a useful status without revealing its title or text when those are protected.

## Interaction rules

- Show what the agent will do before the user starts a consequential run.
- Display explicit waiting states for plan review, tool approval, and final approval.
- Separate **Save draft**, **Request revision**, **Reject**, and **Approve** actions.
- Require approval for every first-release external write; summarize target and payload. Changed arguments require fresh approval.
- Keep user edits distinct from generated text in version history.
- Never show a success toast before the server confirms the action.

## Accessibility and content

All main flows must be keyboard usable. Controls have visible labels and focus states. Status uses text and icon, never color alone. Errors identify the affected step and a recovery action. Evidence links must have meaningful names. Avoid animated progress that obscures whether the run is actually active. Select the accessibility standard and test method during delivery planning.

## Responsive behavior

At narrow widths, stack the evidence panel beneath the artifact and preserve a way to jump between a claim and source. The approval action remains clear, but never becomes a floating button that hides report content.

## Open design decisions

Artifact format, source citation style, plan-review timing, collaboration model, mobile priority, and whether a dedicated agent studio is needed for the first customer.

## Feature coverage by surface

| Surface group | Feature references |
| --- | --- |
| Workspace and review | PF-01.01–03, PF-01.06, PF-01.08–01.10, PF-01.12, PF-04.02, PF-05.05, PF-06.01, PF-06.03–06.05, PF-08.06 |
| Studio | PF-01.05, PF-01.11, PF-02.01–06, PF-03.02, PF-03.05, PF-05.03, PF-09.02, PF-09.04 |
| Enterprise Admin | PF-03.05, PF-04.01–07, PF-07.03–07.06, PF-08.01–02, PF-08.05–08.06, PF-10.04 |
| Developer Portal and embedded channels | PF-01.04, PF-01.13, PF-03.03–03.04, PF-08.02–08.04 |
| Public Website, Trust Center and Support Console | PF-01.07, PF-04.06 |
| Run Operations and Deployment Console | PF-09.01–09.07, PF-10.02–10.05 |

The [feature catalog](../04-specs/EvolvXSI_Feature-Spec.md#full-platform-feature-catalog) specifies what each capability must demonstrate. The portal inventory also covers public, trust and support surfaces for rollout.
