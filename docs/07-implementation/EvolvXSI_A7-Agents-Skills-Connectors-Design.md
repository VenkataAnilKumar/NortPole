# EvolvXSI — A7 design proposal: agents, skills and connectors in packs

Status: **Proposal, 2026-11-13, reviewed the same day (section 9), and the direction agreed the same day (section 11: govern the core's agents, skills, tools and connectors instead of building new ones). Steps 1 to 4 are built (step 3 with search only, step 4 for chat); the rest is not.** The review changes the execution model, adds a step before A7a and reorders the phases; read section 9 before section 6. The decisions in section 8, as revised in section 9, need an answer before any build starts. It covers checklist item 6 (A7) and the open question of horizontal and vertical packs.

## 1. In plain words

Three things can be added to a pack, and they are not equally risky:

| Thing | What it is | Risk |
| --- | --- | --- |
| **Skill** | Written know-how: "how we write a cited brief", "how we check a travel claim". Text only. | Low: it can steer the model but cannot do anything by itself. |
| **Agent** | A named specialist: instructions, the skills it uses, the tools it may call, the libraries it may read, and how far it may go. | Medium: it decides what to call. |
| **Connector / tool** | A way to reach something outside: read a source, call an API, send a message. | High: it touches real systems. |

The proposal is to let packs carry the first two as **data** (text and settings that are signed and checked), and to let packs only **ask for** connectors, never define them. Code stays out of packs.

## 2. What the market does (research, November 2026)

Most sources below are vendor pages or trade press; where a claim rests on one secondary source it is marked. Details change quickly: check the links before relying on them.

| Platform | How agents are built | How they are governed | What we take from it |
| --- | --- | --- | --- |
| **Anthropic, Agent Skills** ([docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)) | A skill is a folder with a `SKILL.md` (name, description, instructions) plus optional files and scripts. Loaded in levels: only name and description are always in context (about 100 tokens each); the body loads when the skill is used; extra files load only when read. | The docs say to use skills only from trusted sources, to audit every bundled file, and to treat them like installing software; a malicious skill can misuse tools or leak data. Enterprise plans can scan uploaded skills. On the API, skills run with no network. | The format is simple and has become common. Keep skills as text; load them in levels; treat scripts as the dangerous part. |
| **Microsoft, Copilot Studio and Agent 365** (secondary: [RCP Mag](https://rcpmag.com/articles/2026/08/19/microsoft-puts-agent-365-to-work.aspx), [Futurum](https://futurumgroup.com/insights/microsoft-agent-365-turns-shadow-ai-into-a-governed-asset-class/)) | Copilot Studio builds agents; Agent 365 (reported as launched May 2026) is the control plane. | A registry of every agent, including unmanaged ones; each agent gets its own identity (Entra Agent ID). One analysis notes the creator becomes the identity's sponsor by default. | The inventory and a **separate identity per agent** are the governance pattern. Agent sprawl is the problem they sell against. |
| **Google, Gemini Enterprise** ([docs](https://docs.cloud.google.com/gemini-enterprise-agent-platform/agents), [blog](https://cloud.google.com/blog/products/ai-machine-learning/the-new-gemini-enterprise-one-platform-for-agent-development)) | No-code Agent Designer for employees, an Agent Development Kit for developers, and the Agent2Agent (A2A) protocol for agents from other vendors; partner agents come through a marketplace. | Agent Registry, Agent Identity and Agent Gateway; administrators register approved agents and control access. Listing needs an "Agent Card" (a description file). | An **agent card** (what it does, what it may call) is a good unit for review. A2A is a possible later interop, not a start. |
| **Glean Agents** ([blog](https://www.glean.com/blog/glean-agents-go-2026)) | Visual builder; since October 2026 also agents built as code from developer tools. | Admins control who may build, share and run agents; policies combine access, behaviour and usage limits and can be tested before rollout; agents check data permissions on every request. | Closest to our promise: **the agent never sees more than the person asking**. Test before rollout matches our evaluation gate. |
| **Salesforce, Agentforce** ([Trailhead](https://trailhead.salesforce.com/content/learn/modules/trusted-agentic-ai/explore-agentforce-guardrails-and-trust-patterns)) | An agent is a set of **topics**; each topic has instructions and a short list of actions. | Guardrails sit outside the model, for example "no refund over a limit without human approval". | **Scoped topics with a short action list** beat a free-roaming agent; limits and approvals live in the platform, not in the prompt. |
| **Cohere North** ([Cohere](https://cohere.com/blog/north-ga), [TechCrunch](https://techcrunch.com/2025/08/06/coheres-new-ai-agent-platform-north-promises-to-keep-enterprise-data-secure/)) | Employees build and orchestrate custom agents with human oversight; private deployment (own cloud, on premises, air-gapped). | Connects to existing identity, logging and governance. (Detailed admin controls were not found in primary documents.) | The nearest model to what we are building: governed agents inside the customer's boundary. |
| **Pokee** ([GeekWire](https://www.geekwire.com/2025/point72-ventures-leads-12m-seed-round-for-a-new-ai-agent-startup-founded-by-ex-meta-manager/), [pokee.ai](https://pokee.ai/home)) | Natural-language workflows across many SaaS tools through native connectors (company claims). | Approval gates, role-based access and a full audit log (company claims). | Action agents need **approval gates and a replayable log**; we already have both for sends. |
| **OpenAI AgentKit** ([page](https://openai.com/index/introducing-agentkit/)) | Visual Agent Builder, Guardrails, a Connector Registry. | The same page now says Agent Builder and Evals are being wound down (an update dated 3 June 2026; the only source found). | **Do not make a visual builder the core.** Keep agent definitions as portable data files so a change of tool does not strand them. |
| **Open-source builders** (Dify, n8n, Langflow, Flowise; secondary: [WZ-IT](https://wz-it.com/en/blog/dify-flowise-langflow-n8n-comparison/), [MadAppGang](https://madappgang.com/blog/open-source-visual-agent-builders-compared-flowise-vs-langflow-vs-n8n-vs-sim-studio-in-2026/)) | Drag-and-drop flows; most support MCP. | Approval nodes exist in some; reports disagree. n8n and Dify are reported as source-available under their own licences, not OSI open source; Langflow is reported as MIT. | **Do not embed them**: licence terms need legal review, and their approval and audit models differ from ours. |
| **MCP security guidance** (secondary: [Trackr](https://www.trackr.live/2026/05/04/tool-poisoning-mcp-agents-threat-model/), [Practical DevSecOps](https://www.practical-devsecops.com/mcp-security/)) | MCP is the common way to give a model tools. | Practitioners report two recurring attacks: tool descriptions that contain instructions to the model, and servers that change a tool's definition after approval. Advice: allowlist by default, pin versions, compare definitions on every update, block outbound traffic from tool servers by default. | We already have a host allowlist. **Add pinning and change detection.** |

### What the market agrees on
1. **Skills are text files in a folder**, loaded in levels, and the risk is in bundled scripts.
2. **Governance is a registry plus an identity per agent plus tests before rollout plus a log.** We have three of the four (inventory, evaluation, audit); identity per agent is the gap.
3. **Small scoped agents with few actions** are easier to govern than open-ended ones.
4. **The model must not be the control.** Limits and approvals sit in the platform.
5. **Builders come and go** (OpenAI's wind-down, IBM's reported purchase of Langflow's owner). Definitions should be portable data.

## 3. Principles for EvolvXSI

1. **Declarative first.** A pack carries text and settings, never code. (Already the rule; this keeps it.)
2. **A pack can ask; only an administrator can grant.** Installation and grants stay separate (already the rule). A pack lists the skills it ships and the tools and connectors it **requests**; an administrator sees the request at install and grants some, all or none.
3. **The agent acts as the person asking, never wider.** Every read goes through the same access check as today; an agent has no standing access of its own. Scheduled runs with their own identity wait for your identity provider.
4. **An agent can propose, a person approves.** Write actions use the existing path: propose the exact content, owner approves, optional second approver, sent once. An agent never executes a send itself.
5. **The platform enforces; the prompt only asks.** The list of tools an agent may call is checked in code on every call, not by telling the model.
6. **Evaluated per model before it is offered** (already the rule), now including cases that test refusal and injection.
7. **Everything is inventoried, versioned, signed and reversible.**

## 4. The design

### 4.1 Skills in packs (instruction-only)

- A pack may ship skills in the common `SKILL.md` shape: `name`, `description` (what it does and when to use it), and a body of instructions. Optional reference files are allowed as **text only**; **no scripts**, no executables, no network calls (the validator refuses them).
- Loaded in levels, like the market format: only the name and description are in the planner's view; the body loads when the planner or a template selects the skill; reference files load when named.
- A skill's text is **pack-signer content**, not source content: it is trusted as far as the pack's signature is, and it can never add tools, widen access or change a route. It is shown to the reviewer in full at install.
- Skills inherit the existing style and review-rule mechanism: a template may name skills; the drafter includes their text under the same size caps.
- ~~Personal skills stay as today, instruction-only.~~ **Corrected in review (section 9):** today's personal skills are the inherited core's skill bundles: zip files of up to 100 MB with any files, mounted into the sandboxed task (Craft) workspace, so they can carry scripts. They are not instruction-only. Pack skills are a separate, text-only kind.

### 4.2 Agents in packs (declarative specs)

An agent is a spec, validated and signed like a template:

```
id, name, description (the agent card text), version
instructions        text, size-capped
skills              names of skills in this pack (or in a pack it depends on)
tools               names from the platform's tool catalog, each with a ceiling:
                    read_only | propose_only      (never "execute")
libraries           the libraries or source groups it may read (further limited by the asking person's access)
data_classes, routes   as for templates (the agent runs only where its pack passed evaluation)
autonomy            draft_only | act_with_approval (lowest tier along the path wins, as today)
limits              maximum steps, maximum tool calls, maximum duration
evaluation_cases    includes refusal and injection cases (see 4.6)
```

- **It runs through the reviewed-task engine** (plan, accept, run, cited draft, review rules, approval), not a new engine. A "pack agent run" is a Draft whose plan is made by the agent's instructions and whose evidence comes from the tools it was allowed. So citations, claim checks, redaction, route policy, tiers, audit and the Quality tab all apply without new code paths.
- **Depth one.** An agent does not call other agents in the pilot. (Salesforce's topic model and our own review burden both argue for small, flat agents.)
- **Agent card.** Each agent gets a read-only page that is also the install review: purpose, skills, requested tools and libraries, data classes, routes it passed evaluation on (and the model), autonomy ceiling, limits, version, signer, owner. The same fields can later be exported as an A2A-style card; that is not planned now.

### 4.3 Tools and connectors (administrator-owned)

- A **tool catalog** lists capability descriptors that only the platform and administrators create: a name, what it does, an argument schema (and its hash), the data classes it may touch, a ceiling (`read_only`, `propose_only`), and who registered it. Built-in tools today (source search, open a source) are the first entries; a **send destination** (already registered by an administrator) appears as a `propose_only` tool.
- A pack's agent can **request** catalog tools by name. It cannot define one. An unknown name makes the pack fail to install.
- **MCP servers and OpenAPI tools** (inherited from the core) enter the catalog only by an administrator: host allowlist (exists), plus **pinning**: at approval the server's tool names, descriptions and schemas are hashed and stored; on every later connection a changed definition marks the tool "changed since approved" and blocks it until an administrator re-approves; descriptions are treated as untrusted text and never placed in the system prompt unescaped; each call is logged with the arguments' size and outcome (not their content).
- Real connectors to document systems belong to A5 and are added to the catalog the same way.

### 4.4 Identity and access

- Run as the asking person, with their access list, at every read (as drafts do today).
- Each agent version has an **agent identity** in the inventory and the audit log ("agent X v2 acting for person Y"), so a run can be attributed and an agent can be disabled alone. No separate credentials in the pilot.
- A pack agent cannot widen access: its `libraries` is an upper bound that is intersected with what the person may open.
- Scheduled and background runs (Automations) with their own identity need your identity provider; not in scope.

### 4.5 Lifecycle and the three levels of who may create what

| Item | Pack author (signed) | Administrator (Studio) | Any person (personal) |
| --- | --- | --- | --- |
| Skill (text) | yes | yes | self-serve, private to them (as today) |
| Agent (spec) | yes | yes, as a draft that must pass evaluation and be activated | no in the pilot; request level later |
| Tool / connector | no (can only request) | yes | no; request only |
| Code | no | no | no |

Lifecycle for an agent: **draft, evaluate on a model, sign and publish, install, grant, activate for the workspace, monitor, roll back**. The mechanics for packs already exist; agents ride on them.

### 4.6 Evaluation for agents

An agent's evaluation cases, run per model as for templates, now also include:
- **refusal cases** (asks for something outside its libraries or tools; the right answer is a refusal),
- **injection cases** (a source tries to make it call a tool it was not given, or to cite a source it was not shown), reusing the injection suite, and
- **tool-use cases** (it uses the tools it needs and no others, within its step limit).
The agent is offered only on models where its exact version passed, and the Quality tab shows the result and the history.

### 4.7 Horizontal and vertical packs

- **Horizontal pack:** domain-neutral skills and agents (evidence briefing, document comparison); **vertical pack:** domain templates, terms, review rules, and agents that build on horizontal ones.
- A vertical pack may declare `extends: [{pack, version range}]`. At install, the extended packs must be installed, activated and evaluated on the same model; a vertical can add to but never loosen what the horizontal pack restricts (data classes, routes, autonomy: the narrower set wins).
- Recommendation: **build this after the first real vertical**, because the shape of the horizontal pack is easier to see once there is one customer's vertical; do the single-pack path first. A partial earlier attempt is kept outside the repository.

## 5. How it fits what is built

| Need | Already built | New |
| --- | --- | --- |
| Signed manifest, install, activate, roll back | yes | schema version 2 adds `skills`, `agents`, `requests.tools` |
| Evaluation per model gates what is offered | yes | agent cases (refusal, injection, tool use) |
| Autonomy tiers, second approver, one-time sends | yes | agents may only propose |
| Route policy, redaction, data classes | yes | none |
| Access check at every read | yes | none (agents inherit it) |
| Inventory, audit, Quality tab | yes | agent identity and tool-call log |
| Extension levels | skills and MCP allowlist | levels for agents; MCP pinning |

## 6. Phases (each ends with a build, test, review note and merge, as before)

| Phase | Work | Size | Needs from you |
| --- | --- | --- | --- |
| **A7a** | Tool catalog and manifest v2 (skills, agents, requests) with validation, signing and an install review page; no agent runs yet. | Medium | decisions 1 to 3 |
| **A7b** | Instruction-only skills: loaded in levels, named by templates, shown in review. | Small to medium | none beyond A7a |
| **A7c** | Pack agents run through the task engine with read-only tools; agent card; agent identity in audit and inventory; per-run tool-call log. | Medium to large | none beyond A7a |
| **A7d** | Agents may propose sends through destinations (never execute). | Small to medium | none |
| **A7e** | MCP pinning and change detection; call log; per-tool ceilings. | Medium | an MCP server to test against (a local one is enough) |
| **A7f** | Studio editor for administrators; request level for people. | Medium | decision 2 |
| **Later** | Horizontal and vertical `extends`; sandboxed code skills; A2A card export; exposing EvolvXSI as an MCP server; scheduled agent identities. | Large | first customer, identity provider |

A7a to A7d are what the pilot needs. Nothing here needs a cloud model, but the injection and tool-use evaluations are only meaningful on a real model (A8).

## 7. Risks and how the design answers them

| Risk | Response |
| --- | --- |
| A malicious or careless skill steers the model | Text only, signed, shown in full at install, no tools or access of its own; injection cases in evaluation. |
| A source tricks an agent into calling a tool | Tool list enforced in code per call; depth one; step and call limits; injection suite extended to tool calls; sends only proposed, then approved by a person. |
| Tool descriptions or definitions carry instructions or change after approval | Pin and hash on approval; block on change; treat descriptions as untrusted text. |
| An agent reads more than the asker may | Runs as the asker; `libraries` is only an upper bound; access checked at each read. |
| Agent sprawl | Every agent is in the inventory with owner, version, signer, last run; personal agents are off in the pilot. |
| Evaluation is gamed or too thin | Cases are part of the signed pack; the exact version must pass on the model in use; the Quality tab shows pass history. |
| Lock-in to a builder | Definitions are plain signed files; the editor is optional. |
| A pack agent is a way to ship code | Validator refuses scripts, executables and network calls; decision 1 keeps it that way. |
| A connector's price and failure modes are unknown | Connectors come in A5 on a real source; until then the catalog holds only built-ins and administrator-registered destinations. |

## 8. Decisions needed from you

1. **Confirm "no code in packs" for the pilot.** (Recommended: yes. Sandboxed code skills are possible later, with a signed bundle, no network and a human approval per run.)
2. **Who may author agents in the pilot?** Recommended: pack authors and administrators (through a Studio draft that must pass evaluation); people get instruction-only personal skills and no personal agents.
3. **Manifest v2 now?** Recommended: yes, so a first vertical can be written against the final shape.
4. **Depth one?** Recommended: agents do not call agents in the pilot.
5. **Horizontal and vertical `extends` now or after the first vertical?** Recommended: after.
6. **Interop (A2A card, EvolvXSI as an MCP server)?** Recommended: not now.
7. **Agent identity** is a label in the log and inventory, not a credential, until your identity provider is chosen. Confirm.

## 9. Review, 2026-11-13 (by the author, against the code)

The direction holds: declarative packs, administrator-owned tools, the asking person's access, proposals instead of sends, evaluation per model. Three problems must be fixed before A7a, and several smaller ones should be.

### Must fix

**R1. The execution model contradicts a security property we already rely on.** Section 4.2 says agents "run through the reviewed-task engine" with tools. But that engine has no tool loop: evidence is gathered by code (`tasks/evidence.py`, the owner's access filters, at most 4 passages), and planning and drafting requests carry **no tools at all**. The A9 work and the threat model (T1) count on that: "no tools on planning and drafting, so source text cannot trigger an action". The injection suite measured the 7B model obeying hostile text in 31% of runs; a tool loop would turn some of those into tool calls.
**Correction: plan-then-execute, with the platform running the tools.** The agent's plan step outputs structured steps that name catalog tools and their arguments (`search(library, query)`, `open(source)`, `propose_send(destination)`), validated against the agent's tool list and limits. The person accepts the plan, as they accept plans today, so they see which tools will run before anything runs. The executor (code, not the model) runs the steps; tool results go to the drafter as **data**, quoted like sources. The drafter still has no tools. A model that obeys injected text can at most write a bad draft, which the reviewer and the claim checks see; it cannot call anything. Follow-up steps that depend on results (search again with a better query) are a second, separately accepted plan, not an open loop. This is slower and less flexible than an agent loop, and that is the point for the pilot.

**R2. The inherited core already has agents, skills and tools, and the design ignores them.**
- *Skills:* the core's custom skills are zip bundles mounted into the Craft sandbox; they can hold scripts (correction to 4.1 above). The `personal_skills` switch governs these. The design must name two kinds: **pack skills** (text, signed, used by drafts) and **sandbox skills** (bundles, Craft only, which stays off unless Craft is on).
- *Agents:* the core's chat "agents" (the Agents page, custom assistants) can be given MCP and OpenAPI tools that the model calls **directly in chat**, with no plan acceptance, no tier and no approval. The MCP host allowlist limits where, not what. This path was outside the threat model ("the chat path ... not assessed"). Pack agents would be governed while chat agents with tools are not.
- **Correction:** add a step before A7a, **A7-0**: list every tool a chat agent can call today, decide which may stay (read-only built-ins), and put tool-calling chat agents behind an administrator switch (default off) until the catalog and pinning (A7e) cover them. Rename in the interface so people can tell a chat assistant from a pack agent.

**R3. The phase order builds a schema before anything uses it.** A7a (catalog and manifest v2, no runs) would fix a format with no feedback from a working agent.
**Correction:** A7b (text-only pack skills) first, since it is small and useful on its own; then one **thin end-to-end slice**: one agent spec, two read-only tools (search, open), plan-then-execute, agent card, audit label, one evaluation case set; then generalise the catalog and manifest v2 from what that slice needed.

### Should fix

- **Mental model in the interface.** Users already have Workflows (pack templates), chat assistants (the core's Agents page) and Drafts. A fourth noun, "pack agent", will confuse. Proposal: present a pack agent as a **workflow that can look things up**: it appears in Workflows, starts a Draft, and its agent card is the workflow's detail panel. "Agents" stays the chat-assistant page.
- **Manifest compatibility.** Installed packs are schema 1, signed over canonical bytes. Version 2 must accept and keep verifying version 1 packs unchanged, and a version 1 pack must never gain agent features by reinterpretation.
- **Skill text is trusted too much.** "Trusted as far as the pack's signature" means a signer can put instructions into every draft prompt. Keep the trust, but give skills the same caps as `style`, keep them below the system rules in the prompt, show them in the install review, and include a "skill tries to widen scope" case in evaluation.
- **Cross-signer `extends`.** A vertical signed by A that extends a horizontal signed by B: both signers must be trusted, revoking B disables the vertical, and the install review shows both. Not in section 4.7.
- **Per-agent budgets.** The token and cost counters (A8) exist; an agent spec should carry a token ceiling per run, enforced by the executor, and the Quality tab should show cost per agent.
- **Kill switch per agent**, not only per pack: an administrator can disable one agent version without deactivating the pack.
- **Research gaps.** Amazon (Bedrock AgentCore) and the code-first frameworks (LangGraph, CrewAI, OpenAI's and Google's agent SDKs) were not looked at, and only one source was read in full. Plan-then-execute is a known pattern in the prompt-injection literature; the design should cite primary work for it before relying on it, which this review has not done.

### Decisions, revised
Decisions 1, 2, 4, 5, 6 and 7 stand. Decision 3 (manifest v2 now) becomes "after the thin slice" (R3). Two decisions are added:

8. **Plan-then-execute instead of a tool loop for the pilot** (R1). Recommended: yes.
9. **Turn off tool-calling for the core's chat agents until A7e covers them** (R2). Recommended: yes. This removes a capability people may already use in the sandbox; nobody uses the product in production yet.

### Phases, revised
| Phase | Work |
| --- | --- |
| A7-0 | List the core's chat-agent tools; administrator switch for tool-calling chat agents (default off); name the two skill kinds in the interface. |
| A7b | Text-only pack skills (as in section 6). |
| A7c-thin | One agent end to end: plan-then-execute with search and open, agent card in Workflows, audit label, evaluation cases including injection and refusal. |
| A7a | Catalog and manifest v2, generalised from the slice; v1 packs unchanged. |
| A7d, A7e, A7f | As in section 6, with A7e also covering chat-agent tools. |

## 10. Not covered

A cost model for agent runs beyond the token counts already collected; a visual flow builder; marketplaces; agents that run unattended; agents that hold their own credentials; a review by someone who did not write this proposal.

## 11. Agreed direction, 2026-11-13: govern the core, do not rebuild it

After looking at what the inherited core already contains (chat agents and their runtime, 13 kinds of chat tools, MCP and OpenAPI tools, a skills system with 14 built-in skills, 63 source connectors), the owner agreed to this shape. It replaces the phase plan in sections 6 and 9; the principles in section 3 and the risks in section 7 stand.

- **One agent concept, two modes.** *Assistant* (the core's chat agents): read-only tools in chat, write and code tools off unless an administrator turns them on. *Workflow agent* (from a pack): plan-then-execute as in section 9 R1, producing a reviewed Draft; sends only proposed.
- **A tool catalog around the core's tools, not new tools.** Every tool has a kind (read, web, generate, personal, code, outside) and is allowed or not; the check sits where the core builds a chat's tools.
- **Two kinds of skill:** *guides* (text only, in packs) and *sandbox skills* (the core's bundles, Craft only).
- **Connectors are reused**, not written: the pilot's one connector is chosen from the 63 and tested with permissions (A5).
- **Outside tools only once pinned** (definitions recorded at approval; a change blocks the tool).
- **Decisions agreed:** govern rather than rebuild; write and code tools off in chat by default; no code in packs; pack authors and administrators write agents. Open: the pilot's source system.

| Step | Work | State |
| --- | --- | --- |
| 1 | Tool catalog: inventory, kinds, administrator switch, enforcement where chat tools are built | **Built 2026-11-13** (see REVIEW) |
| 2 | Guides (text-only skills) in packs, used by Workflows and drafts | **Built 2026-11-13** (see REVIEW) |
| 3 | One workflow agent end to end (plan-then-execute with search and open; agent card; tests incl. injection and refusal) | **Built 2026-11-13 with search only** (see REVIEW): "open" (read more of a found document) is not built; an agent's `libraries` limit is not built (it searches whatever the person can open); evaluation does not yet run through the agent's plan |
| 4 | Pinning for MCP and OpenAPI tools; call log; pinned tools as workflow steps | **Built 2026-11-13 for chat** (see REVIEW): pinned approval, change detection, a server check, a call log. Not built: pinned tools as workflow steps; not tried against a live MCP server (blocked by the SSRF guard in the sandbox, by design) |
| 5 | The pilot connector, tested with permissions | Needs the source system |
| 6 | Administrator editor for agent specs; manifest version 2 shaped by steps 2 to 4 | |

