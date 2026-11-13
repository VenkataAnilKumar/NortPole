# EvolvXSI — pending work checklist

Status: Working list, 2026-11-13. Followed one item at a time, in the order below. The phase definitions are in the [delivery plan](EvolvXSI_Adopted-Core-Delivery-Plan.md); what each finished piece checked and did not check is in [REVIEW](../REVIEW.md). All testing so far is sandbox-only, with stand-in models.

## Phase status

| Phase | Name | State |
| --- | --- | --- |
| A0–A3 | Direction, adopt and rebrand, run and restyle, first routing slice | Done |
| A4 | Product shell and navigation | Mostly done |
| A5 | Knowledge, evidence, permissions | Built for one path (synthetic corpus) |
| A6 | Reviewed task workflow and approvals | Built |
| A7 | Agents, skills, packs | Partly built |
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
- [~] 6. **A7, agents, skills and connectors**: direction agreed 2026-11-13: govern the core's agents, tools, skills and connectors instead of building new ones ([A7 design](EvolvXSI_A7-Agents-Skills-Connectors-Design.md), section 11). Steps 1 (tool catalog), 2 (guides), 3 (a workflow agent, plan-then-execute, search only) and 4 (outside-tool approval with pinned definitions, change check, call log) built; next step 6, an administrator editor for agent specs and manifest version 2; the pilot connector needs your source system.
- [ ] 7. **A5:** a real connector (needs the source system, item 11).

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
