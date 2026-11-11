# EvolvXSI — delivery plan on the adopted core

Status: **proposed; supersedes the sequencing (not the scope) of the fixture-first plan** · Updated: 2026-11-11

This plan rebuilds the delivery sequence around [decision 0004](../decisions/0004-adopt-community-source-as-pilot-core.md): the pilot runs on adapted Onyx Community Edition source in `services/core` and `apps/workspace`, with EvolvXSI-owned governance added in separate modules. The earlier [P00–P11 plan](EvolvXSI_Implementation-Phases.md) stays valid as the scope reference and the source of acceptance wording; this document records what is actually done and the order of what remains. It commits no dates, no staffing and no customer.

How to read it: **Done** means verified in a sandbox on 2026-11-10 (not production). **Sizes** are relative (S, M, L, XL), not time estimates. **PF IDs** refer to the [feature catalog](../04-specs/EvolvXSI_Feature-Spec.md#full-platform-feature-catalog). Every phase ends with evidence a reviewer can check.

## Phase summary

| Phase | Name | Status | Size | Old plan |
| --- | --- | --- | --- | --- |
| A0 | Direction, documents and designs | Done | M | P00 (partly) |
| A1 | Adopt and rebrand the core | Done | L | New |
| A2 | Run, verify and restyle | Done | L | P01–P02 (partly) |
| A3 | Hybrid routing and governance first slice | Done | M | P03, P08 (slice) |
| A4 | Product shell and navigation | Next | M | P06 (UI) |
| A5 | Knowledge, evidence and permissions | Planned | XL | P04 |
| A6 | Reviewed task workflow and approvals | Planned | XL | P03, P06 |
| A7 | Agents, skills, packs and extension levels | Planned | L | P05, P07 |
| A8 | Real model routes, evaluation and spend | Planned; needs model access | L | P02 live, P08 |
| A9 | Security and trust hardening | Planned | L | P03, P10 |
| A10 | Deployment, operations and upstream upkeep | Planned | L | P10 |
| A11 | Pilot with one vertical | Planned; needs customer | XL | P09 |
| A12 | Expansion | Later | XL | P11 |

## Critical path and parallel work

- **Critical path:** A4 → A5 → A6 → A8 → A11. Search and approvals depend on knowledge; the pilot depends on a real model and a customer.
- **Can run in parallel:** A7 (packs) with A5/A6 once the pack manifest is fixed; A9 (hardening) with A6; A10 (deployment) from A5 onward.
- **Blocked on inputs only you can give:** real local and cloud model access (A8), a first customer, vertical and source system (A5, A11), the hosting target and retention rules (A10), trademark review (A9). Without them, A4, A7 (design and contracts) and parts of A9 and A10 can still proceed on the mock routes.

## A0 — Direction, documents and designs (done)

**Goal:** a coherent product definition and a visual direction.

Delivered: product definition, PRD, feature catalog (PF-01 to PF-10), architecture, API and data drafts, North feature mapping, decisions 0001–0004, Light/Dark/System design canvas (user and admin screens), tab and settings specifications.

**Exit evidence:** documents link-checked by `tools/validate_structure.py`; decisions recorded as proposed with open items listed.

**Still open (carried forward):** first customer and vertical, source system, retention periods, deployment target, numeric acceptance targets, final brand artwork and trademark checks.

## A1 — Adopt and rebrand the core (done)

**Goal:** a working product base without rebuilding commodity parts.

Delivered: MIT-licensed parts of Onyx Community Edition (commit `919578e`) copied into `services/core` and `apps/workspace`; all `ee` code, deployment files and documentation excluded; repeatable rebrand script (`tools/rebrand_onyx.py`); notices in `NOTICE` and `UPSTREAM.md`; upstream telemetry off by default; upstream addresses, CDN video and enterprise-only links removed; new logos, icons and backgrounds; licensed font removed.

**Exit evidence:** `UPSTREAM.md` lists what was copied, left out and changed. About 290 documentation links to the upstream site remain by design and are tracked for review.

**Risks carried forward:** every file edited in the adapted code raises the cost of taking upstream updates; legal review of trademark and notices is open.

## A2 — Run, verify and restyle (done)

**Goal:** the adapted product runs end to end and looks like EvolvXSI.

Delivered: lite-mode local profile (PostgreSQL, Redis, no search index or model server); dependency locks regenerated; backend imports and builds without `ee`; web source type-checks (apart from one package blocked in the sandbox); warm light and dark themes with System selection; centered serif home screen with quick-start cards; Manus/North-style chat box; sidebar relabelled (New task, Search, All agents, Tasks); admin-recovery command; offline tokenizer fallback; deterministic mock model routes; local profile runbook.

**Exit evidence:** sign-up, sign-in and a chat round trip through the UI on a mock route; 900+ unit tests passing in the sampled areas (skills, utils, auth, chat, route policy).

**Not verified:** the full unit suite, a production build, any real model, any connector.

## A3 — Hybrid routing and governance, first slice (done)

**Goal:** prove the differentiator on mock routes: a user chooses where work runs, inside an administrator's policy.

Delivered (PF-07.03 slice, PF-04.02 groundwork): route kinds (local, private, cloud) and data classes; fail-closed server check that refuses a blocked route with `POLICY_BLOCKED` before any content is sent; route picker (blocked routes shown disabled with the reason); admin Route Policy page with a test panel; stored audit trail of policy changes and refusals; 20 new unit tests.

**Exit evidence:** a live refusal recorded and shown on the admin page. **Limits:** one workspace-wide data class; no per-route evaluation; mock routes only; allowed requests are not logged; no audit pruning.

## A4 — Product shell and navigation (next)

**Goal:** the sidebar, settings and layout match the corrected specification, so later features have somewhere to live.

| Work item | Notes |
| --- | --- |
| Libraries, Inbox, Automations, Apps and Packs, My Files, Projects/Tasks pages | Start as honest empty or placeholder states; each is filled by a later phase. |
| Composer strip | Run on (exists), Project and Workflow chips wired to real state. |
| User Settings tabs | Appearance (Light/Dark/System), Models (default route), Notifications, then Memory, Accounts, Prompts. |
| Interface quality | Dark theme and narrow-width pass over every new page; accessibility checks (keyboard, contrast, labels); web fonts (Inter, Newsreader). |
| Translations | Labels in other languages, or a documented English-only fallback. |
| Admin tab names | Short tab names with sub-tabs from the UI specification. |

**Progress (2026-11-11):** Libraries and Inbox pages and sidebar entries exist. Libraries lists the backend's document sets and otherwise states plainly that sources cannot be connected without a retrieval index. The Inbox groups notifications into Needs action (approval types), Updates and Resolved, with a working Dismiss. Still to do in A4: Automations, Apps and Packs, My Files, the composer strip, the settings tabs, the dark and narrow-width pass, fonts and translations.

**Exit evidence:** every sidebar entry opens a real page; screenshot set in light, dark and narrow widths; keyboard-only path through the home, chat and settings screens.

**Dependencies:** none external. **Risks:** many upstream files touched; keep changes in separate components and styles where possible.

## A5 — Knowledge, evidence and permissions (planned, XL)

**Goal:** answers cite passages the asking user may see, and access changes take effect immediately (PF-06.01, PF-06.02, PF-01.02, PF-08.01, PF-04.02).

| Work item | Notes |
| --- | --- |
| Retrieval backend | Re-enable a vector index (the adapted code supports one) or an EvolvXSI-owned alternative; decide hosting. Lite mode has none. |
| One source connector | Choose the pilot source; ingestion status, failures, refresh. |
| Per-user permission sync | **Upstream keeps this in `ee`.** EvolvXSI builds its own for the chosen source: effective access per document, applied at retrieval, citation and export. |
| Cited search screen | Replace the stubbed search view: answer, numbered citations, source panel, access state, hidden-result notice without titles. |
| Revocation withholding | Reports, previews and exports that depend on a revoked source are withheld until regenerated; downloaded files cannot be recalled (state this in the pilot agreement). |
| Freshness and conflicts | Flag stale, superseded and conflicting sources (PF-06.05). |

**Exit evidence:** a fixed test set with a permitted document, a restricted document, a superseded version and an unanswerable question; denied content absent from answers and citations; revocation test passes; every citation resolves to a versioned passage.

**Dependencies:** a first source system and permission model (decision needed); a model route that can answer (A8, or the mock for plumbing). **Risks:** biggest unknown in the plan; permission semantics differ per source.

## A6 — Reviewed task workflow and approvals (planned, XL)

**Goal:** the PRD's first workflow end to end: draft, explicit start, plan, evidence, draft, review, exact-version approval, authorized export (FR-01 to FR-07, FR-11, FR-14; PF-01.01, PF-05.01, PF-05.02, PF-01.08, PF-01.09).

| Work item | Notes |
| --- | --- |
| Draft and start separation | Saving a draft creates no work; an explicit start records the run atomically and rejects duplicates. The adapted chat flow starts work on send, so this is real design work. |
| Task states and detail screen | Draft, started, plan review, running, draft ready, awaiting review, approved, exported; step timeline with replay and retry. |
| Plan review | Accept, revise or cancel before drafting. |
| Artifact versions and claim review | Claims marked supported, unsupported or conflicting beside their source; edits create new versions. |
| Exact-version approval | Approval binds to one version or one action payload; changed arguments need fresh approval; approval never overrides a policy block. |
| External-write approvals | Every first-release external write requires bound approval and an idempotency key. |
| Inbox and notifications | One list of items to act on; alerts carry no source text; access rechecked on open. |
| Export | Separate action with a fresh access check; includes the citation list. |
| Recovery | Worker restart and retry without repeating completed external actions. |

**Exit evidence:** the cross-feature acceptance example in the feature specification passes; restart, duplicate-start and revocation tests pass.

**Dependencies:** A5 for real evidence; a durable execution choice (extend the adapted background workers or add an EvolvXSI-owned executor). **Risks:** the adapted code was not designed around approval binding; narrow the guarantee for the pilot if it cannot be met cleanly, and record it.

## A7 — Agents, skills, packs and extension levels (planned, L)

**Goal:** a vertical can be packaged, evaluated, activated and governed (PF-02.01 to PF-02.06, PF-08.02 to PF-08.06, PF-03.02, PF-03.05).

| Work item | Notes |
| --- | --- |
| Pack manifest and registry | Pack, version, compatibility, agents, skills, templates, reviewer rules, declared model requirements. Define the schema in `packages/pack-sdk` and `packages/contracts`. |
| Tenant activation | Installation and access grants stay separate; activation per tenant; rollback. |
| Per-route evaluation | A pack is offered only on routes where its exact version passed (builds on A3 and A8). |
| Extension levels | Off, Request or Self-serve for connectors, skills, plugins and MCP servers; personal items visible only to their owner; plugins and MCP servers request-only. |
| Signed plugins and MCP allowlists | Reject unsigned or tampered packages; allow or block servers and tools; call log. |
| Agent and tool inventory | Admin list of every active agent, skill, connector and tool with owner, version and last run. |
| User and admin pages | Agents and Packs, Skills, Plugins, Connectors, Packs admin. |

**Exit evidence:** a sample pack installs, activates for one tenant, appears only on routes it passed, and rolls back; an unsigned plugin is rejected; a personal skill cannot use a blocked route.

**Dependencies:** decision 0003 confirmation; the first vertical shapes the pack but the mechanism can be built on a synthetic pack.

## A8 — Real model routes, evaluation and spend (planned, L; needs model access)

**Goal:** real answers on at least one local and one cloud route, with a release gate that measures them (PF-07.02, PF-07.03, PF-09.02, PF-07.06, PF-07.05).

| Work item | Notes |
| --- | --- |
| Local route | A local inference server on customer-controlled hardware; capacity and hardware decision. |
| Cloud route | A provider account and key stored as a credential, never in the repository. |
| Gateway extraction | Move route selection, policy and usage accounting toward `services/model-gateway` behind adapters. |
| Evaluation suites | Fixed cases: citation accuracy, unsupported claims, completeness, unsafe or unauthorized actions; results bound to the exact candidate and route. |
| Publication gate | Failed or stale evidence blocks publication; unauthorized disclosure, prohibited transmission and unapproved writes block rollout whatever the score. |
| Spend controls | Quotas, rate limits and alerts per user, group and organization. |
| Fallback | Retries and fallback never leave the allowed set. |

**Exit evidence:** the same fixed suite runs on each route; a route that fails is not offered; a blocked fallback is shown to be blocked.

**Dependencies:** **you cannot currently provide model access**; this phase waits on that. Phases A4 to A7 proceed on the mock routes meanwhile. The mock returns fixed text, so it says nothing about quality, citations or speed.

## A9 — Security and trust hardening (planned, L)

**Goal:** the pilot's trust claims are backed by tests (FR-13; PF-04.03 to PF-04.07).

| Work item | Notes |
| --- | --- |
| Sensitive-data redaction | Detected and redacted before model transmission, trace storage and export; miss rate reported on a fixed set. |
| Prompt-injection and exfiltration defense | Retrieved and tool content treated as untrusted; adversarial suite shows no unapproved tool call or transmission. |
| Autonomy tiers | Read-only, draft-only, act-with-approval per agent and tool. |
| Identity | SSO, service identities, session and token policy; first-user and recovery procedures. |
| Retention and deletion | Customer-agreed periods, legal hold, export of audit records; audit pruning. |
| Secrets and keys | Dedicated secret store; customer-managed keys later (PF-10.04). |
| Review and testing | Threat model, dependency and license scan, security test of tenant isolation, revocation and approval binding. |
| Legal | Trademark and notice review; remove or replace the remaining upstream documentation links; confirm brand rules for third-party logos. |

**Exit evidence:** adversarial and redaction suites in CI; a written security review with findings closed or accepted.

## A10 — Deployment, operations and upstream upkeep (planned, L)

**Goal:** a repeatable, supportable release; upstream files were not copied, so EvolvXSI owns this.

| Work item | Notes |
| --- | --- |
| Build and run | Container or process images and run scripts for each service; the local profile is a sandbox runbook, not a deployment. |
| Production profile | Choose hosting (customer VPC, hosted, on-premises); database, cache, object storage and index topology; separate control and data planes later (PF-10.05). |
| CI | Tests, type checks, link and structure checks, license and dependency scan, build of both apps. |
| Observability | Structured events, correlation IDs, dashboards, alerts; the stored audit trail feeds this. |
| Backup and recovery | Backups, restore drill, rollback to a pinned release set. |
| Release manifest | Product commit, service and package versions, documentation commit and approval record. |
| Upstream upkeep | A rule for taking new upstream commits: fresh copy, re-run `tools/rebrand_onyx.py`, re-apply EvolvXSI modules, re-run tests; decide how often. |

**Exit evidence:** a clean-room deployment from the manifest, a restore drill and a rollback, each recorded.

**Dependencies:** hosting decision. **Risks:** the web dev server and local profile hide production issues; plan a production build early (it has not been run).

## A11 — Pilot with one vertical (planned, XL; needs customer)

**Goal:** a paid, measured pilot of one workflow for one team (PRD release gates; PF-02.02, PF-09.02, PF-09.06).

| Work item | Notes |
| --- | --- |
| Discovery | Named buyer and practitioner, workflow, baseline process, measurable pain; at least two practitioners, one workflow owner, one buyer. |
| Pack build | Domain terminology, templates, reviewer rules, tool mappings and evaluation cases, authored by the workflow owner with product help. |
| Acceptance targets | Numeric quality, latency, cost and recovery targets, suite version, sample size and release approver recorded before rollout. |
| Pilot run | Representative tasks on the chosen routes against the manual baseline. |
| Support | Owner, incident path, operator runbook, known failure modes. |
| Outcome report | Completion rate, reviewer time, corrections, cost per completed task (PF-09.06). |

**Exit evidence:** the release decision record (PRD section 10): targets met, blocking checks clear, commercial terms agreed.

## A12 — Expansion (later, XL)

Informed by pilot evidence, not scheduled: second vertical and reuse measurement (PF-02.04), self-service Studio with a visual builder (PF-01.05), automations and triggers (PF-05.03), memory controls (PF-06.04), file parsing (PF-06.03), bounded delegation and browser actions (PF-05.04, PF-05.06), mobile review (PF-01.10), developer portal, MCP server and agent-to-agent interfaces (PF-03.03, PF-08.03), customer-supplied models (PF-07.05), compliance reports (PF-04.06), billing export (PF-09.07), hybrid control and data planes (PF-10.05). A public marketplace and voice each need a separate decision and stay out of scope until then.

## Decision register (what unblocks what)

| Decision | Needed by | Who | Notes |
| --- | --- | --- | --- |
| Real model access: local server and cloud provider with key | A8 | Owner | Not available now; mock routes stand in. |
| First customer, vertical and source system | A5, A11 | Owner with discovery | Drives permission sync and the first pack. |
| Where local models run (user device or customer servers) | A8, A10 | Owner and technical lead | Decision 0002 open item. |
| Route choice per task or per workspace | A4, A8 | Owner | Decision 0002 open item. |
| Personal skills on cloud routes | A7, A9 | Owner and security | Decision 0003 open item; suggested start is local and private only. |
| Hosting target and retention periods | A9, A10 | Owner and customer | |
| Retrieval backend (re-enable the adapted index or replace) | A5 | Technical lead | |
| Durable execution approach for approvals | A6 | Technical lead | |
| Legal review of trademark, notices and brand rules | A9 | Counsel | |
| Final brand artwork and typeface | A4 | Owner and design | Current assets are placeholders. |

## Cross-cutting rules for every phase

1. **Evidence before claims:** no feature is marked done without a recorded check; sandbox results are labelled as such.
2. **Fail closed:** unknown routes, unplaceable models and missing permissions deny, never allow.
3. **Authority at every boundary:** retrieval, tool calls, approval consumption, views and exports each recheck access and policy.
4. **Keep EvolvXSI code separate** from adapted upstream files, so upstream updates stay possible.
5. **Record decisions and limits** in `docs/decisions`, `UPSTREAM.md` and `docs/REVIEW.md` as work lands; update this plan when a phase closes.
6. **No secrets in the repository;** credentials go through the credential store only.

## Mapping to the earlier plan

A0 covers the documentation part of P00. A1 and A2 replace the P01 and P02 fixture build with the adopted core, keeping the mock route as the PF-07.01 fixture. A3 delivers a slice of P03 and P08. A5 is P04, A6 is P03 and P06, A7 is P05 and P07, A8 is the live half of P02 plus P08, A9 completes P03 and part of P10, A10 is P10, A11 is P09, and A12 is P11. P11A to P11G stages remain the detailed expansion breakdown.
