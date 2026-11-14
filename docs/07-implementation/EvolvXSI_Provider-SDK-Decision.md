# EvolvXSI — provider SDK and dependency decision

> **Where this lives in code (2026-11-14).** Service and package names here (`services/control-plane`, `services/execution`, `services/knowledge`, `packages/*`, `evaluations`) are logical owners from the design stage. [Decision 0006](../decisions/0006-scalable-repository-structure.md) maps them to the code: the three services are implemented inside `services/core`, and the packages and evaluations are planned modules in `modules.json`, created when their first code arrives.

Decision date: 2026-11-02 · Reconfirmed: 2026-11-05 · Status: reference-only owner direction; application implementation pending

## Direction

Use official model-provider SDKs behind EvolvXSI-owned adapters. Agno and the other downloaded agent platforms are reference material, not mandatory runtime dependencies. The earlier source-to-repository map identified reuse candidates; its fork/extraction suggestions are superseded by this decision. Retain checkouts for study and provenance. No source deletion or integration is requested.

EvolvXSI owns its agent/skill manifests, run orchestration, checkpoints, approvals, tenant permissions, memory, retrieval, artifact lifecycle and evaluations. Ordinary infrastructure and language dependencies remain necessary; avoiding another agent framework does not mean implementing databases, cryptography or HTTP stacks from scratch.

## SDK boundaries

- The [official OpenAI API SDKs](https://developers.openai.com/api/docs/libraries) provide model API clients.
- The [OpenAI Agents SDK](https://developers.openai.com/api/docs/guides/agents) is a separate optional in-application agent loop abstraction. It is not selected automatically by choosing the API client. Select it only after deciding whether EvolvXSI owns the loop directly.
- [MiniMax documents use of the OpenAI SDK](https://platform.minimax.io/docs/api-reference/text-openai-api) through its compatible Chat Completions endpoint. This can avoid a second text-client dependency. Provider adapters must respect actual supported parameters and capabilities; compatibility does not establish full Responses API or hosted-tool parity.
- MiniMax Code SDK drives the coding-agent executable. It is not the same dependency as a MiniMax model API client, and is not selected for the core platform by this decision.

Start with the official API client and an EvolvXSI provider interface. Implement an OpenAI route and/or a MiniMax route according to the chosen pilot. Pin SDK versions when implementation starts. The provider, model, language and optional Agents SDK selection remain open; no live requests, credentials or installs are required for this documentation change.

## Repository ownership

| Module | Implementation direction |
| --- | --- |
| services/execution | EvolvXSI-owned run state and lifecycle; optional official agent-loop SDK after explicit selection. |
| packages/agents | EvolvXSI-owned definitions; no imports from third-party agent definitions. |
| packages/skills | EvolvXSI skill contracts; existing skill repositories are examples, not implicit dependencies. |
| services/model-gateway | Official provider clients, capability-aware adapters and EvolvXSI placement policy. |
| services/knowledge | EvolvXSI retrieval/memory boundary using selected storage infrastructure; no mandatory Agno or upstream-core service. |
| evaluations | EvolvXSI quality suites and release gates. |
| Other product modules | EvolvXSI-owned implementation; downloaded application platforms remain references unless the owner later selects explicit reuse. |

Provider endpoints, credentials, retry behavior, streaming, tool calls and usage accounting are isolated in adapters. Persist checkpoints independently of a model response. Apply policy to all processing destinations and recheck approvals before external actions.

## Layer assignment

L07 owns provider adapters and destination enforcement. L05 owns orchestration and run state. The reference-only decision applies across the platform.

## Reconfirmed source strategy

The owner selected the attached local/web reference-only approach after discussing copying and rebranding. The fork-and-rebrand and build-versus-fork proposals are not selected. Study commercially evidenced products, record design conclusions, and implement EvolvXSI behavior independently. Ordinary SDK/library/infrastructure adoption remains a separate dependency decision. See the [implementation workstream](EvolvXSI_Implementation-Phases.md#reference-only-implementation-workstream).
