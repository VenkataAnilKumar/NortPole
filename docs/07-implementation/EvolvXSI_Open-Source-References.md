# EvolvXSI — open source references

> Current dependency direction (2026-11-02): downloaded projects are reference-only. Earlier fork, adapter-copy and runtime-selection suggestions below are historical candidates, superseded by [the provider SDK decision](EvolvXSI_Provider-SDK-Decision.md). Implement EvolvXSI-owned boundaries using official provider clients; no third-party agent platform is a required dependency.

Status: **official-site review, not product decisions** · Updated: 2026-11-02

This document is the sole place in the EvolvXSI document set for named external projects and open source implementation research. The [product overview](../02-product/EvolvXSI_Product-Overview.md), [PRD](../04-specs/EvolvXSI_First-Workflow-PRD.md), [architecture](../06-technical/EvolvXSI_System-Architecture.md), and [implementation phases](EvolvXSI_Implementation-Phases.md) describe EvolvXSI independently of any vendor or project.

## Origin

The owner's chats **Evaluate Onyx For Evolve SI** and **Agent Platform Architecture** discussed an integration-first approach. They proposed using Onyx as a possible base, extending it with specialized components only where the chosen workflow needs them. The chat **Product Ideas Compare** established the horizontal platform and vertical platform concepts. These discussions are planning context, not evidence that a dependency is approved, integrated, licensed for the intended use, or currently maintained.

## Candidate map

