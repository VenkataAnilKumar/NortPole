# NortPole Agent Catalog

Start with the work you want to do. Use **Agents** for a reusable setup with its own Knowledge and instructions, **New Chat** for a quick start, and **Workflows** for a task you want to run on a schedule or trigger. Packs tailor the same agents to teams such as Finance, HR, Support, and Operations.

## Agents in the workspace draft

Open **Agents → Agent Catalog** to find the agents available to you. The catalog opens the first populated view, checking **Company agents**, **Shared with me**, **My agents**, and **Starred** in that order. Use **Start Chat** on a card to work with that agent.

In **Agent Catalog → New Agent**, choose a template, attach Knowledge you can access, and select **Test in Chat**. A tested agent becomes available to its intended audience after an authorized publisher activates it.

| Choose | When to use it | Example request | What you get |
| --- | --- | --- | --- |
| **Research** | You have a question and want the agent to search its configured Knowledge collections. | “What changed in our supplier onboarding policy? Cite the relevant guidance.” | A briefing with findings, supporting sources, and gaps in the evidence. |
| **Document Analysis** | You know which documents to use and want to summarize or compare them. Select the documents in Chat. | “Compare the approval steps in these two policy versions.” | A summary or comparison grounded in the selected documents. |
| **Reporting** | You want a status report for a specific date range. Choose the period and accessible Knowledge sources in Chat. | “Summarize support volume, recurring issues, and unresolved escalations.” | A report with progress, metrics, blockers, next steps, and evidence gaps. |
| **Spreadsheet Analysis** | You want to check an uploaded CSV or Excel workbook. | “Analyze this spreadsheet.” | Column totals, first-to-last changes, missing values, duplicate rows, and potential outliers, with sheet and row references. |
| **Meeting Recap** | You have meeting notes or a transcript to review. | Paste the notes into Chat. | Decisions, action items, and open questions, with quotes from the notes and owners or due dates when stated. |

