# NortPole — Workflows (R6) and Knowledge (R7) design

Written 2026-11-14 after a review of Microsoft Copilot Studio, Google Gemini Enterprise, ChatGPT Enterprise, Claude Enterprise, Glean, Dust, Salesforce Agentforce and ServiceNow (sources at the end). It extends `NortPole_Redesign-Plan.md` stages R6 and R7.

## 1. Principles

1. **Nothing does work without a person's yes.** A scheduled run prepares a plan and stops. No "approve for this session".
2. **Off until an administrator turns it on.** Scheduling, event triggers and restricted domains start off.
3. **A person's own permissions, always.** A scheduled run searches as its owner; a domain only shows what the person can open in the source.
4. **Reuse the core.** Drafts, packs, route policy, document sets, groups, connectors, notifications and the audit chain already exist; this design adds thin tables on top.
5. **Every change is audited; personal text is not copied into the audit log.**

## 2. What other platforms do, and what we take

| Pattern | Seen in | NortPole decision |
|---|---|---|
| Manual, scheduled and event triggers | Copilot Studio, Glean, Gemini, ChatGPT | Scheduled in R6; event triggers later (R6c), off by default |
| Scheduling off by default, enabled for chosen groups | Glean | **Adopt** |
| One-time and recurring tasks | ChatGPT, Claude | **Adopt** |
| Pause for human input or approval | Copilot Studio, ServiceNow, ChatGPT | Already the core rule (plan, then exact-content approval) |
| "Approve for this session" on tool calls | Copilot Studio | **Reject**: weakens exact-content approval |
| Step-by-step run trace | Gemini | **Adopt** (run history per schedule) |
| Share a workflow with a team | Gemini, ChatGPT | **Adopt**: a shared schedule is a template; each person runs their own copy |
| Visual drag-and-drop builder | Copilot Studio, Gemini | Not now: Studio form plus signed packs governs better |
| Spaces decide who can use an agent | Dust | **Adopt** as domains |
| Collections per topic | Glean, NotebookLM | Domains cover this |
| Verified / deprecated with owner and re-check reminder | Glean | **Adopt** |
| Federated or indexed per source, sync frequency | Gemini | Show sync state per source; choice stays with the core connector settings |
| Uploaded copies that skip per-user checks | Copilot Studio (a known trap) | **Avoid**: uploads live in a personal or restricted domain, never shared silently |
| Narrow agents (about 15 actions per topic) | Agentforce | Already: workflow agents have one tool and at most 4 searches |

## 3. Workflows (R6)

### 3.1 Concepts