| Capability | References mentioned in chat history | Evaluation question |
| --- | --- | --- |
| Knowledge, chat, connectors, initial agent UI | [Onyx](https://github.com/onyx-dot-app/onyx) | Can it support the required permission-aware flow and branding through stable extension points? |
| Stateful agent execution | [LangGraph](https://github.com/langchain-ai/langgraph), [Deep Agents](https://github.com/langchain-ai/deepagents) | Do checkpoints, review points, tracing, and upgrades work for the selected workflow? |
| Model gateway | [LiteLLM](https://github.com/BerriAI/litellm) | Can EvolvXSI enforce data-placement policy before provider routing and measure cost per task? |
| Local inference | [Ollama](https://github.com/ollama/ollama) | Are quality, latency, throughput, and operations acceptable for the pilot? |
| Private GPU inference | [vLLM](https://github.com/vllm-project/vllm) | Is a private serving tier justified by deployment requirements and volume? |
| Durable business workflows | [Temporal](https://github.com/temporalio/temporal) | Does the first workflow need a separate process engine beyond agent checkpoints? |
| Evaluation and tracing | [Opik](https://github.com/comet-ml/opik) | Does it support the pilot's evaluation, retention, and trace requirements? |
| Scientific tools and knowledge graphs | [ToolUniverse](https://github.com/mims-harvard/ToolUniverse), [BioCypher](https://github.com/biocypher/biocypher) | Are these needed for the selected vertical, and can outputs carry sufficient provenance? |

Other projects named in the earlier research are alternatives to compare when a specific requirement calls for them, not a mandate to assemble every project into one stack.

## Eight-platform review — 2026-11-02

The owner supplied eight product sites for review. This is a **desk review of official product pages, documentation, and repositories**, not a hands-on install, security audit, benchmark, or legal opinion. “Fit” below is an inference against EvolvXSI's current PRD. Marketing claims are not treated as measured performance.

| Product | What the official material emphasizes | EvolvXSI fit to test | Source and licensing signal |
| --- | --- | --- | --- |
| [Onyx](https://onyx.app/) | Enterprise knowledge indexing, permission-aware search, chat, agents, and research. | Strong context and retrieval candidate; test whether its workflow and approval model supports the first vertical. | [Community Edition is MIT; Enterprise Edition is separate](https://github.com/onyx-dot-app/onyx#-licensing). |
| [Sim](https://www.sim.ai/) | Visual and code-built workflows, knowledge base, files, tables, logs, and workspace governance. | Strong candidate for the complete workflow workspace; test evidence permissions and reviewer UX. | [Core is Apache 2.0; enterprise features have a separate production license](https://github.com/simstudioai/sim/blob/main/apps/docs/content/docs/introduction/index.mdx). |
| [Kortix](https://kortix.com/) | Shared agents, company configuration in git, computer-based work, and self-hosting. | Reference for a company-wide agent workspace and long-running execution. | Current [repository license is Elastic License 2.0](https://github.com/kortix-ai/suna/blob/dev/LICENSE); [white-label hosting terms](https://github.com/kortix-ai/suna/blob/dev/WHITE-LABEL-LICENSE.md) add conditions. |
| [Agno](https://www.agno.com/) | Agent SDK, AgentOS runtime, and a control plane for traces, evaluation, approvals, and scheduling. | Strong runtime/control-plane candidate; test whether its UI meets practitioner needs or needs a separate product front end. | [SDK repository is Apache 2.0](https://github.com/agno-agi/agno/blob/main/LICENSE); confirm terms for the [Control Plane](https://docs.agno.com/agent-os/control-plane) separately. |
| [Busabase](https://busabase.com/) | Structured agent data, knowledge, apps, skills, and reviewable writes. | Candidate for persistent agent work products or reference pattern for provenance; not yet a proven replacement for retrieval or runtime. | [Repository is MIT](https://github.com/busabase/busabase/blob/main/LICENSE). |
| [OpenAgents](https://openagents.org/) | Shared people-and-agent workspace, threads, files, remote or local agents, and reviews. | Candidate collaboration front end; test workflow state, source permissions, and evaluation depth. | [Self-hosted platform is Apache 2.0](https://openagents.org/). |
| [Opengeni](https://opengeni.ai/) | Always-on agent computers, shared sessions, scoped credentials, action approvals, and schedules. | Candidate for sandboxed long-running tasks where code or browser execution is necessary. | [Apache 2.0 and self-hosting are described by the project](https://opengeni.ai/). |
| [Rerun](https://rerun.build/) | AI coworkers with their own computers, scheduled work, integrations, and human approvals. | Reference for an outcome-focused, approachable UX; test the product against the selected vertical rather than adopting it as a default foundation. | [Repository is AGPL-3.0](https://github.com/rerun-build/rerun/blob/main/LICENSE); verify obligations before reuse. |

### Onyx

Onyx's [repository](https://github.com/onyx-dot-app/onyx) describes indexed knowledge from many applications, fine-grained permissions, deep research, custom agents, MCP actions, sandboxes, and artifacts. Its own deployment description distinguishes a full indexing stack from a Lite chat-and-agent mode, so a knowledge-focused spike should use the full mode. The company [announced it is joining Zoom](https://onyx.app/blog/onyx-joins-zoom) and says Onyx will remain a standalone open-source product. That is relevant to the future roadmap and support relationship, but does not by itself disqualify the project. Test source permission propagation, citation provenance, workflow extension points, and what features are CE versus EE before treating Onyx as the base.

### Sim

Sim's [product site](https://www.sim.ai/) presents a single workspace for visual or coded workflows, knowledge, files, tables, and block-level run logs. Its [documentation](https://github.com/simstudioai/sim/blob/main/apps/docs/content/docs/introduction/index.mdx) describes self-hosting and distinguishes Apache-licensed core from separately licensed enterprise features. This is a closer “whole workspace” comparison than a single runtime library. Test workflow approval points, retrieval permissions, export provenance, and which governance controls require an enterprise subscription.

### Kortix

Kortix's [site](https://kortix.com/) centers on shared company agents, skills, memory, connectors, and sessions with configuration stored in git. Its current [license file](https://github.com/kortix-ai/suna/blob/dev/LICENSE) says Elastic License 2.0. The separate [white-label agreement](https://github.com/kortix-ai/suna/blob/dev/WHITE-LABEL-LICENSE.md) permits branded hosted offerings under stated conditions, including exclusive use of Platinum for covered compute and a termination mechanism. This is a material commercial constraint for an EvolvXSI-branded fork. Treat Kortix as **source-available under the current terms**, despite the site's broad “open source” phrasing, until counsel reviews the exact version and agreement. Study the company-as-code and sandbox UX without making it the default base.

### Agno

Agno separates an [SDK](https://github.com/agno-agi/agno), [AgentOS runtime](https://www.agno.com/products/runtime), and [Control Plane](https://docs.agno.com/agent-os/control-plane). Its official material describes durable execution, RBAC, audit logs, traces, evaluations, and approvals. The SDK repository is Apache 2.0; that does not establish redistribution rights for every product surface shown on the site. For EvolvXSI, Agno is a serious candidate for a runtime with built-in operations. A spike should test run resumption, approval semantics, per-tenant isolation, model placement policy, and whether the control-plane UX can be embedded or must remain separate.

### Busabase

Busabase's [site](https://busabase.com/) describes a durable workspace for agent-produced tables, documents, skills, and apps. It highlights source and change history plus human review for important writes. The [license file](https://github.com/busabase/busabase/blob/main/LICENSE) is MIT. It could help with the “work product survives the session” part of EvolvXSI, but its site does not establish that it solves the PRD's full permission-aware retrieval and agent execution needs. Test record provenance, tenant and user permissions, approval semantics, and integration with the chosen runtime before adding another data system.

### OpenAgents

OpenAgents' [workspace](https://openagents.org/) centers on people and agents sharing threads, files, live browser context, delegation, and reviews. It can connect agents running on a user's computer or remote server. The site says the full self-hosted platform is Apache 2.0, consistent with its [license file](https://github.com/openagents-org/openagents/blob/develop/LICENSE). It is a useful reference for team collaboration, but must be tested for the selected vertical's task state, evidence links, source permissions, and versioned evaluations.

### Opengeni

Opengeni's [site](https://opengeni.ai/) describes persistent agent computers, long-running goals, shared workspaces, schedules, a credential vault, and action policies of Allow, Ask first, or Block. It says the project is [Apache 2.0 and self-hostable](https://opengeni.ai/). This is most relevant if the chosen workflow requires a real sandbox or extended unattended work. Test credential isolation, permission inheritance, interruption and replay, and whether the infrastructure cost is justified for a report workflow.

### Rerun

Rerun's [site](https://rerun.build/) packages agents as approachable “coworkers” with their own computers, scheduled tasks, app integrations, and approval requests. The [repository](https://github.com/rerun-build/rerun) describes self-hosting and carries an [AGPL-3.0 license](https://github.com/rerun-build/rerun/blob/main/LICENSE). Its outcome-oriented language and review flow are useful product references. A commercial fork or hosted derivative needs a license review and a clear fit with the first customer workflow before adoption.

## Decision for the next technical spike

**No platform is selected as EvolvXSI's foundation by this review.** The earlier Onyx-first assumption should be tested against the broader options now available. Run the same thin vertical slice on three routes:

1. **Onyx-led:** indexed context, practitioner task flow, citation, and approval.
2. **Sim-led:** workspace and workflow, with equivalent source permission and evidence checks.
3. **Agno-led:** runtime and control plane, measuring the extra work required for a practitioner-facing UI and enterprise context.

Score each on permission fidelity, evidence and citation quality, review and approval behavior, restart recovery, tenant isolation, extension cost, upgrade path, operating cost, and commercial rights. Keep Busabase as a data/work-product spike only if the chosen route lacks that capability. Evaluate OpenAgents, Opengeni, Kortix, or Rerun as focused collaboration or execution references when the first workflow needs them. Do not combine all eight into one stack.

## MiniMax-AI references — 2026-11-02

Reviewed the [official organization](https://github.com/MiniMax-AI) and five relevant repository READMEs. This is a source review; no packages were installed, executed, or approved as dependencies. License labels below describe repository declarations; check bundled assets, individual skills, host software, and service terms before copying or shipping.

| Priority | Repository | Reference value for EvolvXSI | Limit to validate |
| --- | --- | --- | --- |
| High | [MiniMax-Code-MiniApps](https://github.com/MiniMax-AI/MiniMax-Code-MiniApps) | Domain-specific interactive workspaces where users inspect, edit, and confirm agent work. The host separates UI, business services, tools, and credentials. | Desktop-host architecture; validate portability to a web product and each plugin's license and permissions. Organization lists repository as MIT. |
| High | [Mini-Agent](https://github.com/MiniMax-AI/Mini-Agent) | Small execution-loop reference with session notes, context summarization, MCP tools, and logging. | Explicitly a single-agent demo; enterprise isolation, durable approvals, and retrieval permissions need separate proof. Repository declares MIT. |
| High | [skills](https://github.com/MiniMax-AI/skills) | Reusable document, spreadsheet, presentation, and media workflows; useful for the artifact-output part of a vertical solution. | Review individual skill dependencies, attribution, validation, and external API data destinations. Repository declares MIT and includes credits for derived work. |
| Conditional | [OpenAgentCore](https://github.com/MiniMax-AI/OpenAgentCore) | Durable execution state and replaceable harness, sandbox, filesystem, and provider protocols. Useful for studying execution infrastructure. | API compatibility is the project's claim; verify the required operations and lifecycle behavior with contract tests. Repository declares MIT. |
| Conditional | [OpenRoom](https://github.com/MiniMax-AI/OpenRoom) | Browser desktop and structured app-action system; useful for agent-operable UI patterns. | Browser-local storage and sample apps do not establish enterprise multi-user controls. Its README notes that agent chat requires an LLM API key. Repository declares MIT. |

**Recommendation:** prioritize MiniApps for the vertical workspace pattern, Mini-Agent for a readable agent loop, and skills for validated artifact production. Compare OpenAgentCore with the runtime options only if sandboxed coding sessions are required. Use OpenRoom as an interaction reference. These are focused references, not a new foundation decision. Model-weight repositories and multimodal services can be evaluated later against a concrete workflow; repository code licenses do not establish model or hosted-service rights.

### MiniMax Code — additional reference

[MiniMax Code](https://github.com/MiniMax-AI/minimax-code) is a useful harness reference for code editing, command execution, permissions, session resumption, plugins, and custom models. Headless execution, ACP, and a TypeScript SDK offer integration paths. Evaluate it for an engineering vertical or sandbox worker. Enterprise tenancy, source permissions, and approval contracts still need testing against EvolvXSI's PRD.

The repository covers terminal/headless/ACP source; the desktop app source is excluded. First-party code defaults to MIT with file/package exceptions. Check [license status](https://github.com/MiniMax-AI/minimax-code/blob/main/LICENSE-STATUS.md), bundled tools, and hosted-service terms. No installation or benchmark was performed.

## Selection checklist

1. Confirm the current repository, release health, support model, and security posture.
2. Read the current license and terms for hosting, redistribution, branding, and modified versions. Do not infer rights from an earlier chat summary.
3. Run a small technical spike against the PRD's permission, citation, approval, recovery, and audit requirements.
4. Estimate ongoing upgrade, deployment, and operating cost.
5. Record the chosen component, alternatives considered, and reason in a decision record.

The eight supplied sites and linked official repositories were reviewed on 2026-11-02. The older candidate map above includes projects that were **not** re-reviewed in this pass. Feature claims, license boundaries, and commercial terms must be checked again at the exact commit and product edition chosen for a build.


## Local source mapping and correction

See [source-to-repository mapping](EvolvXSI_Source-Repository-Mapping.md) for exact local evidence and reuse candidates. The earlier OpenAgents checkout was a different project; sources/openagents-workspace now contains the project linked by openagents.org. Earlier OpenAgentsInc links do not substantiate that collaboration product.

## Pokee research: RL environments and self-improvement reference

Reviewed: 2026-11-02 · Reference only; no code cloned, copied, installed or selected as a dependency.

Primary sources: [PokeeResearchOSS](https://github.com/Pokee-AI/PokeeResearchOSS) and [research paper, revision 4](https://arxiv.org/abs/2510.15862v4). The paper originally used the PokeeResearch title; revision 4 is titled Rethinking the Design of Reinforcement Learning-Based Deep Research Agents.

The paper formulates deep research as an episodic finite Markov decision process. It studies AI-judge feedback, on-policy RLOO, filtering training samples and error-tolerant inference rollouts. Reported benchmark improvements are findings for that research setting, not independently verified results for EvolvXSI or every enterprise workflow.

The public repository exposes agent, agent_loop, reward, tool_client, tool_server and data directories, plus a verl submodule. Its README documents multi-turn search/read research, trajectory output and benchmark evaluation. The setup names external search, content extraction and judge services and GPU model inference. It is not evidence of a self-contained offline environment or the complete enterprise platform. Full training reproducibility and enterprise deployment capabilities have not been verified by running the repository.

| Reference pattern | Proposed EvolvXSI adaptation |
| --- | --- |
| Research episodes and tool interaction | Versioned synthetic/approved document tasks with simulated search/read tools. |
| Reward and AI feedback | Deterministic checks plus calibrated judges and expert review. |
| Recorded trajectories and benchmarks | Immutable experiment lineage and held-out comparison. |
| Training/inference design experiments | Compare simple candidate changes before authorizing model RL. |

The adaptation above is our proposal, not a claim about Pokee's internal system. [Learning-environment architecture](../06-technical/EvolvXSI_Learning-Environments.md) defines EvolvXSI-owned contracts and controlled promotion. This does not supersede the provider SDK decision or permit automatic production self-modification.


## Commercial reference research — 4 November 2026

The [commercial reference review](EvolvXSI_Commercial_Reference_Research.md) evaluates Temporal, Langfuse, LiteLLM, Qdrant, Infisical, Appsmith, E2B, Dify, n8n and Airbyte against named adoption evidence and product-module relevance. It records source-license boundaries and maps each study to an EvolvXSI design question. Temporal and LiteLLM were already mentioned in earlier research. All entries remain reference only. This review adds research candidates to the documentation. The downloaded-source manifest continues to describe only existing local snapshots.