These templates have been tested locally with indexed Knowledge. Internal pilot enrollment is pending. **Review documents** is a proposed task label. The template in the draft is **Document Analysis**. [Delivery plan](NortPole_Horizontal-Agents-Delivery-Plan.md#research-and-document-analysis-pilots)

### Evidence Brief pack

The draft supports versioning **Evidence Research**, a read-only configuration of Research from the **Evidence Brief** pack. Once Evidence Brief 1.1.0 is signed and activated, an agent owner with permission to add agents can open **Workflows → Evidence Brief → Prepare Chat agent draft**, configure Knowledge and a model, then use **Test in Chat**. Signing and activation are pending. [Versioned pack agents](NortPole_Horizontal-Agents-Delivery-Plan.md#versioned-pack-agents-in-chat)

## Quick starts in New Chat

The draft has four common start cards across teams. **Ask company knowledge**, **Research a topic**, and **Analyze data** start a prompt. **Draft a document** opens the document builder. To create a reusable agent with its own instructions and Knowledge, use **Agent Catalog → New Agent**.

**Explore more** includes common task starters such as **Compare sources** and **Capture meeting actions**, along with workflow templates from available packs. In the catalog proposal, top-level start cards stay common across teams. Pack templates appear under **Explore more** when available.

## Agent cards

Agent cards show the agent's description and available actions and provide **Start Chat**. The card design calls for a clear input, expected output, and example in the agent details. Company verification applies to the reviewed company-listed version. [Company verification](NortPole_Horizontal-Agents-Delivery-Plan.md#company-verification)

## Additional task candidates

Group related tasks under the same agent when they share its inputs and permissions. The labels below are catalog candidates. Some already have general Chat starters.

| Area | Suggested tasks |
| --- | --- |
| Research and Knowledge | Find an answer, find conflicting guidance, check against a checklist |
| Data and reporting | Write a project status update, create a chart or dashboard, review data quality, find exceptions |
| Writing and communication | Draft a document, create slides, draft a message, edit or translate, write an executive brief |
| Meetings and collaboration | Prepare for a meeting, summarize feedback |
| Operations and service | Triage a request, draft a support reply, prepare a handoff, design a workflow |
| Planning and decisions | Compare options, create a plan, review risks |

For example, **Check against a checklist** can be a starter for Document Analysis. **Review data quality** can be a starter for Spreadsheet Analysis. A recurring exception check can be a Workflow once its access and run identity are verified.

## How packs adapt agents

Packs set the task label, suggested inputs, approved Knowledge scope, and output format. The run uses the caller’s current access to the configured sources. Users see required inputs before starting and evidence gaps in the result.

| Proposed pack template | Shared agent | Pack-specific configuration |
| --- | --- | --- |
| Weekly support trends | Reporting | Weekly period, case volumes, recurring issues, and unresolved escalations. |
| Monthly budget variance | Reporting | Monthly period, approved budget sources, variance fields, and room for explanations. |
| Compare deal terms | Document Analysis | A checklist of terms and a cited comparison format. |
| Review onboarding material | Document Analysis | An onboarding checklist and a section for missing or conflicting guidance. |

## Reporting first release

1. In **Agent Catalog → New Agent**, select **Reporting**, add the Knowledge collections the agent can use, and save the draft. Use **Test in Chat** to try the exact candidate.
2. In Chat, choose an inclusive start and end date and one or more available Knowledge sources. Describe the report or use the general status, Support, or Finance starter.
3. Review the report's sources and evidence gaps. A completed response from a released Reporting agent can be saved as a Project output with its source links.

Each run retrieves evidence from its selected sources and assembles a report from verbatim, cited excerpts. Use an ISO date such as **2026-11-20** in the statement or on a date heading immediately above the corresponding lines in the same block. The agent omits statements it cannot tie to the selected period and flags empty report sections. The report uses a fixed format. Signed packs can opt in to the same Reporting agent, and the pack templates above are proposals.

The first release is on demand and read-only. Scheduled generation and delivery follow verification of the on-demand experience and its access controls.

## Spreadsheet Analysis first release

In **Agent Catalog → New Agent**, select **Spreadsheet Analysis**, save the agent, and open **Test in Chat**. Attach a UTF-8 CSV or XLSX file up to 1 MB. Use the first row for column headers. The agent accepts up to five visible sheets, each with up to 5,000 data rows and 24 columns. A completed answer from a released agent uses the existing Project output flow.

The agent calculates a standard profile of the attached file. First-to-last change follows row order. Potential outliers use the 1.5 × interquartile range rule for columns with at least eight supported values. Workbook formula and error cells are skipped and flagged. A values-only copy can include calculated results. Each run reads the file attached to that turn using the current user's upload access.

## Meeting Recap first release

In **Agent Catalog → New Agent**, select **Meeting Recap**, save the agent, and open **Test in Chat**. Paste meeting notes or a transcript and send. Each turn uses the notes supplied for that turn. The recap groups decisions, action items, and open questions, with the original quote and its line number. Owners and due dates are drawn from the action's supporting quote. Missing details appear as **Not stated**.

For structured notes, label lines **Decision:**, **Action:**, or **Open question:**. The agent can read those labels directly. For unlabelled notes, review the model's selection against the quoted lines. Use up to 16,000 characters and 250 lines per turn, within the selected model's context window. Each recap includes up to 12 items. Completed recaps from released agents can be saved to Projects.

## Market references

- Glean pairs all-team agents with department templates and describes the deliverable on each listing. [Glean Agent Library](https://www.glean.com/ai-agents/agent-library)
- Cohere North tests agents against task criteria before publication and supports restoring earlier versions. [Cohere North Agents](https://cohere.com/north/agents)
- Hebbia presents specialized capabilities through outputs such as diligence analyses, decks, and financial models. [Hebbia Matrix](https://www.hebbia.com/matrix/) · [Hebbia Max](https://www.hebbia.com/max/)
- WRITER packages repeatable work into Playbooks and reports quality, execution speed, and token cost. [WRITER Playbooks](https://writer.com/product/playbooks/)
- Salesforce and ServiceNow offer prebuilt agents for specific jobs and functions. [Salesforce Agentforce](https://www.salesforce.com/agentforce/) · [ServiceNow AI Agents](https://www.servicenow.com/products/ai-agents.html)

The comparison draws on public documentation and product pages. Authenticated behavior remains unverified.
