# EvolvXSI — delivery plan on the adopted core

Status: **proposed; supersedes the sequencing (not the scope) of the fixture-first plan** · Updated: 2026-11-11

This plan rebuilds the delivery sequence around [decision 0004](../decisions/0004-adopt-community-source-as-pilot-core.md): the pilot runs on adapted Onyx Community Edition source in `services/core` and `apps/workspace`, with EvolvXSI-owned governance added in separate modules. The earlier [P00–P11 plan](EvolvXSI_Implementation-Phases.md) stays valid as the scope reference and the source of acceptance wording; this document records what is actually done and the order of what remains. It commits no dates, no staffing and no customer.

How to read it: **Done** means verified in a sandbox on 2026-11-10 (not production). **Sizes** are relative (S, M, L, XL), not time estimates. **PF IDs** refer to the [feature catalog](../04-specs/EvolvXSI_Feature-Spec.md#full-platform-feature-catalog). Every phase ends with evidence a reviewer can check.

## Phase summary

Status as of 2026-11-12, from what is built and tested in the sandbox only (see `docs/REVIEW.md`).

| Phase | Name | Status | Size | Old plan |
| --- | --- | --- | --- | --- |
| A0 | Direction, documents and designs | Done | M | P00 (partly) |
| A1 | Adopt and rebrand the core | Done | L | New |
| A2 | Run, verify and restyle | Done | L | P01–P02 (partly) |
| A3 | Hybrid routing and governance first slice | Done | M | P03, P08 (slice) |
| A4 | Product shell and navigation | Mostly done (Settings and admin audited against the spec with gaps recorded; interface quality pass on ten pages; translations of the new pages, Privacy and Security settings, an admin Overview and Quality tab open) | M | P06 (UI) |
| A5 | Knowledge, evidence and permissions | Built for one path (no real connector; synthetic corpus) | XL | P04 |
| A6 | Reviewed task workflow and approvals | Built (web and email destinations; Craft set aside) | XL | P03, P06 |
| A7 | Agents, skills, packs and extension levels | Partly built (signed packs and evaluation gating; no pack agents, skills or connectors) | L | P05, P07 |
| A8 | Real model routes, evaluation and spend | Started (local 7B and embeddings; request counts by route; no cloud model, no token or cost tracking); needs model access | L | P02 live, P08 |
| A9 | Security and trust hardening | Partly built (address safety, endpoint checks, audit log with a hash chain, redaction, autonomy tiers, retention and export, injection suite, threat model and scans) | L | P03, P10 |
| A10 | Deployment, operations and upstream upkeep | Started (API and web images, nginx entry point, and a retrieval overlay (OpenSearch, workers) checked in the sandbox; a TLS overlay, backup and restore with a drill, version pinning and a release manifest checked in the sandbox; no registry, CI, log shipping or clean-room deployment) | L | P10 |
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

**Progress (2026-11-11):** Libraries and Inbox pages and sidebar entries exist. Libraries lists the backend's document sets and otherwise states plainly that sources cannot be connected without a retrieval index. The Inbox groups notifications into Needs action (approval types), Updates and Resolved, with a working Dismiss. A Models settings tab (default route, routes you can use) is in, and the home screen applies the saved default route; the browser-stored preference is a stopgap until a server-side user preference exists. Theme selection (Light, Dark, System) already sits in the existing General settings tab. Still to do in A4: Automations, Apps and Packs, My Files, the composer strip with Project and Workflow chips, a Notifications settings tab (needs a backend preference), the dark and narrow-width pass, fonts and translations.

**Exit evidence:** every sidebar entry opens a real page; screenshot set in light, dark and narrow widths; keyboard-only path through the home, chat and settings screens.

**Dependencies:** none external. **Risks:** many upstream files touched; keep changes in separate components and styles where possible.

## Direction note, 2026-11-11

[Decision 0005](../decisions/0005-north-plus-pokee-unified-direction.md) (accepted 2026-11-12) makes the product a governed workspace with action agents on top. It raises the weight of A6 (approval-gated actions) and A7 (connectors as actions) and changes no phase scope. It rests on Pokee's own marketing page, not on anything we measured.

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

**Progress and finding (2026-11-11):** the adopted core already has an action-approval system for sandbox tasks (`server/features/build/approvals`, `db/action_approval.py`): a stored payload, a race-safe decision, a wait timeout and a list of live approvals. It has no payload fingerprint, no idempotency key, and it offers "approve for the whole session", which conflicts with our one-action rule. A6 should extend this system rather than add a second one, and decide whether session-wide grants are switched off for governed packs. The binding rules now exist as pure, tested functions in `services/core/evolvxsi/action_binding/binding.py` (exact action, payload and target fingerprint; policy block beats approval; expiry; single use; one idempotency key per approved action). Wiring, same day: "approve for the whole session" is now off by default (`EVOLVXSI_APPROVAL_SESSION_GRANTS=true` turns it back on); the approval screen hides the button and the API refuses the choice. Every decision writes an audit record with the action fingerprint and no payload text (`approval.decision`). Still not wired: the held sandbox request is forwarded as held, so exact-payload binding is already inherent there; the binding functions are for actions that run outside that proxy path, which do not exist yet. The Inbox now lists the person's own pending approvals (screen checked against a mocked endpoint). Nothing ran against a live sandbox: Craft cannot start in lite mode (it needs the vector database and background workers), so testing real approvals and Automations needs a full deployment profile (see A10).

**Progress (2026-11-12), task flow slice 1 (backend):** reviewed tasks now exist as their own record (`services/core/evolvxsi/tasks/`, table `evolvxsi_task`, migration `c4d2e8a91f07`). Saving a draft creates no work. An explicit start moves the draft to planning in one conditional update keyed on owner, state and version, so a second click or an old tab is refused. A plan of 3 to 8 numbered steps is then drafted by the default model through the route policy (a blocked route fails the plan before anything is sent). The owner accepts, sends it back to an editable draft with a note, or cancels. Every write names the version it was based on; others cannot see or change the task; start, accept and cancel are audited without task text. Checked: 12 unit tests and 8 database tests, including the real planner calling the mock route (which returns a labelled three-step fixture plan for planning prompts). Since then (same day): the Reviewed tasks screen; running an accepted plan (evidence gathered with the owner's access, cited draft through the route policy, citations to sources the run did not have removed); approval bound to the exact draft by fingerprint; export as Markdown after a fresh access check that withholds the export if any cited source is no longer open. Claim review followed: each sentence is supported (cites a source the run had) or unsupported, and approval waits until the owner keeps (labelled in the export) or removes every unsupported one. Draft editing followed: an edit becomes a new numbered version, earlier versions stay readable, edits may cite only the run's sources, and decisions carry over only to unchanged sentences. Not built yet: conflict detection between sources, external-write actions, background execution and restart recovery.

**Exit evidence:** the cross-feature acceptance example in the feature specification passes; restart, duplicate-start and revocation tests pass.

**Dependencies:** A5 for real evidence; a durable execution choice (extend the adapted background workers or add an EvolvXSI-owned executor). **Risks:** the adapted code was not designed around approval binding; narrow the guarantee for the pilot if it cannot be met cleanly, and record it.

**Craft assessed and set aside (2026-11-12).** With the full stack running, Craft's sandbox still cannot start here: its image name (`evolvxsidotapp/sandbox`) exists on no registry (the rebrand renamed it and upstream's Dockerfile was left out of the copy), building one means adopting upstream deployment pieces plus a coding-agent runtime that needs a strong model, and Craft is built for sandboxed coding agents, which is not the "agents acting across apps with approval" path of decision 0005. EvolvXSI builds its own action layer instead (next paragraph) and keeps the approval, policy and audit rules it already has.

**Progress (2026-11-12), first outbound action, in the sandbox** (`services/core/evolvxsi/actions/`, migration `1b8d4f6a2e93`): an owner can propose sending an *approved* draft to a target an administrator registered (a webhook). The payload is built on the server from the draft (title, Markdown with its cited sources), never typed in. Approval names the exact payload fingerprint, is single use and expires after 30 minutes. At send time the server re-checks, from the database: the target is still enabled and allowed for the workspace's data class (policy); the owner can still open every cited source; the approval is exact, unexpired and unused. The request carries an `Idempotency-Key` that is stable for the action, so a retry after a failure or an unknown outcome reuses it. Destinations resolving to link-local, metadata, multicast, unspecified or reserved addresses are refused at registration and again at send, redirects are not followed, and the response body is not stored. Propose, approve, send, denied send and target changes are audited with the fingerprint and no draft text. Checked: 16 integration checks against a local sink that records every request (sent once; retry after a 500 reused the key; policy, disabled target, lost access and expired approval each sent nothing; another user got "not found"; audit held no draft text). Not built: the screen, other target kinds (email, chat, a real connector), an owner-visible send history, a policy by target and route beyond data class, and live use against a real receiver.

## A7 — Agents, skills, packs and extension levels (planned, L)

> Progress 2026-11-12: signed packs, install/activate/rollback, revocation and requirement checks are built, and a pack's evaluation cases must pass on the model in use before it runs (see REVIEW.md). Template house style (text guidance) is built; pack-supplied agents, tools and connectors are not.

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

**Progress (2026-11-13), first slice of vertical packs** (`services/core/evolvxsi/packs/`, migration `2c9e5a7b3f14`): a pack is a strict manifest (unknown fields refused, sizes capped, slug ids, semantic versions) of task templates plus what it requires: the data classes it supports and the model route kinds (local, private, cloud) it may run on, optionally requested permissions and evaluation cases (declared, not yet run). It is signed with Ed25519 over the canonical manifest bytes. An administrator registers trusted signer keys; a package installs only when its signer is trusted and not revoked, the signature matches the exact manifest and the manifest is valid; the reason is stated and a refusal is audited. Installing does not activate; one version of a pack is active at a time, so activating a newer version is an upgrade and an older one a rollback. People see the active packs and can start a **draft** from a template (nothing runs until Start); the task records the exact pack version, so later upgrades and rollbacks never change a past run. A task started from a pack starts and runs only if the workspace's data class and the model route in use are both listed in that version's requirements, and the signer is still trusted; otherwise it is refused before any model call and audited. Revoking a signer flags its packs for administrators, stops offering them to people, and blocks activating or running them. Requested permissions are shown and grant nothing. A signing tool (`services/core/scripts/sign_pack.py`) and a sample pack are included. Checked: 13 unit tests (manifest limits, canonical form, signatures) and 10 database tests (install, tamper, unknown signer, invalid manifest, duplicate version, upgrade and rollback keeping past tasks on their version, revocation, route and data-class refusal), plus admin-only checks on the new endpoints; and a browser run (tampered package refused, install, upgrade, rollback, a person using a template and landing on the draft, revocation hiding the pack). Not built: evaluation per route (`evaluation_cases` are not run, so a route is not yet "offered only after the version passes on it"), compatibility checks between versions, per-tenant activation, partner publishing, pack-supplied agents, skills, connectors or reviewer rules (only task templates and requirements exist), and a key-rotation flow.

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

**Progress (2026-11-12), first A9 slice: source text is data.** Passages from sources may carry text aimed at the model. Controls that hold whatever the model does (`services/core/evolvxsi/tasks/untrusted.py`):

- A passage cannot mint citations (`[3]` becomes `(3)`) or start a fake source or prompt section (line breaks collapsed; delimiter look-alikes defused). Each source is one line between `<<source n>>` and `<<source>>`.
- The drafting prompt says text inside a source is data, never an instruction.
- Planning and drafting requests carry no tools, so source text cannot trigger an action.
- Plan steps are capped at 300 characters; output citations are kept only for sources the run had.

Checked: unit tests for each control, and a run with a hostile passage (asks to cite [9] and fakes a second source) through the real drafter and mock route produced a draft with only the real source and no injected citations. The mock model does not try to obey injected text, so this shows the structural controls hold, not that a real model resists instructions; that needs testing against real models (A8).

**Progress (2026-11-12), second A9 slice: endpoint access and audit privacy** (`services/core/tests/evolvxsi_integration/test_endpoint_security.py`, against the running API with one throwaway user): 16 EvolvXSI endpoints (tasks, preferences, route policy, access groups, source groups, pending approvals) refuse signed-out requests; a signed-in ordinary user is refused (403) on the five admin endpoints but can use their own tasks and preferences; another person's task answers 404, the same as a missing one; and after creating and cancelling a task with a distinctive title and request, no audit row holds that text. 25 checks pass, run twice. Limits: this covers the endpoints we added, not the whole upstream API; an administrator role was not probed in this file; sign-in used basic auth only (no SSO).

**Progress (2026-11-12), third A9 slice: the action layer's destination checks hold at connection time.** The first version checked where a destination pointed and then let the HTTP library look the name up again when it connected, so a name that answered safely once and a metadata address the second time would have passed the check and reached the metadata address (DNS rebinding). Now (`services/core/evolvxsi/actions/delivery.py`): the name is looked up once, every address it returns must be allowed (a name that also points somewhere forbidden is refused), and the connection is pinned to the checked address while the real host name is kept for the `Host` header and for TLS certificate and SNI checks; IPv4-mapped IPv6 forms of forbidden addresses (`::ffff:169.254.169.254`), link-local, multicast, unspecified and reserved addresses are refused; user names or passwords in the address are refused; proxy settings in the environment are ignored so a proxy variable cannot reroute a send; redirects are still not followed. Checked with 17 unit tests, including a resolver that answers with a safe address once and the metadata address afterwards (the send reaches the checked address, with the real `Host` header, after exactly one lookup), an environment proxy that must be ignored, and a 307 whose target must never be contacted; 116 integration checks still pass. Limits: private (RFC 1918) addresses are allowed on purpose, since an administrator may register an internal receiver; the HTTPS pinning was checked by inspecting the adapter's settings, not against a live TLS server with a bad certificate; there is no per-destination rate limit or maximum payload beyond the draft length limit.

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
