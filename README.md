# EvolvXSI

**The governed AI workspace for teams that cannot afford a wrong answer.**

EvolvXSI lets people ask questions and run multi-step work over their company's own knowledge — policies, contracts, files in their drives — and get cited answers and drafts back. Every step is governed: you approve the plan before work runs, you approve the exact draft before anything leaves, the system only reads what each person is allowed to open, and every action lands in a tamper-evident audit log.

> **Status: pilot preview.** The product runs end to end and is tested in a sandbox with local models. We are looking for **design partners** — one team, one workflow — for a first pilot. See [Work with us](#work-with-us).

![The EvolvXSI AI workspace: ask a question or start a ready-made workflow, choose where it runs, and find your Inbox, Search, Workflows, Knowledge, Sources and agents in one place](docs/assets/readme/workspace.png)

---

## The AI workspace

One place to ask, search and get work done over your company's knowledge:

| In the workspace | What it does |
|---|---|
| **New** | Ask a question or start a ready-made workflow (*Cited brief*, *Find the policy*, *Compare two documents*). Attach files and choose which knowledge to use. |
| **Run on** | Choose where the work runs (local, private or cloud model), within what the administrator's route policy allows. A blocked route is shown with the reason and is never used. |
| **Inbox** | Plans waiting for your yes, drafts ready to review, and updates on your requests. |
| **Search** | One search over company knowledge, showing only what you may open. |
| **Workflows** | Start versioned workflows from signed packs, keep them on a schedule, and find your drafts. |
| **Knowledge** and **Sources** | What the workspace knows, which systems are connected, and what you can ask to have switched on. |
| **Agents** and **Projects** | Chat assistants with the knowledge and tools they may use, and folders for related work. |
| **Admin Panel** | For administrators: approvals, route policy, packs, tools, people, audit and quality. |

## Core features

| | Feature | What you get |
|---|---|---|
| **Trust** | Cited answers | Every statement links to the passage it came from; unsupported sentences are flagged, and a draft with nothing to cite says so instead of guessing. |
| | Permission-aware knowledge | Answers only use documents each person may open in the source system; Google Drive sharing is applied per document. |
| | Audit log | A hash-chained, tamper-evident record of refusals, approvals, sends, policy changes and exports, with integrity checks, a savable head, and export. |
| **Control** | Route policy and redaction | Mark each model as local, private or cloud, decide which class of data may go where, and redact sensitive patterns before the cloud. Blocked requests fail before anything is sent. |
| | Approvals | Accept the plan before work runs and approve one exact draft before anything leaves; optional second approver for sends and two-administrator rules for sensitive changes, all in one queue. |
| | Tool governance | A catalog of what assistants may use; outside tools (MCP, OpenAPI) stay off until approved, with pinned definitions that stop the tool if they change. |
| | Retention and legal hold | Set how long records are kept and hold them when needed. |
| **Work** | Governed workflows | Ready-made, versioned workflows: plan, gather sources, cited draft, review rules, approve, export or send. |
| | Signed packs and Studio | Workflows ship as signed packs that run only on models they passed evaluation on; administrators build their own in Studio. |
| | Workflow agents | Agents plan their searches first, run as you over the sources you can open, and can never send anything. |
| | Scheduled workflows | Recurring runs prepare the plan and wait in your Inbox; nothing continues without your yes, and a schedule pauses itself if plans go unaccepted. |
| | Inbox and Discover | One place for plans to approve, drafts to review and updates; see what connectors, skills and tools exist and request them. |
| **Insight** | Quality and cost | Draft and approval rates, unsupported-claim share, evaluation results per model, scheduled runs, and tokens and estimated cost per route. |

## Why EvolvXSI

Most AI assistants are built to be helpful first and safe second. In finance, legal, HR, compliance and operations that order is backwards: an invented answer, a leaked document or an unreviewed email costs more than the time AI saves.

EvolvXSI starts from the other end:

| You need | EvolvXSI gives you |
|---|---|
| Answers you can check | Every statement cites the passage it came from; unsupported sentences are flagged, and a draft with nothing to cite says so instead of guessing. |
| People to stay in charge | A plan you accept before work runs, and approval of one exact draft before anything is sent — with an optional second approver. |
| Data to stay where it belongs | A route policy decides which model (local, private or cloud) may see which class of data, and redacts sensitive patterns before anything goes to the cloud. |
| Answers to respect access | The system only reads what each person may open in the source system (Google Drive sharing is applied per document; the live Drive pilot is next). |
| Proof for auditors | A hash-chained audit log of refusals, approvals, sends, policy changes and exports, with integrity checks and export. |

## What people can do

- **Ask, with sources.** Chat over company knowledge; answers cite what they used.
- **Run a workflow.** Pick a ready-made workflow (a cited brief, find the policy that covers a question, compare two documents), review the plan, get a cited draft, approve it, export or send it.
- **Let an agent prepare the work.** Workflow agents plan their searches first and run only what you accept — as you, over the sources you can open, and they can never send anything.
- **Put work on a schedule.** A weekly check runs on its own, prepares the plan, and waits in your Inbox. Nothing runs further without your yes, and a schedule pauses itself if its plans keep going unaccepted.
- **Keep track in one Inbox.** *To approve*, *To review* and *Updates* — plans waiting for you, drafts ready to check, decisions on your requests.
- **Discover and request.** See which connectors, skills and tools exist but are not switched on, and ask for them. An administrator decides.

![Start a workflow: ready-made, versioned workflows grouped in packs](docs/assets/readme/workflows.png)

![A draft under review: the agent's plan, the draft, and a review rule that blocks approval until a source is cited](docs/assets/readme/draft-review.png)

## What administrators control

- **Model routes and data classes.** Mark each model as local, private or cloud; decide which data may go where; turn on redaction per route. A blocked request fails before anything is sent.
- **Signed workflow packs.** Workflows ship as signed, versioned packs that run only on models they passed evaluation on, with review rules and house style built in. A Studio form lets administrators build their own.
- **Tools and outside systems.** A tool catalog decides what chat assistants may use; outside tools (MCP, OpenAPI) are off until approved, their definition is pinned, and a changed definition stops the tool until approved again.
- **Approvals in one place.** Sends that need a second approver, changes that need a second administrator, requests from people, tool definitions.
- **Scheduling, retention and audit.** Who may schedule; how long records are kept and a legal hold; audit-log integrity checks, a head you can save off the machine and compare later, and export.
- **Quality and cost.** Draft and approval rates, unsupported-claim share, evaluation results per model, scheduled-run counts, and tokens and estimated cost per route.

![Route policy: which model routes may process which data, and redaction before the cloud](docs/assets/readme/route-policy.png)

## How it works

```mermaid
flowchart LR
    P[Person] -->|asks or starts a workflow| W[EvolvXSI workspace]
    W -->|plan| P
    P -->|accepts the plan| W
    W -->|searches as that person| K[(Company knowledge<br/>permission-aware)]
    W -->|route policy and redaction| M{{Model routes<br/>local · private · cloud}}
    W -->|cited draft + review rules| P
    P -->|approves the exact draft| S[Export or send<br/>to an approved destination]
    W -.->|every step| A[(Hash-chained audit log)]
```

1. **Request.** A question, a workflow from a signed pack, or a scheduled run.
2. **Plan.** The model proposes the steps — drafted on a route the policy allows — and you accept or revise it.
3. **Gather.** Searches run as you, over the sources you may open.
4. **Draft.** A cited draft is checked against the pack's review rules; unsupported claims are flagged.
5. **Approve.** You approve one exact version; sending to an outside system can require a second person.
6. **Record.** Each step is written to the audit log.

![Inbox: plans waiting for your yes, drafts to review, and updates](docs/assets/readme/inbox.png)

## Built for your environment

- **Self-hosted.** Docker Compose profile with TLS, backup and restore, version pinning and a release manifest ([staging profile](infrastructure/profiles/staging/README.md)).
- **Your models.** Run local models (for example through Ollama) for sensitive data and add private or cloud routes as policy allows.
- **Your knowledge.** Connectors bring company documents into search with their access rules; Google Drive permission sync is built, and more sources follow per customer.
- **Accessible.** Light and dark themes, phone-width layouts and keyboard navigation, checked against WCAG 2.1 AA with axe.

## Status and roadmap

**Built and tested (sandbox, local models):** workspace and admin console, reviewed workflows with plans and approvals, workflow agents, scheduled workflows, signed packs and Studio, route policy and redaction, tool catalog and outside-tool approval, second approver and two-administrator rules, audit log with integrity checks, retention and legal hold, Discover and requests, Inbox, Quality, and Google Drive permission sync.

**Next:** a live Google Drive pilot with a search index, knowledge domains (open or restricted areas with verified documents), event-triggered workflows, and hardening for a first customer deployment (identity provider and MFA, hosting, a cloud model route).

**Not yet:** a production deployment, single sign-on, and a third-party security review. All results so far come from sandbox testing.

The full, honest list lives in the [pending-work checklist](docs/07-implementation/EvolvXSI_Pending-Work-Checklist.md), and what each piece checked is in the [review log](docs/REVIEW.md).

## Work with us

We are looking for a **design partner**: a team with one high-stakes, document-heavy workflow — policy questions, contract review, audit evidence, compliance checks — that would pilot EvolvXSI on its own documents and models.

To talk about a pilot, email [vanilkumarch@gmail.com](mailto:vanilkumarch@gmail.com).

## For developers

| Part | Where |
|---|---|
| API and core services (Python, FastAPI) | [services/core](services/core) |
| Web workspace (Next.js) | [apps/workspace](apps/workspace) |
| Workflow packs | [packs](packs) |
| Deployment profiles | [infrastructure/profiles](infrastructure/profiles) |
| Product and architecture documents | [Document index](docs/README.md), [Product definition](docs/02-product/EvolvXSI_Product-Definition.md), [System architecture](docs/06-technical/EvolvXSI_System-Architecture.md) |

Run `python tools/validate_structure.py` to check the repository layout and document links.