- **Schedule:** a saved workflow (a pack template or the person's own request) plus a cadence. It belongs to one person and runs as that person.
- **Run:** one firing of a schedule. It creates a draft, drafts the plan through the route policy, and stops in `plan_review`. The plan waits in Inbox → To approve.
- **Newer replaces older:** if the previous run's plan is still waiting when the next run fires, the old draft moves to `superseded` and the new one takes its place.
- **Auto-pause:** after **3 runs in a row** whose plans were never accepted, the schedule pauses and the owner gets an Inbox update. Accepting a plan resets the count.
- **Skip with a reason:** a run is skipped (and recorded) when the pack is no longer active, has not passed evaluation on the current model, or the route policy refuses the plan. Three skips in a row also pause the schedule.

### 3.2 Data

`evolvxsi_workflow_schedule`

| Column | Notes |
|---|---|
| id, owner_id | The person it runs as |
| name | Shown in Inbox and lists |
| pack_id, pack_template | Or null for the person's own request |
| title, request, desired_output | The draft each run starts from (a snapshot; editing the schedule changes future runs only) |
| cadence | `once`, `daily`, `weekdays`, `weekly`, `monthly` |
| at_time, timezone, weekday, month_day | When it fires; times are stored with the owner's time zone |
| next_run_at | Computed; indexed |
| state | `active`, `paused`, `ended` (after a one-time run) |
| pause_reason | `owner`, `unaccepted`, `skipped`, `admin`, `scheduling_off` |
| unaccepted_streak, skip_streak | For auto-pause |
| shared_with_group_ids | Groups that may copy it (sharing, 3.5) |
| copied_from_id | When a person copied a shared schedule |
| version, created_at, updated_at | Writes name the version they were based on, as drafts do |

`evolvxsi_workflow_run`: id, schedule_id, task_id (nullable when skipped), fired_at, outcome (`plan_ready`, `plan_failed`, `skipped`, `superseded`, `accepted`, `draft_ready`, `approved`, `cancelled`), reason, route_kind, input_tokens, output_tokens.

`evolvxsi_task` gains `schedule_id` (nullable) and the new state `superseded` (a transition from `plan_review` only, shown in My drafts as "Replaced by a newer run"; it counts as ended for retention).

Settings in the key-value store `evolvxsi_schedule_controls`: `enabled` (default **false**), `group_ids` (empty = everyone once enabled), `max_per_person` (default 10), `min_cadence` (default `daily`; no hourly schedules in the pilot), `two_admin` (whether changing these needs a second administrator, using the existing admin-changes flow).

### 3.3 Running

- A Celery beat entry `evolvxsi-workflow-schedules` runs **every 5 minutes**. It **claims** due schedules in a short transaction (`SELECT … FOR UPDATE SKIP LOCKED`, then set `next_run_at` to the next time and commit), so two workers never fire the same one, and the slow planning call happens **after** the claim, holding no lock.
- **Missed runs are not caught up.** After downtime a schedule fires once and moves on to its next time.
- **Load:** at most 20 runs per tick; the rest wait for the next tick. The schedule form spreads start times by a few minutes after the chosen time, so ten 08:30 schedules do not hit the model at once.
- For each: check scheduling is on, the owner is still **active** and still in an allowed group (if not: pause, reason `scheduling_off` or `owner_inactive`); supersede a waiting plan **with the same version check people use**, so if the owner accepted it a moment earlier the accept wins and the run is recorded as `accepted`; create the draft; draft the plan with the same code as Start (`draft_plan` or `draft_agent_plan`, the owner's permissions, the route policy); record the run and tokens; compute `next_run_at`.
- A run never accepts a plan or sends anything, and **reads no knowledge**: agent plans only list the searches they will make, and those run after the owner accepts.
- **Tokens per run:** today tokens are counted per day and model only. The planner will return the call's token counts so the run row can store them; Quality sums them with the existing price rules.
- Failures are recorded on the run and shown in history; they never retry in a loop (the next fire is the retry).

### 3.4 Screens

- **Workflows → Start:** each template tile gets **Schedule…** next to Start a draft.
- **Workflows → My drafts:** a finished draft gets **Repeat on a schedule…**.
- **Workflows → Scheduled:** the person's schedules: name, cadence in words ("Weekdays at 08:30, Europe/London"), next run, last outcome, state, **Pause / Resume / Edit / Delete**, and **History** with each run's trace (fired → plan drafted on route → waiting → accepted / superseded / skipped with reason → draft ready → approved). Shared schedules the person may copy appear under "Shared with you".
- **Schedule form:** name; cadence; time and time zone (the browser's by default); for monthly, the day; a one-line reminder: "Each run prepares a plan and waits for you in Inbox. Nothing runs further without your yes."
- **Inbox → To approve:** scheduled plans show "Scheduled: name" and the run time.
- **Admin → Agents & tools → Scheduling:** turn on or off, allowed groups, limits; every schedule in the workspace with owner, state and last outcome; an administrator can pause any schedule (the owner is told).
- **Admin → Quality:** scheduled runs in the period, share accepted, auto-paused schedules, and tokens and cost for scheduled runs (using the existing price rules).

### 3.5 Sharing

The owner can share a schedule with groups. People in those groups see it under "Shared with you" and **copy** it: the copy is theirs, runs as them, and is independent. No one runs work as someone else, and the original owner sees no one's drafts. The copy is checked at copy time and at every run against the copier's own access (pack requirements, route policy, scheduling group); a copy the copier may not run is refused with the reason.

### 3.5a Lifecycle

Deleting a person deletes their schedules (cascade). Deactivating a person pauses them. Run rows follow the retention period for usage counts.

### 3.6 Audit

`schedule.change` (create, edit, share, delete), `schedule.state` (pause, resume, auto-pause, admin pause), `schedule.fire` (outcome and reason; no request text), `schedule.controls` (admin settings). Titles and requests stay out of the audit record, as for drafts.

### 3.7 Event triggers (R6c, later)

Start a scheduled-style run when a connected source changes (for example, a new file in a Drive folder). Off by default, enabled per group, only for sources the owner can read, and still stopping at the plan. Waits for the Google Drive connector.

### 3.8 Tests

Unit: next-run computation across time zones, daylight-saving changes, month ends, weekdays. Integration: a due schedule fires once with two workers; it stops at `plan_review`; supersede; auto-pause after 3; skip when the pack is inactive or the route refuses; scheduling off pauses; copy of a shared schedule runs as the copier; audit has no request text. Browser: create, see the plan in Inbox, accept, history trace, pause and resume, admin turning scheduling off; 1280 and 390 pixels, axe.

### 3.9 Stages

| Stage | Contents | Size |
|---|---|---|
| R6a | Tables, controls, beat runner, supersede, auto-pause, skip, audit, Inbox label | Medium |
| R6b | Scheduled tab with history, Schedule buttons, sharing and copy, admin Scheduling page, Quality numbers | Medium |
| R6c | Event triggers | After the connector |

## 4. Knowledge (R7)

### 4.1 Concepts

- **Domain:** a named area of knowledge (Finance, HR, Legal…). Each domain is backed by one core **document set** (the sources and folders in it) and has:
  - **open** or **restricted** access. Open: everyone in the workspace. Restricted: members (groups).
  - **owners**, who may verify documents and approve additions.
- **How restriction is enforced (review fix):** a document set's own visibility only hides the set in pickers; its documents would still appear in an "all knowledge" search. So a restricted domain is enforced through the **reading groups of its sources** (the A5 per-source data-access groups that feed every document's access list): each source in a restricted domain gets the domain's member groups as its reading groups. Search, chat and agent searches then exclude the documents for non-members everywhere, not only in the picker.
- **One restricted domain per source.** A source may sit in several open domains but in at most one restricted domain, so two domains never disagree about who may read a document. The admin page refuses a second restricted domain for the same source.
- **Company knowledge** is the default open domain; it cannot be removed or restricted.
- **Uploaded data:** a person's files. They live in **My files** (private, the core's user files and projects as folders) or in a **restricted domain** the person belongs to. Moving files into an open domain or Company knowledge is a request that a domain owner or administrator approves. Uploads never become visible to others silently.
- **Who can use what:** an assistant or workflow bound to a restricted domain can be used only by that domain's members (Dust's rule). Search and answers only include documents the person can open in the source system, as now.
- **Verification:** an owner of any domain that holds the document marks it **verified** (with a re-check date) or **deprecated**. Verification is **per document**, not per domain, so a document never shows two different badges. Badges show who and when. Deprecated documents rank lower and a draft that cites one gets a warning. When a re-check is due, the owner gets an Inbox item.
- **Freshness:** every result and citation shows when the document last changed in its source; each domain shows when each source last synced.

