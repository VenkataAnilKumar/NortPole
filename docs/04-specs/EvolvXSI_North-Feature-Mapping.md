# EvolvXSI — North feature mapping

Status: **draft; secondary sources only** · Updated: 2026-11-10

This maps publicly described Cohere North capabilities to the [platform feature catalog](EvolvXSI_Feature-Spec.md#full-platform-feature-catalog). North details come from news coverage, release notes and third-party summaries, not from Cohere's own documentation or a hands-on review. Release dates conflict between sources. Treat each North row as a vendor-described capability, and mark anything unverified as untested. The mapping does not claim feature parity and does not change scope. All EvolvXSI features are proposed; none is implemented.

## Mapping

| North capability (as described) | EvolvXSI feature | First target | Fit and notes |
| --- | --- | --- | --- |
| Chat, with consolidated tools menu and recent chats | PF-01.03 chat, libraries and generated applications; PF-01.12 slash commands | Expansion | Partial. EvolvXSI treats tasks as primary and chat as a way into a task. |
| Search across company data | PF-01.02 search and artifact review; PF-06.01 ingestion and provenance; PF-06.02 hybrid retrieval | Pilot / Expansion | Strong. Citations resolve to versioned, permitted passages. |
| Agents built from simple prompts | PF-02.01 agents and skills; PF-01.11 prompt-to-agent drafting | Pilot / Expansion | Strong. Drafts must pass evaluation and are never published automatically. |
| Skills (reusable capabilities) | PF-02.01; PF-02.05 signed packages | Pilot / Expansion | Strong |
| Automations with drag-and-drop templates | PF-01.05 Studio; PF-05.03 schedules, triggers and isolation | Expansion | Partial. No visual builder is specified. |
| Libraries (shared organization assets) | PF-06.01; PF-06.03 file parsing; Knowledge tab in the [UI spec](../05-design/EvolvXSI_UI-Spec.md#user-portal) | Pilot / Expansion | The UI tab is now named Libraries (renamed from Knowledge on 2026-11-10). |
| Memory across sessions | PF-06.04 memory controls | Expansion | Strong. Adds view, edit, delete and scope limits. |
| Connectors (Slack, SharePoint, OneDrive, Outlook, Exchange, Jira, Linear, Notion, GitHub, Google Drive, Gmail) | PF-08.01 source adapters; PF-08.02 tool ecosystem | Pilot / Expansion | Partial. One connector is planned for the pilot and none is named. |
| Orchestration with human sign-off before critical actions | PF-05.02 human checkpoints; PF-04.02 approval and revocation; PF-05.04 delegation | Pilot / Expansion | Strong. Approval binds to the exact version or payload. |
| Artifact creation and analytics | PF-01.03; PF-09.03 analytics and alerting | Expansion | Partial |
| Roles and permissions | PF-04.01 tenant and actor access; PF-04.03 enterprise governance | Fixture / Expansion | Strong |
| Control over which models are used where and by whom | PF-07.02 approved inference; PF-07.03 hybrid routing | Pilot / Expansion | Strong. See [decision 0002](../decisions/0002-hybrid-routing-and-pilot-scope.md). |
| Per-agent guardrails and autonomy policies | PF-04.07 autonomy tiers | Pilot | Strong |
| Budget controls: quotas, rate limits, caps, usage by user and agent, alerts | PF-07.06 spend controls; PF-09.07 metering export | Expansion | Strong on paper. The UI spec lists Usage & Billing as expansion only. |
| Customer-supplied models | PF-07.05 customer-supplied and tuned models | Expansion | Strong |
| Private cloud, on-premises and air-gapped deployment | PF-10.02 and PF-10.03 profiles; PF-10.05 hybrid control and data planes | Pilot / Expansion | Partial. Air-gapped is not a named profile. |
| Admin console | PF-03.05 agent and tool inventory; Admin Console tabs in the UI spec | Pilot / Expansion | Strong |

## Gaps to decide

- Connector breadth: email and calendar connectors and the list above are not catalog entries.
- A visual workflow builder for automations (PF-01.05 and PF-05.03 do not specify one).
- Air-gapped deployment as an explicit profile (PF-10.03).
- Navigation: Knowledge is now Libraries. Skills, Memory and Connectors are sub-tabs (Agents, My Files, Settings) rather than top-level tabs; reconsider if visible parity with North matters. Usage is an admin tab but remains expansion scope, although spend controls are North's best-described admin area.
- Personal and requested extensions: PF-08.06 covers Off, Request and Self-serve levels; North sources did not describe an equivalent.

## EvolvXSI areas not seen in North sources

The searches found nothing on these, which is not evidence that North lacks them: exact-version approval binding and revocation withholding (PF-04.02), sensitive-data redaction and an injection-defense suite (PF-04.04, PF-04.05), evaluation-gated publication bound to exact dependencies (PF-09.02), claim-to-source review (PF-01.02), compliance evidence reports (PF-04.06). EvolvXSI also adds user-selectable local and cloud routes (PF-07.03) and vertical pack lifecycle (PF-02.02, PF-02.03).

## Suggested sequence

1. Pilot core: PF-01.02, PF-02.01, PF-02.02, PF-04.02, PF-04.07, PF-05.02, PF-06.01, PF-07.02, PF-09.02.
2. Visible breadth: PF-06.04, PF-06.03, PF-07.03, PF-07.06, PF-08.02.
3. Later: PF-01.05 with a visual builder, PF-02.03, PF-10.05.

Verify North rows against Cohere's own documentation before using any of them in product or competitive claims.
