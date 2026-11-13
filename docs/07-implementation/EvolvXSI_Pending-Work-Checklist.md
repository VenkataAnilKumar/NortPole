# EvolvXSI — pending work checklist

Status: Working list, 2026-11-13 (pending-work list below saved 2026-11-13 after the A7 steps and the Google Drive discussion). Followed one item at a time, in the order below. The phase definitions are in the [delivery plan](EvolvXSI_Adopted-Core-Delivery-Plan.md); what each finished piece checked and did not check is in [REVIEW](../REVIEW.md). All testing so far is sandbox-only, with stand-in models.

## Phase status

| Phase | Name | State |
| --- | --- | --- |
| A0–A3 | Direction, adopt and rebrand, run and restyle, first routing slice | Done |
| A4 | Product shell and navigation | Mostly done (translations and user Privacy/Security settings wait on you) |
| A5 | Knowledge, evidence, permissions | Built for one path (synthetic corpus) |
| A6 | Reviewed task workflow and approvals | Built |
| A7 | Agents, skills, packs | Mostly built (steps 1 to 4 and 6; the connector waits for the source system) |
| A8 | Real model routes, evaluation, spend | Started |
| A9 | Security and trust hardening | Partly built |
| A10 | Deployment and operations | Started |
| A11 | Pilot with one vertical | Planned, needs a customer |
| A12 | Expansion | Later |

## Order of work (no decision needed from the owner)