### 4.2 Data

`evolvxsi_domain`: id, slug, name, description, document_set_id, access (`open`, `restricted`), member_group_ids, member_user_ids, owner_user_ids, is_default, created_at.

`evolvxsi_doc_verification`: document_id (unique), state (`verified`, `deprecated`), by_email, at, recheck_at, note. One current row per document and domain; history in the audit log.

`evolvxsi_source_request` gains the kind `knowledge` (add files to a domain), reusing the R4 request and decision flow; the decision is made by a domain owner or an administrator. **A deliberate exception to R4's "approving turns nothing on":** here approving performs the addition, because it is a change inside the workspace that the approver owns and it widens nothing beyond the domain's members; it is recorded in the audit log. The files are **copied** into a file source that belongs to the domain (so they take the domain's reading groups); the person's private copy stays private.

Packs may declare domains for a template or workflow agent (`Template.domains`); the agent's searches are limited to those domains.

**Assistants bound to a restricted domain:** when a chat assistant uses a restricted domain's document set, it may only be shared with that domain's member groups (checked when sharing) and is refused to anyone else at use time. Even without this check the reading groups would keep the documents out; the check stops people seeing an assistant that cannot help them.

### 4.3 Screens

- **Knowledge (user):** tabs **Company knowledge**, **Domains** (those the person can see: name, access, owners, sources, last sync, verified count) and **My files** (uploads and project folders, with "Request to add to a domain").
- **Search and New:** a domain picker ("All my knowledge", one domain, "My files"). Results show domain, source, last changed and a verified or deprecated badge.
- **Draft review:** citations show the badge and last-changed date; a deprecated citation shows a warning.
- **Admin → Knowledge → Domains:** create and edit domains, access, members, owners, sources (document set); **Verification** (documents due for re-check, deprecated documents); **Requests** (knowledge requests, also in Approvals); **Index status**; **Allowed source types** (the Discover connector list becomes an editable allow-list).

### 4.4 Audit

`domain.change` (create, edit, access, members, owners), `doc.verify` (verified, deprecated, cleared), `knowledge.request` and decision (through `source.request` actions with kind `knowledge`).

### 4.5 Prerequisites and risks

- **A search index and a real source.** The sandbox runs without a vector index (`DISABLE_VECTOR_DB=true`). R7 needs the index on and at least one connector: the paused **Google Drive** connector, or the core's file connector for a first test.
- **Permission sync for restricted domains.** Restricted access narrows what the source already allows; it never widens it.
- **Ranking change for deprecated documents** is applied after retrieval (a lower score for deprecated documents, no index change) and must be tested on recorded queries so verified content does not crowd out relevant content.
- **Moving a source into or out of a restricted domain changes its reading groups**, which re-syncs every document's access list; on a large source this takes time, and until it finishes the old access applies. The admin page shows the sync state.

### 4.6 Tests

Integration: open and restricted domains filter search; a non-member cannot use an assistant bound to a restricted domain; a file in My files is invisible to others; a knowledge request moves files only after approval, by an owner or administrator; verification badge, re-check reminder and deprecated warning in a draft; audit rows. Browser: Knowledge tabs, domain picker in Search and New, admin Domains; 1280 and 390 pixels, axe.

### 4.7 Stages

| Stage | Contents | Size |
|---|---|---|
| R7a | Domains on document sets, access, Company knowledge default, admin Domains, domain picker in Search and New | Large |
| R7b | My files, knowledge requests and moves, domain-bound assistants and workflow agents | Medium |
| R7c | Verification, re-check reminders, deprecated warning, freshness on citations | Medium |

R7 starts after the search index is on in the sandbox and the Google Drive connector (A5) is resumed.

## 5. Review, 2026-11-14

A review of this design against the code found one flaw and several gaps; all are fixed above.

| Finding | Severity | Fix |
|---|---|---|
| A restricted domain built only on document-set visibility would still let its documents appear in an "all knowledge" search | **Critical** | Enforce through the sources' reading groups (A5), which feed every document's access list (§4.1) |
| A source in two restricted domains would have two answers to "who may read this" | High | At most one restricted domain per source (§4.1) |
| Planning under a row lock would hold locks for the length of a model call | High | Claim and commit first, plan afterwards (§3.3) |
| A runner superseding a plan the owner is accepting at that moment | High | Same version check as people; the accept wins (§3.3) |
| After downtime, catch-up could fire many runs at once; many schedules at one time spike the model | Medium | No catch-up; at most 20 per tick; start times spread (§3.3) |
| Per-run cost was promised, but tokens are counted per day and model only | Medium | The planner returns token counts; stored per run (§3.3) |
| A deactivated or deleted person's schedules kept running | Medium | Pause on deactivation, delete with the person (§3.5a) |
| A copied schedule the copier may not run | Medium | Checked at copy and at each run (§3.5) |
| Verification per document and domain could show two badges | Medium | One verification per document (§4.1, §4.2) |
| "Approving performs the move" contradicted R4's rule | Medium | Stated as a deliberate, bounded exception; files are copied into a domain source (§4.2) |
| Assistants tied to a restricted domain could still be shared with others | Low | Share-time and use-time check (§4.2) |
| The `superseded` state had no place in My drafts or retention | Low | Defined (§3.2) |

Not changed: research caveats remain (vendor and third-party sources; several 2026 features in preview). Email or push notice for a ready plan is out of scope; the Inbox badge covers it.

## 6. Decisions taken (owner may change them)

1. Minimum cadence daily; no hourly schedules in the pilot.
2. Auto-pause after 3 unaccepted plans or 3 skips in a row.
3. Sharing a schedule means others copy it; no one runs as someone else.
4. Domain owners (not only administrators) verify documents and approve additions to their domain.
5. Deprecated documents are ranked lower and flagged, not hidden.
6. Uploads are private by default; nothing moves to a shared domain without approval.

## 7. Order

R6a → R6b → R8 pass for R1–R6 → (Google Drive connector and search index) → R7a → R7b → R7c → R6c.

## Sources

Microsoft: [Copilot Studio overview](https://learn.microsoft.com/en-us/microsoft-copilot-studio/overview), [human approval for tool calls](https://mc.merill.net/message/RM570434), [human-in-the-loop lab](https://microsoft.github.io/mcs-labs/labs/human-in-the-loop), [unstructured data as knowledge](https://learn.microsoft.com/microsoft-copilot-studio/knowledge-unstructured-data), [Dataverse indexer sample](https://microsoft.github.io/CopilotStudioSamples/authoring/solutions/dataverse-indexer/). Google: [Gemini Enterprise workflows](https://docs.cloud.google.cn/gemini/enterprise/docs/workflow-builder/workflow-agents), [release notes](https://docs.cloud.google.com/agentspace/docs/release-notes), [connectors and data stores](https://docs.cloud.google.com/agentspace/docs/introduction-to-connectors-and-data-stores). OpenAI: [workspace agents](https://help.openai.com/en/articles/20001143-chatgpt-workspace-agents-for-enterprise-and-business[2]), [connectors](https://help.openai.com/en/articles/10128477-chatgpt-enterprise-and-edu-connectors), [company knowledge](https://venturebeat.com/ai/openai-launches-company-knowledge-in-chatgpt-letting-you-access-your-firms). Anthropic: [release notes](https://support.claude.com/en/articles/12138966-release-notes). Glean: [schedule triggers](https://docs.glean.com/agents/concepts/schedule-triggers), [verification](https://docs.glean.com/user-guide/knowledge/verification/how-verification-works). Dust: [access controls](https://docs.dust.tt/docs/access-controls-and-permissions). Salesforce: [Agentforce architecture guide](https://sf-cta-study-cfh.pages.dev/04-solution-architecture/agentforce-architecture/). ServiceNow: [approval assistance agent](https://www.servicenow.com/docs/r/intelligent-experiences/platform-approval-aia.html). Several sources are vendor or third-party pages and many 2026 features are in preview; treat them as direction, not specification.
