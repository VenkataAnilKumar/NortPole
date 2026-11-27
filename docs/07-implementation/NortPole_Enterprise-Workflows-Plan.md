# NortPole enterprise workflows

## Research

| Platform | Publicly documented behavior | NortPole decision |
| --- | --- | --- |
| Glean | Published agents can run from chat, forms, content changes, or schedules. Users can save inputs, select Run now and see past scheduled runs in Chat. A background run that needs manual tool confirmation sends an email. [Triggers](https://docs.glean.com/agents/concepts/triggers) · [Schedule triggers](https://docs.glean.com/agents/concepts/schedule-triggers) | Let a user schedule the same workflow they can run manually. Keep recurring inputs visible and use Inbox for approvals. |
| Cohere North | Teams can design, deploy and share agent-powered workflows tailored to their tools and processes. The public overview gives limited detail on scheduler and run-history behavior. [North](https://cohere.com/north) | Let agents and teams reuse workflow definitions through approved packs. |
| Hebbia | Matrix structures document-heavy work into comparable inputs and analyses. Hebbia describes continuously triggered workflows. Its public materials give limited detail on schedule controls and run history. [Matrix](https://www.hebbia.com/matrix) · [Product](https://www.hebbia.com/product) | Give each vertical workflow a useful result format with evidence linked to the items under review. |
| WRITER | Teams can author multi-step Playbooks in natural language. Admins can scope, reassign and disable them. The application API documents background jobs and retry for a failed job. [Control Center](https://writer.com/product/control-center/) · [Job retry](https://dev.writer.com/api-reference/application-api/post-retry-async-job) | Start authoring from natural language in Chat. Add durable run IDs and explicit failed-run retries before widening unattended automation. |
| Microsoft Copilot Studio and Power Automate | Event triggers, scheduled cloud flows, and a wait-for-approval step with responses in email or the approvals center. [Event triggers](https://learn.microsoft.com/en-us/microsoft-copilot-studio/authoring-triggers-about) · [Scheduled flows](https://learn.microsoft.com/en-us/power-automate/run-scheduled-tasks) · [Approvals](https://learn.microsoft.com/en-us/power-automate/modern-approvals) | Use one trigger model for manual, timed and future source events. Make approval a visible run state. |

## Requirements

- People can create schedules from Workflows or Chat, schedule a pack workflow, repeat a draft, or copy a workflow shared with their group. A copy runs with its owner's permissions.
- The schedule editor shows the task, sources when applicable, time zone, cadence, next occurrence and notification settings. Create and run now saves the schedule first. Run now on an existing active schedule leaves its recurrence in place.
- History shows outcomes and reasons, with links to the exact draft or result. Approval requests and eligible status updates go to Inbox.
- A run uses the owner's current source, integration, and model access. General workflows prepare a plan for approval. A configured Expense Review can produce a private result. External actions follow the existing approval rules.
- Agents can propose a new schedule or a run of a named schedule. The user can inspect the exact request and confirm it. A confirmation is scoped to a user, tenant, operation and input snapshot. Running an existing schedule also requires its current version.
- Before enabling event triggers or agent confirmations, persist run origin, workflow and input versions, initiator, and a replay-safe request identifier. Distinguish repeat runs with current inputs from retries of a particular failed run.

## Design and architecture

**Workflows** is the management surface. Scheduled shows cadence, status, next run, Run now, and History. History opens the draft or private Chat result. Inbox carries approval requests and notification links. Chat's plus menu opens the same New schedule form through Workflows.

For natural-language scheduling, show a Chat confirmation card with the workflow, request, schedule, time zone, next occurrence, inputs, and approval behavior. For a run request, resolve the schedule from the user's own schedules, disambiguate identical names, and show Run now with its scope before submission. Unavailable sources and tenant policies surface errors in the same flow.

Use the same scheduler for horizontal and vertical packs. Packs supply input schemas, review rules, and output formats. The workflow service owns authorization, recurrence, run records and approvals. Chat, Workflows and a future scoped agent tool call that service with the signed-in user's identity. The agent tool should create a typed proposal. A server handler consumes the confirmation and revalidates access and versions at execution time. No agent identity inherits the schedule owner's access simply by knowing the schedule ID.

The implementation shares the existing planner, Expense Review runner, notifications and audit records. A tenant-scoped Redis lock serializes executions of each schedule. Timed runs still advance recurrence on claim. Run now uses the owner's current active schedule and uses the same plan and result handling.

## Implementation and review

1. **Implemented.** Open the schedule editor from Chat. Add owner-only Run now to Scheduled and open the resulting history entry. Reuse the same owner, model, and source checks and output links.
2. **Implemented.** Chat agents can propose a prompt-based schedule or a run of an existing active schedule. The owner sees the saved request and timing in Chat and can confirm or dismiss it. An existing schedule is resolved by exact name, with ambiguity rejected. New Expense Reviews still use the editor to select sources.
3. **Implemented for Chat proposals.** Postgres stores the request before confirmation. The workflow worker claims each confirmed request once, rechecks permissions and the schedule version, and records the schedule or run link for Chat. The periodic scheduler picks up confirmations when immediate dispatch is unavailable. Expired requests are ineligible. If a worker stops after claiming a request, Chat shows that the result is unavailable and directs the owner to Workflows to check the outcome.
4. **Implemented.** Workflows → Runs combines timer runs, Run now, confirmed Chat runs, and direct Chat reviews. Schedule runs store the trigger, schedule version, and worker start and end times. Approval progress comes from the linked draft. Earlier schedule runs stay visible with an unknown trigger. Timer runs that were queued before a worker interruption can be picked up on the next tick. A run still marked running after 30 minutes displays “Result unavailable” until an outcome is recorded.
5. **Implemented.** Runs can retry the latest scheduled planning failure when the saved workflow is still current and the failed task has no plan, draft, approval, export, or external action. A retry records one linked attempt before planning, keeps the next scheduled occurrence in place, and uses the standard plan approval. Repeating the request opens the same attempt.
6. **Implemented.** **Check outcome** reads the exact linked task or review response for an interrupted run. The run history records recovered results or the reason review is still needed. New runs link the task or reserve the exact Chat response before execution, so later messages in the same Chat cannot be mistaken for the interrupted attempt.
7. **Implemented.** Knowledge changes can trigger prompt-based workflows. Workspace scheduling policy and a separate opt-in switch control eligibility. The active index records content changes, the worker reserves one run per schedule and event, and approval remains in Inbox. The run and task retain the original library, document ID and content hash. The owner must still be able to access the triggering revision when the plan is prepared and when the approved task gathers evidence.

### Verification scope

Knowledge change triggers passed 42 backend tests, 15 workspace tests, and the workspace type check. The tests exercised PostgreSQL event capture, repeat delivery, stale revisions, pause and resume, access revocation, and retrieval scoped to the triggering document. Chromium created a watch through the live API and showed its pending approval in Runs after a test revision was stamped. The planner and approved document retrieval were stubbed in execution tests.

A later live walkthrough used a synthetic policy indexed through the ingestion API with `nomic-embed-text`. The real Celery scheduler task and the configured local `qwen2.5:1.5b` model produced an Inbox plan. Accepting and running it in Chromium produced a draft citing the original policy. Re-ingesting the same content and invoking the scheduler again kept one event and one run. A revised policy produced a second plan. Removing the owner's source access after accepting that plan blocked drafting and left the run failed with no draft or citations. The walkthrough invoked the worker directly through Celery and restored the prior scheduling controls.

Safe retries and outcome checks passed 100 backend tests, 15 workspace tests, and the workspace type check. Chromium exercised the retry and outcome-check endpoints against seeded runs with a stubbed planner. The database tests verified repeated requests during execution, schedule and owner checks, external actions that still need review, and recovery of the exact saved Expense Review response.

Unified Runs passed 35 backend tests, 15 workspace tests, and the workspace type check. Chromium verified the new page against the live API with seeded run records, including approval status, the draft link and focus on a linked run. The planner was stubbed in execution tests.

Chat scheduling passed 30 workflow and Expense Review tests, 15 workspace tests, and the workspace type check. A Chromium smoke test verified the proposal preview, confirmation, status polling and run link using stubbed schedule responses. An authenticated request to the running API reached a Celery worker through Redis and saved one schedule after two confirmation requests. Run execution was verified with a stubbed planner.

The scheduling and Expense Review suites passed 27 tests. They cover ownership, disabled scheduling, stale versions, paused schedules, a competing lock, preservation of the next occurrence after a successful manual run, and draft and history linkage. The workspace type check and eight Chat composer tests passed. A Chromium smoke test with stubbed schedule responses verified Chat menu navigation, the version sent by Run now, and the resulting history row and draft link. The integration tests used a stubbed planner for manual runs.

Existing schedule semantics can supersede an unaccepted plan or auto-pause after repeated issues, including an on-demand run. The execution lock covers overlap while its lease is held. Durable request deduplication and recovery after a worker interruption belong to the queued-run phase.
