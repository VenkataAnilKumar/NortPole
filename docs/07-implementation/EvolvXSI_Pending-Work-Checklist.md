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
- [ ] 2b. **Admin Quality tab** (Runs, Evals, Feedback, Trends; see the UI specification): a medium build. Do it after item 3 unless you want it earlier.
- [ ] 3. **A10:** TLS, backups, upgrade path, container registry.
- [ ] 4. **A8:** token and cost tracking per route (today only request counts).
- [ ] 5. **A9:** remaining hardening items (check the A4/A7/A9 plan for the exact list before starting).
- [ ] 6. **A7:** pack agents, skills and connectors (none built).
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