- [x] 1. **U6, UI quality pass** (done 2026-11-13) on changed screens: home cards, "Turn into a draft", Drafts, Recents, Workflows, admin Overview. Light and dark, 1280 and 390 wide, axe at 0 violations, keyboard.
- [x] 2. **A4 wording pass** (done 2026-11-13): the visible "task" wording on Drafts, Workflows and the Packs admin page now says draft or workflow; the home message box placeholder reads "Ask a question or type / for more". The rest of the old item 2 moved out: translations of the new pages stay deferred until a customer's language is known (an earlier decision), the user Privacy and Security settings depend on the retention and identity decisions (items 14 and 16), and the admin Quality tab is item 2b.
- [x] 2b. **Admin Quality tab** (done 2026-11-13): `GET /admin/quality` and an admin Quality page with Runs, Evals, Feedback and Trends. Counts, rates and durations only. Not built: per-run diagnostics for one run, regression alerts, and evaluation by route over time (the Evals view shows the latest result per pack version and model).
- [x] 3. **A10, first slice** (done 2026-11-13, then the gaps closed the same day): TLS overlay, backup and restore with `KEEP` retention, version pinning, release manifest, upgrade and rollback runbook, a registry round trip, a clean-room start, and a restore of an older backup into a rebuilt image with the audit chain check, all in `infrastructure/profiles/staging`. Still open under A10 (3b): a vulnerability scan and the image build in CI (the workflow exists; see 5c), log shipping and dashboards, encrypted backups, a managed registry with image signing and scanning, a real certificate and its renewal, a rebuilt web image in the clean-room run, and everything that depends on the hosting target (item 13).
- [x] 4. **A8, tokens and cost per route** (done 2026-11-13): tokens and an estimated cost are counted by day, route type and model, shown on the Route policy page and at `GET /admin/route-tokens`. Not built: spend limits or budgets, cost by person or team, cost by pack or purpose, and a reconciliation against a provider invoice (the figure is an estimate from the price list).
- [x] 5. **A9, hardening that needs no decision from you** (done 2026-11-13): the off-box audit head (5), an optional second approver for sends (5b), and a software bill of materials plus a CI workflow (5c; the workflow's first two jobs were run locally, the third has not run on GitHub). Blocked on you: administrator MFA and single sign-on (identity provider), a secrets manager (hosting target), an outside review before real data; The optional two-administrator rule for route policy and retention changes is built (5d, 2026-11-13); signers, destinations and other administrator actions are not covered.
- [~] 6. **A7, agents, skills and connectors**: direction agreed 2026-11-13: govern the core's agents, tools, skills and connectors instead of building new ones ([A7 design](EvolvXSI_A7-Agents-Skills-Connectors-Design.md), section 11). Steps 1 (tool catalog), 2 (guides), 3 (a workflow agent, plan-then-execute, search only) and 4 (outside-tool approval with pinned definitions, change check, call log) built; and 6 (Studio, an administrator editor that publishes through the normal pack path; no manifest version 2 needed) built; the pilot connector needs your source system.
- [ ] 7. **A5 and A7 step 5, a real connector:** **Google Drive chosen** (2026-11-13; the owner has Gmail and Microsoft personal accounts, no Workspace or Microsoft 365 tenant). **Paused at the owner's request.** Plan when resumed: (a) build Drive permission reading and syncing in the repo, tested on recorded Google responses (needs nothing from the owner); (b) start the sandbox search index; (c) a live test against the owner's Drive with three Gmail accounts, six shared test documents and a read-only OAuth refresh token (attached as a file, never pasted), plus approval of sandbox network access to `oauth2.googleapis.com` and `www.googleapis.com`; (d) groups cannot be tested with personal Gmail and wait for a Workspace or Microsoft 365 customer or test tenant. Open question: should "anyone with the link" files be hidden except to people named on them (recommended)?

## More work that needs no decision from the owner (saved 2026-11-13)

**Agents (A7)**
- [ ] 17. An "open a document" step for workflow agents.
- [ ] 18. Let workflow agents use approved outside tools as plan steps.
- [ ] 19. A per-agent library limit, cost limit and on/off switch.
- [ ] 20. Run a pack's tests through the agent's own plan.
- [ ] 21. Studio form: edit review rules, house style and test cases.

**Security (A9)**
- [ ] 22. Close the pack takeover gap: any trusted signer can publish a new version of another signer's pack; needs a key-change flow that keeps rotation working.
- [ ] 23. A second administrator for the remaining admin actions: pack publish and activate, send destinations, tool approvals, signers.
- [ ] 24. A scheduled job that saves the audit-log head off the machine.

**Operations (A10)**
- [ ] 25. Check the first CI runs on GitHub, make the core-test job required, add a vulnerability scan.
- [ ] 26. Encrypted backups.
- [ ] 27. Rebuild the web image and repeat the clean-room start with it.

**Quality (A4)**
- [ ] 28. Quality tab: details of a single run, regression alerts, test history.

**Retrieval**
- [ ] 29. Start the search index in the sandbox (retrieval is tested only in code tests so far).

**Suggested order if work continues:** 7(a), 29, 22, 25; decisions 10, 12 and 13 unblock the most.

## UI and admin console redesign (agreed 2026-11-13; plan in `docs/05-design/EvolvXSI_Redesign-Plan.md`)

- [x] R1. Sidebar order and names, Workflows and Sources tabs, Knowledge rename, redirects, read-only Skills, Connectors and Plugins.
- [ ] R2. Admin console regroup, merged Approvals queue, hide inherited screens.
- [ ] R3. Workflows Start cleanup and the Agent tab for chat assistants only.
- [ ] R4. Request buttons on Sources, landing in Approvals.
- [ ] R5. Inbox filters.
- [ ] R6. Scheduled workflows with stop at the plan and auto-pause.
- [ ] R7. Knowledge domains and uploads (after the Google Drive connector).
- [ ] R8. Quality pass of each stage.

## Known issues (saved 2026-11-13)

- The local 7B model obeyed hostile text in 31% of injection tests; guides' effect on a real model is not measured.
- No real document source has been connected; retrieval, agent search results and connectors are tested only in code tests.
- Tools that are switched on still run in chat with no approval step; web tools can carry text out in a web address.
- Not tried live: an MCP server (the safety system blocked turning off the SSRF check), a real OpenAPI tool, the Slack bot path, CI on GitHub.
- The web unit tests cannot run in this copy (the Jest setup file is missing).
- Sandbox leftovers (test accounts, demo packs) are listed in `docs/REVIEW.md`.
- All testing is sandbox-only, with the local 7B model or stand-in models.

## Waiting for the owner's yes

- [ ] 8. **Agents in the UI:** a hint on the agents page that agents answer in chat only; check "Turn into a draft" in an agent chat; list custom agents with their route and data class in the admin Inventory.
- [ ] 9. **Horizontal and vertical packs:** plan only. Not built until approved and the open decisions are answered. Partial work is kept outside the repo.

## Blocked on the owner or outside the sandbox

- [ ] 10. Customer and vertical (unblocks A11).
- [ ] 11. Source system for the real connector (unblocks A5).
- [ ] 12. Cloud model (unblocks the live part of A8).
- [ ] 13. Hosting target (A10 depends on it).
- [ ] 14. Real retention periods (365 days is a placeholder).
- [ ] 15. Trademark and legal licence review.
- [ ] 16. Identity decisions (sign-in provider, MFA), needed for the user Security settings.

## Done recently

UI plan U1–U5 (sidebar order and names, Workflows page, admin regroup, admin Overview, home cards and "Turn into a draft"); renames Chats to Recents and Tasks to Drafts ("New" kept).
