# NortPole — pending work checklist

Status: Working list, updated 2026-11-14 (after the redesign stages R1–R6b and R8 and the inherited test suite work). Followed one item at a time, in the order below. The phase definitions are in the [delivery plan](NortPole_Adopted-Core-Delivery-Plan.md); what each finished piece checked and did not check is in [REVIEW](../REVIEW.md). All testing so far is sandbox-only, with stand-in models.

## Phase status

| Phase | Name | State |
| --- | --- | --- |
| A0–A3 | Direction, adopt and rebrand, run and restyle, first routing slice | Done |
| A4 | Product shell and navigation (now the redesign R1–R8) | Mostly done (translations of new pages and user Privacy/Security settings wait on you) |
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
- [~] 6. **A7, agents, skills and connectors**: direction agreed 2026-11-13: govern the core's agents, tools, skills and connectors instead of building new ones ([A7 design](NortPole_A7-Agents-Skills-Connectors-Design.md), section 11). Steps 1 (tool catalog), 2 (guides), 3 (a workflow agent, plan-then-execute, search only) and 4 (outside-tool approval with pinned definitions, change check, call log) built; and 6 (Studio, an administrator editor that publishes through the normal pack path; no manifest version 2 needed) built; the pilot connector needs your source system.
- [ ] 7. **A5 and A7 step 5, a real connector:** **Google Drive chosen** (2026-11-13; the owner has Gmail and Microsoft personal accounts, no Workspace or Microsoft 365 tenant). **Paused at the owner's request.** Plan when resumed: (a) **done 2026-11-14**: Drive permission reading and the access builder honouring it, tested on recorded Drive responses ([A5 design](NortPole_A5-Knowledge-and-Permissions-Design.md), last section); "anyone with the link" files are hidden except to the people named (the recommended default; awaiting the owner's confirmation); (b) start the sandbox search index; (c) a live test against the owner's Drive with three Gmail accounts, six shared test documents and a read-only OAuth refresh token (attached as a file, never pasted), plus approval of sandbox network access to `oauth2.googleapis.com` and `www.googleapis.com`; (d) groups cannot be tested with personal Gmail and wait for a Workspace or Microsoft 365 customer or test tenant. Open question: should "anyone with the link" files be hidden except to people named on them (recommended)?

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
- [x] 30. **Stored secrets are now sealed (found 2026-11-16, fixed the same day; decision 0008 note).** The inherited `EncryptedString` and `EncryptedJson` column types did not encrypt in this edition (`_encrypt_string` returned the text as bytes), so connector credentials, API keys, bot tokens and every other secret stored through them were readable in the database. They now seal with `ENCRYPTION_KEY_SECRET` (Fernet; a generated key or a passphrase), the API refuses to start without a key unless `NORTPOLE_ALLOW_PLAINTEXT_SECRETS=true` (local development and tests), values stored before sealing still read and are sealed by `python -m nortpole.db.rotate_encryption_key`, which also moves values to a new key. The Studio signing key and people's integration accounts are sealed too. **Correction:** the key-value store never used the encrypted column (it keeps plain JSON, plus a copy in the cache backend), so the Studio key was readable for that reason too; the key-value store holds settings and policies, not other secrets, so it is left as it is. **Still open:** the key is read from the environment, not a secret manager; a lost key means stored secrets cannot be opened (the staging guide says to keep it with backups); the rotation tool has no schedule; the dev and test setups store plain text on purpose.

**Operations (A10)**
- [ ] 25. Check the first CI runs on GitHub, make the core-test job required, add a vulnerability scan, and add a job that runs the full unit suite (to confirm the IPv6 and `torch` tests pass outside the sandbox).
- [ ] 26. Encrypted backups.
- [ ] 27. Rebuild the web image and repeat the clean-room start with it; build the API image once to confirm the new tokenizer bake step.

**Quality (A4)**
- [ ] 28. Quality tab: details of a single run, regression alerts, test history.
- [ ] 30. Cost in money per scheduled run (runs store tokens, not the model used; needs a column for the model).
- [ ] 31. Accessibility checks not yet done: screen-reader output, right-to-left layout for Arabic, 200% zoom.

**Retrieval**
- [ ] 29. Start the search index in the sandbox (retrieval is tested only in code tests so far).

**Suggested order if work continues (2026-11-14):** 7(a) Drive permission sync on recorded responses, 29 search index, 22 pack takeover gap, 25 CI checks with the full-suite job; decisions 10 (customer), 12 (cloud model) and 13 (hosting) unblock the most.

## UI and admin console redesign (agreed 2026-11-13; plan in `docs/05-design/NortPole_Redesign-Plan.md`)

- [x] R1. Sidebar order and names, Workflows and Sources tabs, Knowledge rename, redirects, read-only Skills, Connectors and Plugins.
- [x] R2. Admin console regroup, merged Approvals queue, hide inherited screens.
- [x] R3. "Run by" line on Start, Agent tab for chat assistants, Channels rename, Sources order.
- [x] R4. Discover as the first Sources tab, with requests landing in Approvals.
- [x] R5. Inbox filters.
- [ ] R6. Scheduled workflows (design in `docs/05-design/NortPole_Workflows-and-Knowledge-Design.md`): R6a runner and rules (done), R6b screens and sharing (done), R6c event triggers (after the connector). Follow-up: per-run cost in money (runs store tokens, not the model used).
- [ ] R7. Knowledge (same design): R7a domains, R7b My files and requests, R7c verification and freshness (after the search index and the Google Drive connector).
- [x] R8. Quality pass for R1–R6: 24 pages in light and dark at 1280 and 390 pixels (96 runs, all clean) and a keyboard pass. Repeat for R7.

