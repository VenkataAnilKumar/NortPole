# EvolvXSI — open decisions

Status: for the product owner to answer · Updated: 2026-11-12

What is built so far (the workspace, route policy, group-based access, reviewed tasks from draft to export, first security checks) was verified only in a sandbox with mock model routes and synthetic documents. The items below are what the rest of the delivery plan waits on. Each has a recommendation, the reason, and what it unblocks. A recommendation is a suggestion, not a decision.

| # | Decision | Recommendation | Why | Unblocks |
| --- | --- | --- | --- | --- |
| 1 | First source system | One shared-document source your pilot team already uses (for example a shared drive or a wiki), chosen with the first customer | Permission rules differ by source, so the first connector fixes what permission sync must do; choosing without the customer risks rework | A5 connector and permission sync; a realistic cited-answer test |
| 2 | Real model access | One local or private route and one cloud route, even small ones, plus API access for evaluation | Hybrid routing, real draft quality and prompt-injection resistance can only be judged on real models; today every result comes from a labelled mock | A8; the remaining A9 injection testing; draft quality |
| 3 | Embedding model | Allow the model host used by the core's default embedding model, or name an alternative you can supply | Search quality cannot be measured with the test vectors used in the sandbox | Search quality tests; a real retrieval pilot |
| 4 | Test deployment host | One small managed or customer-cloud environment (index, workers, database) that EvolvXSI can deploy to | Real approvals, Automations, the access re-sync job and the source-id backfill need workers and an index, which the sandbox cannot run together | Live approvals (A6), A10, end-to-end pilot rehearsal |
| 5 | Where local models run | Decide with decision 4: on the customer's own hardware for the pilot if the data class requires it | The route policy already separates local, private and cloud; the pilot needs at least one route that keeps restricted data in the customer's boundary | Meaningful route-policy demo on real data |
| 6 | First customer and vertical | One regulated team with a repeatable, document-heavy workflow and a named approver | The reviewed-task flow (plan, cited draft, approval, export) fits work that needs sign-off; the vertical decides the first pack | A7 first pack; A11 pilot |
| 7 | Retention and hosting rules | Keep task drafts and audit records for a fixed period set with the customer; audit never stores task or document text (already enforced) | Needed before real data is used | A10, A11 agreements |
| 8 | Trademark review of the EvolvXSI name | Start a clearance search before any external use | Cheap now, expensive after launch | Public launch |
| 9 | "Approve for the whole session" for sandbox actions | Keep it off for governed packs (the current default) | It lets later, different actions through without review | A6 live approvals |

## How to answer

Reply with the decision number and your choice. A one-line answer is enough, for example "1: Google Drive; 6: a compliance team". Where you do not yet know, say so; items 4 and 2 are the ones that most change what can be built next.

## What can still progress without answers

- More tests and small screens in the sandbox (audit-log view for admins, tests of the upstream API's most exposed routes).
- Documentation and the pack format design (A7), without a customer.
- Keeping the sandbox work merged and green.

None of these changes the main risk: until real models, a real source and a real deployment exist, quality and security claims stay unproven.