## Inherited test suite (2026-11-14)

- [x] Fixed: neutral governance settings for unit tests, missing fixtures and test helpers, monorepo paths, the route contract (with three GET handlers that wrote), files the upstream copy dropped (Craft agent templates, dev scripts, test helpers), tests pointed at NortPole's own deployment, and tokenizers baked into the API image.
- Not a gap (checked 2026-11-14): Box web links. A failing test suggested they had no access list, but that test switches on Enterprise mode; in the community edition every Box document takes the source's own access setting.
- Sandbox-only (pass on a normal machine): IPv6 `::1` binding in the sandbox proxy tests, DNS for `example.com`, the model server needs `torch`, and one Hugging Face download host blocked (the Docker image bake was therefore not run here).

## Known issues (saved 2026-11-13)

- The local 7B model obeyed hostile text in 31% of injection tests; guides' effect on a real model is not measured.
- No real document source has been connected; retrieval, agent search results and connectors are tested only in code tests.
- Tools that are switched on still run in chat with no approval step; web tools can carry text out in a web address.
- Not tried live: an MCP server (the safety system blocked turning off the SSRF check), a real OpenAPI tool, the Slack bot path.
- The web unit tests cannot run as configured (the Jest setup file `tests/setup/jest.setup.ts` is missing); they run with a scratch config that skips it, and the same gap leaves 372 type errors in test files, so CI type-checks app code only (`tsconfig.app.json`).
- The web app's `dev`, `build` and `lint` scripts call files in an `apps/workspace/tools/` folder that was never copied (PDF asset preparation, the type-check wrapper, an i18n lint plugin). The Dockerfile and `make` targets call Next.js and `tsc` directly; restore or replace those scripts.
- Sandbox services stopping: the database stops were caused by the sandbox restart script deleting a running Postgres's lock file (fixed 2026-11-14 in the sandbox scripts, which are not in the repository); the local model container and the API still stop after session restarts, so test runs check them first.
- Sandbox leftovers (test accounts, demo packs) are listed in `docs/REVIEW.md`.
- All testing is sandbox-only, with the local 7B model or stand-in models.

## Repository structure (decision 0006, 2026-11-14)

- [x] Phase 1: placeholders removed, `modules.json` true, structure check updated, `CODEOWNERS`, `Makefile`, CI for the web app and a nightly full suite.
- [x] Phase 2: NortPole modules grouped by domain in `services/core/nortpole`, with an import-boundary test.
- [x] Phase 3: first-party packs as source in `packs/horizontal` and `packs/vertical/<industry>`, editions.
- [x] Phase 4: generated contracts in `packages/contracts` and `packages/pack-sdk`.
- [ ] Phase 5 (when needed): tenancy decision, Kubernetes and cloud profiles, service splits, connector SDK.
- [x] Pack signatures re-checkable from the database (done 2026-11-14): each version keeps its exact signed bytes (`signed_manifest`, migration `a1c3e5f7b9d2`) and `GET /admin/packs/verify` re-checks digest, signature and content. Versions installed earlier whose bytes could not be recovered are reported as unverifiable until the same signed package is uploaded again.
- [ ] Packs admin page: show the integrity check's result and the "signed bytes kept" flag (the API is built; the screen is not).

## Product name (decision 0007, 2026-11-14)

- [x] Step 1: the visible name is NortPole (app, notifications, skill text, README, documents, screenshots).
- [x] Step 2: code names (package, settings, identifiers, documents).
- [x] Step 3: stored and shared names, and the repository name (owner).
- [ ] Before launch: trademark search for NortPole (software, classes 9 and 42) and the `.com` and `.ai` domains.

## Waiting for the owner's yes

- [ ] 8. **Agents in the UI:** a hint on the agents page that agents answer in chat only; check "Turn into a draft" in an agent chat; list custom agents with their route and data class in the admin Inventory.
- [ ] 9. **Horizontal and vertical packs:** the repository side is done (decision 0006 phase 3): packs live in `packs/horizontal/` and `packs/vertical/<industry>/`, bundled by `packs/editions/`, validated and signed with the pack SDK. Still waiting for your yes: letting a vertical pack *use* a horizontal pack at run time (dependency checks before activation); a partial patch for that is kept outside the repository.

## Blocked on the owner or outside the sandbox

- [ ] 10. Customer and vertical (unblocks A11).
- [ ] 11. Google Drive test setup for the real connector (unblocks A5, R6c and R7): Gmail test accounts with shared test documents, a read-only OAuth refresh token attached as a file, approval of network access to Google's API hosts. "Anyone with the link" files: built as hidden except to people named on them (the recommended default); confirm or change.
- [ ] 12. Cloud model (unblocks the live part of A8).
- [ ] 13. Hosting target (A10 depends on it).
- [ ] 14. Real retention periods (365 days is a placeholder).
- [ ] 15. Trademark and legal licence review.
- [ ] 16. Identity decisions (sign-in provider, MFA), needed for the user Security settings.

## Done recently

UI plan U1–U5 (sidebar order and names, Workflows page, admin regroup, admin Overview, home cards and "Turn into a draft"); renames Chats to Recents and Tasks to Drafts ("New" kept).
