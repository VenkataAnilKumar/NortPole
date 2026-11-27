# NortPole horizontal Agents delivery plan

**Status** — All five core agents passed the local rehearsal retest with disposable accounts after the Reporting fix. Real pilot enrollment remains pending. [Reporting retest](#reporting-grounding-and-latency-retest)

**Goal** — Make Agents a core NortPole feature. A teammate can find a trusted agent by the work they need done, launch it in Chat, verify its evidence, and save the result to Projects. A builder can test an exact configuration and publish it to a defined audience.

**First release** — Research produces a cited briefing from accessible Knowledge. Document Analysis compares selected documents and cites the evidence for each finding. Both are read-only horizontal agents. Later horizontal releases add Reporting, Spreadsheet Analysis, and Meeting Follow-up. External writes and scheduled or event-driven runs follow once approvals and run identity have been verified. Vertical packs configure the same platform with their own inputs, evidence rules, and output templates.

[Horizontal agent catalog](NortPole_Horizontal-Agent-Catalog.md)

## Phase 1 — Requirements

**Deliverable** — Approved scope, user journeys, and a permissions matrix.

- **Discovery.** Keep Starred, Mine, Shared, and Company. Search names, descriptions, and labels so people can find agents by purpose. Company reflects company-wide availability. Verified marks an explicit review of a published version. Cards show purpose, maintainer, examples, and Open in Chat.
- **Authoring.** Extend the existing editor. Support templates and fields for instructions, starters, Knowledge, Skills, eligible Integrations, model policy, and expected output. Builders keep a private draft and can invite designated testers.
- **Testing and release.** Test in Chat with example inputs and expected results. Show citations, allowed tool calls, blocked actions, latency, and usage when available. A tester runs with their own account. Preview the intended audience and publish the exact tested configuration. Support rollback and record the agent version used for each run.
- **Access.** Distinguish Can run, Can edit, and Can publish. Grant changes to the runtime audience through a separate sharing capability. Check agent access on each new turn, including in open chats. Apply the caller’s current source permissions to fresh retrieval and to source-backed context reused from earlier turns. The pilots use permissioned Knowledge. Agent-uploaded files are outside the pilot.
- **Evidence and outputs.** A result cites authorized sources, distinguishes findings from missing evidence, and can be saved as a Project output using existing project access rules. Document Analysis accepts only documents the caller can open.

**Review gate** — Agree on the two pilot agents, the capability matrix, which actions remain outside the pilot, and the test fixtures needed for different access levels.

## Phase 2 — Design

**Deliverable** — Annotated flows for a runner, a builder, a tester, and an authorized publisher, including loading, empty, denied, and revoked states.

1. **Find and run.** Agents → Company or Shared → Agent details → Open in Chat. The details show starters, maintainer, published version, and verification status. Chat displays citations and an option to save the result to a project.
2. **Build and test.** Agents → Create or Edit → Test in Chat. A private preview identifies the test candidate and test account, reports sources and tool decisions, and distinguishes a blocked action from a missing connection. Publishing a newer draft requires a test of that candidate.
3. **Publish and recover.** Preview the exact candidate, test results, and audience. Publishing requires the appropriate capability. Version history shows what changed, who published, and who tested. Rollback previews the target version and identifies open conversations affected by withdrawing a version.
4. **Handle access changes.** If someone loses access, explain why they cannot continue the agent conversation and offer a route to regular Chat. Existing chat history follows chat access rules. If a source permission changes and prior context cannot be reused safely, stop the new turn before model or tool execution and offer a fresh conversation without carrying over the prior context. Explain unavailable sources without revealing restricted titles, excerpts, links, or identifiers.

**Review gate** — Walk through discovery, test, publication, revocation, and rollback using the proposed screens. Include a builder who can edit and test but cannot broaden the audience or publish.

## Phase 3 — Architecture

**Deliverable** — Architecture decision and migration notes covering state, authorization, runtime, and compatibility.

- **Identity and versions.** Keep the existing stable agent identity. Store mutable drafts separately from immutable test candidates and published configurations. Bind tests to the exact candidate and record the active version through an atomic publication change. Keep access grants and current admin policies outside the configuration so rollback cannot restore obsolete permissions. Activate a version only when its test is valid for the exact candidate and current dependency fingerprint.
- **Test validity.** Record the candidate fingerprint, resolved model route and model revision where exposed, skill versions or content hashes, and tool definition versions or hashes. A changed effective model or route, skill, tool definition, or configured Knowledge scope requires a fresh test before activation. Keep live Knowledge contents and membership dynamic. Recheck current access and policy at publish, rollback, and execution, and deny use when the configured dependency is no longer allowed.
- **Chat execution.** Use the existing Chat and tool runtime for both previews and published agents. Authorize the specific mode and agent at the server on every turn. Record actor, agent, version or test candidate, outcome, and available timing and usage data. Keep credentials and source contents out of those records.
- **Conversation continuity.** Pin an existing conversation to its initial published version while that version remains eligible. New conversations use the current published version. Rollback activates the selected version for new conversations and withdraws the version being rolled back. Further turns using a withdrawn version stop and direct the runner to a fresh conversation.
- **Runtime checks.** Effective access is the intersection of the agent configuration, current workspace policy, the runner’s access, and downstream permissions. Check configured Knowledge and explicitly selected documents. Use the existing tool-policy checks with a read-only allowlist for the pilots. Publish, rollback, re-share, and draft preview have separate server-side checks. Draft preview cannot perform external writes. For the pilot, track the source revisions behind retrieved evidence, citations, file references, source-backed turns, and summaries. Revalidate that provenance before constructing the next model context. Reject continuation when access is revoked or provenance cannot be established confidently. A fresh chat starts with newly authorized retrieval.
- **Existing endpoints and audience.** Apply the same server-side capability checks to existing and new paths. Route legacy configuration edits for enrolled agents to drafts. Use existing share and visibility endpoints only for authorized audience changes. Activating a tested version requires publish authority, and widening the audience during publication also requires sharing authority. Enforce these rules for direct API calls and administrative paths.
- **Compatibility and packs.** Preserve existing agent IDs, chat links, and access grants during migration. Inventory uploads and enroll only eligible Knowledge-backed configurations. Agents with uploads remain outside versioned publishing until the owner reviews the inventory and replaces those uploads with permissioned Knowledge or removes them from the candidate. Any future inclusion of uploads requires explicit audience approval before publication. Keep existing pack workflows on their established execution path. Map pack declarations to the same agent configuration and permission model as the horizontal lifecycle expands.

**Review gate** — Sign off on the migration and rollback policy, the handling of agent-uploaded files, and who can broaden the audience. Confirm the design reuses the existing runtime and respects the A7 tool-policy and pack decisions. [A7 architecture and agreed direction](NortPole_A7-Agents-Skills-Connectors-Design.md#11-agreed-direction-2026-11-13-govern-the-core-do-not-rebuild-it)

## Phase 4 — Implementation

**Deliverable** — Incremental changes to the existing Agents experience and two pilot configurations ready for internal testing.

| Increment | Work | Completion evidence |
| --- | --- | --- |
| A. Runtime access | Add agent checks to new and existing Chat turns. Validate prior source-backed context before reuse, enforce the pilot’s Knowledge and tool bounds, and exclude agent uploads from pilot candidates. | Permission and revocation regressions pass through Chat and its API. A revoked source cannot be reused through a prior response, summary, or file reference. |
| B. Catalog and launch | Fix Company filtering, add description search, and improve cards, details, starters, and launch. | A runner can find and start both pilot agents. Company and Verified reflect separate rules. |
| C. Draft, test, publish | Apply the capability model to existing and new endpoints. Add Test in Chat, dependency fingerprints, version history, atomic publish, rollback, and run attribution. Migrate eligible agents and flag uploads for owner review. | Direct API calls obey draft and audience controls. Only a candidate with current test evidence can go live, including on rollback. |
| D. Pilot and observations | Configure Research and Document Analysis, connect citations and Project output saving, and expose failures, quality feedback, latency, and usage by version where available. | Both pilots complete a meaningful task and generate evidence the team can review. |

Work is staged in the current draft. Release or environment publication is a separate decision.

### First delivery increment

Chat now checks current non-default agent access before reserving a turn or loading its model and files. The catalog searches descriptions along with names and labels. Company shows listed, company-wide agents. The existing card and detail actions open Chat.

At this increment, runtime access covers agent revocation. Evidence revalidation is tracked in the subsequent implementation notes.

Verification passed the workspace TypeScript check, 13 focused backend tests, and five frontend tests. The PostgreSQL regression covered removal of a direct agent share. Chromium checked Company visibility, description search, and launch into Chat. A live Chat request after removal of an agent was blocked before any message was created.

### Search evidence across turns

Chat records the document and chunk references, the explicitly selected library when present, and fingerprints of the titles and excerpts used in each response that takes evidence from Search. A follow-up rechecks the selected branch before model setup or message creation. The lookup uses the current source, library, and document permissions. If access is gone, the excerpt or title changed, or a detected older Search citation lacks provenance, the user can start a fresh chat. This check also covers earlier evidence that reached a response without an emitted citation.

The database migration adds a nullable provenance field to chat responses. It stores references and fingerprints. This first delivery covered explicit evidence selected in Search.

Verification passed 64 focused tests. The live API used an isolated private Search document in two successive turns and then returned HTTP 403 before creating a message after its source grant was revoked. The local database migration was applied.

### Retained Knowledge, files, and temporary chat

The branch check also reauthorizes indexed source references from stored tool results and from Knowledge provided directly to the model. It checks current index permissions and applies the source’s existing read-time authorization. For workspace files and ingested sources it also checks current database grants, so stale index entries cannot preserve access. Evidence retrieved from explicitly selected Knowledge libraries stays subject to those libraries' access and membership.

Chat records the project and agent files available to a response as file row and blob IDs. It checks the earlier file references against the files currently available for that agent and project. Removing the file or replacing its blob stops use of the old evidence. These checks happen before model setup and new message creation.

Temporary chat saves source references in the existing Redis session state. It keeps references to ancestors that may still contribute through a summary. The response row in PostgreSQL omits this provenance under content-free recording, and ending the temporary session clears the Redis data.

An explicit Search handoff runs with the selected evidence and citations with chat tools and code execution disabled. Chat still rechecks that evidence before a later turn reuses it.

Verification passed 279 focused backend tests, 13 frontend tests, and the workspace type check. Live API checks covered a revoked Knowledge grant, an unlinked project file, and removal of temporary-chat evidence on session teardown. The affected follow-up turns stopped before message creation.

### Test in Chat

The editor opens a private Chat session from an unsaved configuration. The session stores its own instructions, reminders, search cutoff, Knowledge library IDs, and model configuration ID. An empty model choice uses the workspace default at the time the preview opens. The current tester must have permission to create the agent or edit the existing one. Each turn checks that tester's current permissions and the model and libraries used by the preview.

The first preview supports text and indexed Knowledge. It disables actions, federated retrieval, code execution, uploads, and automatic personal memories. Preview conversations use the normal Chat transcript and citations. Sharing or moving a preview to a project is blocked. Existing agents are saved through their normal editor flow.

Verification passed 273 focused backend tests, 28 frontend tests, and the workspace type check. Chromium opened a preview from the editor with unsaved instructions and sent a message. Live API checks covered creation, viewer denial, preview privacy, pinned runtime configuration, Knowledge grounding, and revocation.

### Versioned publishing and rollback

An eligible saved agent can opt in from **Version history**. An owner or agent administrator reviews a completed preview and publishes its exact runtime configuration to the agent's existing audience. Existing editors can save a separate draft and test it. The server rejects a test that differs from the saved draft, fails to complete, or has a stale dependency fingerprint. The fingerprint covers the fixed model, its provider route, the workspace prompt, and the candidate's Knowledge library IDs. Library contents and access remain live.

Chat pins new sessions to the active version. Normal publication keeps older versions available to existing pinned conversations. Restoring an earlier eligible version withdraws the current one. A conversation on a withdrawn version or started before version enrollment remains readable and requires a fresh chat to continue. Publishing and rollback leave audience grants in place. Changing a versioned agent's audience requires the owner or an agent administrator.

Verification passed 279 focused backend tests, 31 frontend tests, and the workspace type check. The live API used a disposable private agent and separate editor and owner accounts. It checked completed-test eligibility, stale draft rejection, concurrent publication, version pinning, and withdrawal before message creation. Chromium verified publication from Version history and the transition to Save draft.

The first versioning increment covers read-only Chat with indexed Knowledge. It excludes agents with actions, uploads, or direct attachments from enrollment.

### Company verification

A workspace administrator with global **Manage Agents** permission can open **Version history**, review the active version of a Company-listed agent, and select **Verify version**. NortPole checks that the version is still active and that the reviewer can access its configured Knowledge and model route. It records the reviewer and date on that specific release and writes a governance audit event.

The catalog card and agent details show **Verified** while the reviewed version is active and available in the Company listing. Each newer version starts without verification. Rolling back to an earlier version with an existing review restores that version’s badge. Administrators can remove verification from current or historical versions in Version history.

Local tests verified the permission gate, exact-version review, stale requests, the effect of a new version, rollback, unlisting, and removal. The PostgreSQL check used an isolated transaction and rolled back its fixtures.

### Versioned pack agents in Chat

Evidence Brief 1.1.0 defines **Evidence Research** as its first read-only Chat agent. For an active, signed pack, **Prepare Chat agent draft** opens the agent editor with the pack’s instructions. The owner selects permissioned Knowledge and a model, saves the candidate, and runs **Test in Chat**. Version history shows the signed pack version on both the test and the release.

Staging a newer version of the pack reuses the same owner’s agent and carries over its Knowledge and model choices. A release requires a test of the new candidate. Publishing a test of a superseded pack version is rejected. Existing chats keep their pinned version. Rollback uses the earlier signed configuration and applies the existing withdrawal behavior.

Chat revalidates the exact pack signature, signer status, model route, and data class before using the pinned release. The editor shows the signed instructions as read-only. The pack’s workflow templates continue to use their established launch flow.

### Research and Document Analysis pilots

Choose a template under **Agents → Create**, attach accessible Knowledge libraries, and save the agent. Run **Test in Chat**, then activate the tested candidate through **Version history** when ready. Both templates start on the existing private test and versioned publishing path.

- **Research** retrieves from the configured indexed libraries and asks for a briefing with findings, citations, and evidence gaps.
- **Document Analysis** requires an explicit selection of up to five documents per turn. It uses one indexed passage per document. A missing or inaccessible selection stops the turn before the user message is saved.
- Completed published pilot answers can be saved as Markdown documents through the existing Project output permissions. Chat lists any supplied sources that the model omitted from its inline citations. Saved outputs preserve links when available.

The local smoke run used two synthetic policy revisions through preview and published versions of both templates. It checked grounding, missing and inaccessible selections, revocation during a conversation, and the Project output round trip. The small local model omitted inline citations in one Research run. The evidence list shows what was supplied so a reviewer can verify the briefing. Chromium verified the two template choices. The workspace type check, 281 focused backend tests, and 44 frontend tests passed. Internal quality review still needs representative tasks and agreed citation, latency, and cost thresholds.

In the final smoke run with the warmed local model, Research completed in 19.5 seconds and showed two supplied sources. Document Analysis completed in 3.4 seconds and emitted two inline citations. These are individual runs against synthetic documents. Token usage and cost were outside this smoke run.

### Internal evaluation

The evaluation uses two synthetic supplier onboarding policy revisions. Revision 1 assigns standard approvals to Procurement within five business days. Revision 2 assigns them to Vendor Operations within three business days. Both require Compliance review before activating high-risk suppliers. Neither specifies an appeal deadline. The full-access account can read both revisions. A separate runner can open each published agent and read revision 1.

The review checks each answer against those facts, checks which passages support each inline citation, and checks whether the assistant states evidence gaps. It also checks whether the restricted runner receives only authorized text and source metadata and whether Project permissions govern output saving. The 78 focused authorization, retrieval, Project output, and release tests passed. The sample assesses behavior in the local environment. Wider pilot enrollment and service-level targets require separate review.

Both published agents ran at version 1 on the local Qwen 2.5 1.5B model. Latency is elapsed time for the local Chat API request.

| Task | Research | Document Analysis |
| --- | --- | --- |
| Full access comparison | Retrieved both revisions. Omitted the two deadlines and Procurement's role in revision 1, invented an initial publication year, and conflated emergency exceptions with appeals. 25.78 s. | Retrieved both revisions and identified the owners and the shared Compliance rule. Omitted both deadlines and answered the revision 2 appeal question with the emergency exception rule. 12.95 s. |
| Restricted comparison | Retrieved revision 1 only. Misattributed its five-day deadline to revision 2 and high-risk suppliers. 28.45 s. | Retrieved revision 1 only. Invented details for revision 2 and applied a five-day deadline to high-risk suppliers. 17.91 s. |
| Missing appeal deadline | Correctly reported the gap. 20.54 s. | Correctly reported the gap. 10.63 s. |

The restricted runner received only the accessible revision in the retrieved source metadata for both agents. Document Analysis rejected a mixed selection with HTTP 400 before saving a user message. The runner was denied access to the private previews and writes to the owner's private Project. The owner saved and reopened each agent's output. All successful turns produced zero tool calls.

None of the six scored answers emitted a resolvable inline citation. Supplied-source links remain available for review. The two evaluation accounts reported 7,840 input and 1,908 output tokens across the scored turns and two preview runs. The recorded local inference cost was zero and excludes infrastructure cost.

Both agents passed the tested access checks. Both remain below the answer-quality bar for wider enrollment on this model. Re-evaluate under the chosen model and runtime configuration before wider enrollment using a corpus that requires complete comparisons, accurate distinctions between policies, and claim-level citations. An inaccessible revision must be reported as unavailable.

Two direct Ollama probes used the same passages with a stricter response format. Qwen 2.5 3B avoided inventing facts about revision 2 in the restricted case, but omitted the explicit availability statement and failed to attach citations to the comparison findings. Qwen 3 4B reached the probe's output limit before completing both responses. These probes bypassed NortPole's runtime and do not qualify either model for rollout. The workspace model configuration was not changed.

### Verified excerpts in Document Analysis

Document Analysis renders findings directly from the currently selected, authorized passages. It groups excerpts by source and generates the citation markers on the server. Short indexed passages are shown in full. For longer passages, the model can select numbered lines from the supplied text. The server discards references outside that selection and falls back to the supplied passage when there is no usable selection. An answer with a single source states that other documents or revisions are unavailable for comparison.

The two-account retest used the same supplier onboarding fixture and normal Chat API. The full-access response contained both owners and deadlines, the Compliance rule, and the absence of an appeal deadline in two cited passages. The restricted response contained only revision 1, its citation, and an explicit coverage gap. The mixed-access selection and the follow-up after revocation were rejected before a user message was saved. The Project output round trip and 265 focused tests passed. The three short-passage responses finished in 0.19 to 0.21 seconds without a generation call.

A second two-account run used a longer revision 1 passage. The full-access answer returned selected lines and two citations in 10.30 seconds. The restricted answer showed the longer passage as fallback with one citation and an explicit coverage gap in 1.50 seconds. These timings are local fixture measurements.

This implementation first presented verified excerpts grouped by document. The comparison section below records the subsequent synthesis work.

### Verified excerpts in Research

Research uses the same verifier after searching the configured Knowledge libraries. The brief uses the current turn's retrieved excerpts, groups them by document, and renders citation markers on the server. Multiple passages from a single document count as one source for coverage. If retrieval returns no verified passages, the brief reports that gap.

In the live supplier onboarding retest, the full-access runner received both revisions and both citations. The restricted runner received revision 1 and its citation, with an explicit comparison gap. A fresh request after both source grants were revoked reported no verified passages and returned no source metadata or citations. The follow-up from the earlier conversation returned HTTP 403 before a user message was saved. The authorized Research output saved and reopened, and the restricted user was denied the same Project write.

The four successful Research requests took 0.41 to 0.54 seconds locally. The short-passage fixture used no generation calls. The 260 focused tests passed, including grouping, missing evidence, restoration, and both pilot paths.

### Verified comparisons

Document Analysis and Research add a comparison section when the question asks for one and the current evidence supports it. NortPole derives differences and agreements from explicit labeled values, narrowly matched approval and review clauses, and statements repeated verbatim across sources. Each comparison field needs one unambiguous value from every represented document. Comparisons cite each contributing document, and the source excerpts remain available below.

The supplier-policy retest checks both approval owners and windows, the shared pre-activation Compliance review, and the shared absence of a specified appeal deadline. It uses both pilot types and two permission levels. The one-source account receives its authorized excerpts and a coverage gap. Focused tests also check ambiguous values, qualified policy text, ordinary lookups, and the distinction between business and calendar days.

Both supplier runs passed. A second live Document Analysis run compared service agreements and preserved the distinction between 30 calendar days and 30 business days. It identified the shared 12-month term and payment statement. The three full-access comparison requests took 0.22, 0.49, and 0.27 seconds locally. Restricted-source handling, revocation, Project output permissions, and 264 focused tests passed.

### Broader corpus check

The local API evaluation used disposable synthetic document pairs for both pilots. No approved internal evaluation corpus was available in the workspace.

| Fixture | Observed behavior |
| --- | --- |
| Markdown incident runbook | Both pilots cited the change from 15 to 10 minutes and the shared quarterly review cadence after the verifier learned to read labeled Markdown list items. |
| Access-review prose | Both pilots cited the shared security check and kept the qualified approval window in the excerpts. |
| Conflicting reimbursement policy | Both pilots compared the reporting deadlines and kept the conflicting reimbursement limits in the excerpts. The comparison preserved business and calendar day units. |
| Change-control table | Both pilots returned cited excerpts. Structured comparison of table rows remains outside the verifier’s current coverage. |

All eight API scenarios passed. Each full-access run cited both revisions, and each restricted run cited only the permitted revision. The API checks also covered draft isolation, source revocation during a conversation, and permission checks on saved Project outputs. Document Analysis rejected mixed selections containing a restricted source before saving the chat message. The 28 focused automated tests passed for this baseline.

### Repository document evaluation

The draft evaluation used excerpts from four NortPole documents in disposable local libraries with the local model. The Search question checked when access is revalidated and how the cited Chat handoff handles a revoked source. The Workflows question checked whether saving a draft dispatches work and how an agent proposes a schedule run for user confirmation.

| Question | Repository sources |
| --- | --- |
| Search access and revocation | [Enterprise Search PRD](../04-specs/NortPole_Enterprise-Search-PRD.md#retrieval-and-permissions) and [Enterprise Search implementation plan](NortPole_Enterprise-Search-Implementation-Plan.md#release-3--cited-chat-handoff) |
| Workflow execution and confirmation | [First workflow PRD](../04-specs/NortPole_First-Workflow-PRD.md#2-primary-user-journey) and [Enterprise Workflows plan](NortPole_Enterprise-Workflows-Plan.md#requirements) |

The Research baseline cited both Search documents but selected sentences that omitted the permission recheck and revocation behavior. Comparison requests now show the retrieved passages within the existing retrieval limits. The verifier still generates structured findings for the explicit fields and repeated statements it can substantiate. The repository questions use the cited excerpts because their answers are expressed in prose.

All four API retests covered the expected evidence in both documents. Restricted users received only their permitted source. After revocation, the existing conversation rejected the follow-up before saving a user message, and a fresh chat cited only the remaining source. Private test previews and Project outputs enforced their access checks. The 29 focused automated tests passed for the excerpt-based evaluation.

### Full-document retrieval evaluation

The same four repository documents were indexed in full in the local draft. The baseline Research answers each cited one of the two accessible documents. Document Analysis cited both title-search selections, which pointed to the opening passages. Those passages contained one of the four expected facts across the two comparisons.

Research now considers more ranked candidates, reserves the same share of available model context for evidence as Document Analysis, and budgets the strongest passage from each document before considering additional passages from already represented documents. Authorization is checked for every passage included in the turn.

| Full-document comparison | Research after the change | Document Analysis with topic-specific selections |
| --- | --- | --- |
| Search access and revocation | Cited both documents. The passages omitted both expected clauses. | Cited both documents and included the expected Chat handoff clause. The Search PRD clause was missing. |
| Workflow execution and confirmation | Cited both documents and included both expected facts. | Cited both documents and included both expected facts. |

The targeted Search PRD pick found the correct indexed passage. Its permission-recheck sentence started after the 1,800-character cutoff for selected evidence and was omitted from Chat.

All four API runs at this checkpoint cited both accessible documents. Restricted users saw only the permitted source, follow-ups failed after revocation, and fresh chats cited only the remaining source. The Project access checks and 35 focused automated tests passed.

### Full-document retrieval fixes

Document Analysis includes the full selected index passage when it fits the existing token budget. Under a tighter budget it selects a relevant sentence from that passage. New turns store the offsets used to verify the exact evidence on follow-up. Older turns continue to revalidate the original excerpt and current source permissions.

Research retrieves candidates for the individual parts of a comparison question and the original question. It ranks nearby sentences by how well they cover each topic and the subjects named in the comparison. Results still prioritize distinct documents and revalidate the passages included in the answer.

All four final API retests supplied the expected evidence with citations to the corresponding documents. Research found both Search clauses from the original question. Document Analysis preserved both after topic-specific selection, including the sentence beyond the previous cutoff. For Workflows, both pilots cited the explicit start and user confirmation requirements. Research cited the implementation section for confirmation.

Authorized follow-ups succeeded, revoked follow-ups were rejected before saving a user message, and fresh chats cited only the remaining authorized source. Project access checks and 98 focused automated tests passed. The retests used locally indexed repository documents. Live connector validation remains open.

### Research Drive permission checks

Research checks Drive candidates against the configured pilot library and the signed-in user's current named Drive grants before ranking excerpts or returning citations. It uses the authorized Drive link and withholds passages it cannot verify. When a conversation reuses Drive evidence, Research repeats the live check before saving the follow-up or preparing a model request. A revoked source requires a fresh chat.

The integration test uses real library and document records, a stale index response, and a simulated Drive permission provider. It verifies permitted citations, an unauthorized user, library scope, revocation during a conversation, and a provider outage with an authorized local source still available. The 80 focused automated tests passed. The draft API also passed both full-document Research comparisons using locally indexed sources. A connected Drive test library is needed for live validation.

### Reporting in Chat

The draft includes a **Reporting** template under **Agents → Create**. In Chat, choose a start date, an end date, and one or more available Knowledge sources. The agent returns a status report with sections for progress, metrics, blockers, next steps, and evidence gaps. Runs use their selected sources for retrieval. Previous report text stays out of model context. Completed reports from released agents use the existing Project output flow. Signed packs can configure the same Reporting template.

Local Support and Finance previews on the same agent retrieved distinct synthetic source documents and returned an inline citation for each report in the final run. PostgreSQL tests checked library selection for accounts with different access and the signed pack version lifecycle. The API check rejected malformed input and revoked evidence before saving a user turn, and verified Project output access. Chromium checked the template picker and the reporting period and source controls.

### Spreadsheet Analysis in Chat

The draft includes a **Spreadsheet Analysis** template for one CSV or XLSX attachment per turn. It reports numeric totals, changes in row order, missing values, duplicate rows, and potential outliers. The report identifies columns and refers to rows or CSV records for flagged findings. Excel formulas and error cells are flagged and skipped. Workbooks and CSV inputs are bounded by file, sheet, row, and column limits. The agent uses the current user's upload access and computes the report directly from the file.

Local API checks uploaded CSV and XLSX fixtures, verified exact totals and formula handling, rejected an attachment with a mismatched file ID, and saved and reopened the result via Projects. An isolated PostgreSQL check verified version pinning for the template without configured Knowledge. Chromium verified creation, Test in Chat, CSV upload, and the rendered total.

### Meeting Recap in Chat

The draft includes a **Meeting Recap** template for pasted notes and transcript text. Each turn uses its own input to list decisions, commitments, and open questions. Items cite the note by line number. Owners and due dates are copied from the supporting line or marked **Not stated**. Explicitly labelled notes are handled directly. For other notes, the model selects and classifies lines for review. Completed recaps from released agents use the existing Project output flow.

Local API checks covered labelled and unlabelled notes, input limits, separation between two meetings in the same chat, test eligibility, and the Project output round trip. Chromium verified creation, Test in Chat, multiline input, and a rendered action item. PostgreSQL tests covered version pinning without a Knowledge library.

## Phase 5 — Test

**Deliverable** — Automated results, an authenticated browser walkthrough, and a pilot evidence report.

| Scenario | Pass condition |
| --- | --- |
| Same version, different access | Two signed-in teammates run the same published version and receive results, citations, and source metadata limited to what each can access. Fresh retrieval reflects source revocation. |
| Source access revoked mid-conversation | Start a chat with an accessible source, then revoke access and send a follow-up in the same chat. The new turn stops before model and tool execution and offers a fresh-chat option. The fresh chat uses only newly authorized evidence and carries over no prior excerpts, citations, metadata, or file references. |
| Agent access revoked mid-conversation | The next turn is rejected through Chat and its direct API. No retrieval or tool call runs for that turn. |
| Draft access and isolation | A runner cannot open a test candidate through a direct link. Authorized testers use their own access. Draft edits leave the published behavior unchanged. |
| Existing endpoint authorization | Legacy configuration edits update only the draft for an enrolled agent. Direct edit, share, and public-visibility requests by a user without the corresponding authority cannot change the active version or audience. Publishing can widen access only with sharing authority. |
| Migration with uploads | An existing shared agent with uploads retains its ID and chat links. It stays outside versioned publishing until the owner resolves the uploaded files. The resulting pilot candidate uses permissioned Knowledge with separate caller checks. |
| Publish and rollback | An editor without publish permission is denied. An altered draft or changed model, skill, tool definition, or Knowledge configuration invalidates the relevant test. Concurrent writes resolve consistently. Rollback rechecks current policy and test validity, and the withdrawn version stops serving new turns. |
| Research and Document Analysis | Research produces a verifiable briefing. Document Analysis cites findings across permitted documents and accounts for missing evidence. Both can save outputs under the existing Project ACL. |
| Read-only and compatibility | Preview and published pilot requests cannot execute external writes. Existing private and shared agents, direct chat links, and pack workflow launch paths pass regression checks. |

Run focused backend and frontend suites, the workspace type check, and the browser walkthrough using independent user accounts. Record model and version, quality findings, latency, and available usage. Agree on quality thresholds with pilot reviewers using representative tasks.

### Authenticated browser walkthrough

Headless Chromium exercised both pilots through Test in Chat, Version history, a released chat, and Project output save and reopen. The disposable owner and restricted accounts had different access to two synthetic policy documents. Browser clicks opened the expected citation destinations. The restricted account received only its authorized source and could access neither the owner's preview nor the owner's saved Project outputs.

The walkthrough exposed a missing Save to Project action on the first reply in a newly created released-agent chat. The create-session endpoint now returns the server-pinned version, and the workspace initializes the new chat with it. Both pilots saved their first reply without a page reload on retest. The workspace type check, 16 frontend tests, and 90 backend tests passed. Live Drive validation remains open.

## Phase 6 — Review

**Deliverable** — A review record with decisions, evidence links, owners, and any remaining issues.

- **Before implementation.** Review the scope, screen flows, ownership and publishing rules, migration, and acceptance criteria in this proposal.
- **Before internal pilot.** Review same-chat source revocation, legacy endpoint authorization, owner review of uploads, dependency test freshness, version integrity, and rollback. Resolve issues that could disclose data, execute a write, or activate an untested version.
- **Before wider rollout.** Review actual pilot tasks and feedback, decide where each agent is listed, and confirm how to withdraw a version and how to route support. Prioritize subsequent horizontal agents and action-enabled Workflows using the pilot evidence.

**Decisions for this review** — Who can publish or verify a company agent and which teams and permission sets should take part in the pilot. The proposed defaults are workspace-authorized publishers, admin verification, permissioned Knowledge for both pilots, and two pilot accounts with intentionally different source access.

### Pilot readiness record

**Decision** — Recommend a small, read-only internal pilot with indexed Knowledge after the workspace owner confirms the audience, the release owner, and the evaluation criteria. A pilot that includes live Drive also needs connector validation. Wider enrollment and Company verification remain separate decisions.

| Area | Evidence from the current draft |
| --- | --- |
| Release integrity and recovery | An editor could test a candidate, and only the owner could activate it. An altered draft was rejected. Concurrent publication activated one version. The create-session response matched the pinned version. Rollback restored the earlier version for new chats and rejected follow-ups on the withdrawn version before saving a message. |
| Existing agents with uploads | The presence of an upload blocked version enrollment on a disposable shared agent. Detaching the test upload restored eligibility with the same agent ID and existing chat link. A real agent's owner still needs to review its uploads before enrollment. |
| Permissions and output handling | The draft tests covered agent-share revocation, source revocation, preview isolation, and Project access. The authenticated browser walkthrough verified citations and Project save and reopen for both pilots. |
| Connector status | Automated checks used simulated Drive permissions with stale index data. A connected test library and two verified Drive users are needed to measure live revocation and link behavior for both pilots. |

The review reran 91 focused tests and both local API checks for the release lifecycle and upload eligibility. The [full-document retrieval results](#full-document-retrieval-fixes) and [browser walkthrough](#authenticated-browser-walkthrough) cover representative local content and the editor-to-chat path.

| Open decision | Proposed owner | Completion evidence |
| --- | --- | --- |
| Select the pilot audience and libraries | Workspace owner and Knowledge owner | Agree which users can run each pilot and which indexed libraries they can inspect. Exercise full and limited source access with the chosen accounts. |
| Assign publishing, rollback, and support | Workspace administrator and agent owner | Name the individuals responsible for activation, withdrawal, and handling pilot issues. |
| Set quality and operating targets | Pilot reviewers and engineering | Agree on representative tasks, expected findings, and citation checks. Record missing evidence, p95 response time, token usage, and per-run cost on the pilot configuration. |
| Enable live Drive in a pilot | Connector owner and workspace administrator | Connect a test library, check both users' citations and original links, then revoke one grant and verify Search, follow-ups, and fresh chats. |

### Indexed Knowledge pilot rehearsal

The local draft rehearsal uses Research and Document Analysis, the four full NortPole Search and Workflows documents, and disposable accounts with full and restricted source grants. The owner compares two documents, asks a direct factual question, and asks for a fact outside the library. Document Analysis uses the topic-specific picker selections for scored comparisons and lookups. The restricted run checks source visibility and Project output access. Each comparison also checks an authorized follow-up, a revoked follow-up, and a fresh chat after revocation.

Comparison evidence must include the expected findings and a citation to the corresponding source. A lookup should surface the requested fact, and a question outside the library should say when the evidence cannot answer it. The rehearsal records local API latency, available usage, and whether permissions hold independently of the quality score. Production limits depend on measurements from the intended deployment and model.

| Task | Result | Observed local API time |
| --- | --- | --- |
| Compare two authorized documents | Both expected findings and their source citations appeared in all four scored comparisons. | 0.18–0.56 s |
| Look up one known fact | The expected fact and its citation appeared in all four lookups. | 14.97–43.34 s |
| Ask for an employee travel allowance outside the library | Both responses showed unrelated excerpts and neither explicitly said the library could not answer. | 11.26–46.57 s |

The restricted account received only its permitted source in all four scenarios. Authorized follow-ups worked, revocation blocked follow-ups before saving the user message, and fresh chats cited only the remaining source. Project output checks passed. The local model recorded 8,832 input tokens and 531 output tokens across the rehearsal, including previews, with zero provider charges recorded. Infrastructure cost was outside the measurement. The sample is too small for a production latency target.

The rehearsal used disposable accounts. Real teammate enrollment remains pending.

### Direct lookup and missing evidence retest

Both pilots now select direct lookup excerpts with bounded term matching across nearby sentences. This removes the generation call previously used to select lines. When nothing qualifies, the reply reports that evidence is unavailable and the API omits unrelated excerpts, citations, and source metadata. Comparison requests still use the full eligible retrieved passages within the evidence budget so qualifications remain visible.

| Task | Retest result | Observed local API time |
| --- | --- | --- |
| Compare two authorized documents | All four answers contained both expected findings and the correct citations. | 0.18–0.85 s |
| Look up one known fact | All four answers contained the expected fact and its citation. | 0.18–0.43 s |
| Ask a question outside the library | Both replies reported missing evidence, with zero citations and zero returned documents. | 0.17–0.30 s |

Restricted-source visibility, revoked follow-ups, and Project output checks passed on the same fixtures. The local usage ledger recorded zero generation tokens across the retest, including previews. All 218 focused tests passed. These results measure lexical lookup on the selected local cases. Paraphrase coverage, deployment latency, real teammate enrollment, and live Drive validation remain open.

### Paraphrase evaluation

The draft API tested both pilots against two known facts from the four full Search and Workflows documents. Each pilot received a literal control, three rephrasings per fact, and two questions on nearby topics that lacked answers in the indexed documents. Document Analysis had the same known relevant passage selected for the controls and paraphrases. Research retrieved evidence independently for each turn.

| Question group | Result | Observed local API time |
| --- | --- | --- |
| Four literal controls | Four returned the expected fact and citation. | 0.16–0.40 s |
| Twelve paraphrases | Eleven reported missing evidence. One Research reply cited a retry rule when asked whether saving a draft starts a run. | 0.17–0.41 s |
| Four adjacent questions outside the corpus | All four reported missing evidence and returned no citations or documents. | 0.17–0.35 s |

All four comparison controls and the restricted-source, revocation, and Project checks passed. The paraphrase misses in Document Analysis occurred with the correct passage selected, so improving document retrieval alone would leave that gap open.

### Access and workflow paraphrase retest

An experimental model-based selector recovered six of the twelve paraphrases and selected an irrelevant excerpt for the other six. It took 7.34–15.24 seconds locally. The implementation uses a narrower rule for access rechecks and explicit workflow start. Research normalizes recognized questions for retrieval, and both pilots require the quoted, authorized passage to state the corresponding operation. Other questions continue through the existing lookup path.

All twelve paraphrases returned the expected fact and citation in 0.17–0.38 seconds locally. All four literal controls and the comparison controls passed. All four unsupported questions reported missing evidence and returned zero citations or documents. Revocation and Project checks passed. The usage ledger recorded zero generation tokens, and 224 focused tests passed. This retest covers the two recognized patterns. General paraphrase handling remains open.

### Held-out passage verifier benchmark

The [local benchmark](../../services/core/scripts/benchmark_passage_verifier.py) uses eight synthetic scenarios across access, automation, finance, HR, supplier data, support, and document retention. Every scenario pairs a paraphrased question with an unsupported question that shares its subject and vocabulary. Each verifier sees the same four excerpts and returns one excerpt number or zero. The test supplies the answer-bearing passage in every supported case, so these results isolate verification from retrieval. The twelve previous paraphrases remain the separate pilot regression set.

| Local verifier | Correct supported questions | Correct abstentions | Irrelevant citations | Invalid replies | Observed p95 |
| --- | --- | --- | --- | --- | --- |
| Qwen2.5 1.5B | 5/8 | 5/8 | 3 | 0 | 1.68 s |
| Qwen2.5 3B | 3/8 | 7/8 | 1 | 0 | 3.70 s |
| Qwen3 1.7B | 8/8 | 2/8 | 6 | 0 | 2.01 s |
| Qwen3 4B | 0/8 | 0/8 | 0 | 16 | 4.28 s |
| Qwen3 4B with integer-constrained output | 2/8 | 0/8 | 14 | 0 | 4.65 s |

The receipt question was clarified to ask for a separate reimbursement cap under an approved exception. The affected scenario was rerun for the first three models. Timings are local verifier requests after a warm-up. With sixteen observations per configuration, nearest-rank p95 is the slowest observed request. The existing 25 focused lookup, comparison, and retrieval tests passed.

The benchmark found no candidate that consistently verified support and abstained on near-misses. Constraining output fixed response format for Qwen3 4B and it still selected irrelevant passages. The draft uses the existing lookup rules. Evaluate an answer-support classifier on a new held-out set and then through the normal Research and Document Analysis retrieval paths before enabling a broader fallback.

### Extractive QA and abstention benchmark

The [benchmark runner](../../services/core/scripts/benchmark_extractive_qa.py) evaluates SQuAD 2.0 ONNX readers locally. Each reader scores a question against four passages, extracts a literal span from the best candidate, and compares its score with the model's no-answer score. The previous 16 questions set the lowest threshold that excluded every incorrect calibration citation. The threshold was held fixed for 16 new questions. A supported result had to select the expected passage and an answer-bearing span. A late wording edit made the support question ask which case type to open and the final run used that wording.

| Local reader | Correct supported answers | Correct abstentions | Unsupported citations | Local verifier p95 |
| --- | --- | --- | --- | --- |
| MiniLM SQuAD 2.0 | 0/8 | 8/8 | 0 | 51 ms |
| Quantized RoBERTa SQuAD 2.0 | 4/8 | 5/8 | 3 | 217 ms |

At the default zero-margin threshold, MiniLM found four supported answers and RoBERTa found seven. Both cited five unsupported answers. After calibration, RoBERTa still extracted the first extension's approver for a question about a second extension, an unused invitation's expiration for a question about granted access, and a fee approver for a question about a refund. These passages contain real text about a different condition.

The runs used two CPU threads after warming each reader. The small-sample nearest-rank p95 is the slowest held-out request and measures tokenization and local inference. The model assets were pinned to the [MiniLM ONNX export](https://huggingface.co/lquint/minilm-uncased-squad2-onnx/tree/a7e7389ca93a51306b1410426768e79874da1551) and [quantized RoBERTa ONNX export](https://huggingface.co/onnx-community/roberta-base-squad2-ONNX/tree/6d1aeed784b6386659454d3be72de76fad8b73db).

Neither reader met the support and abstention checks on the held-out set. The draft continues to use the validated lookup rules. The next verifier candidate should check whether the entire question, including conditions and exceptions, is supported by the extracted span. Run that check on new held-out examples before measuring through live retrieval.

### Whole-claim condition benchmark

The [condition benchmark](../../services/core/scripts/benchmark_condition_support.py) tests two local natural language inference models. Each source is paired with a supported claim and a claim that changes a condition. Four pairs calibrate the acceptance threshold, with a floor that requires the entailment logit to exceed both alternatives. Eight new pairs measure support and abstention. The final run clarifies the deadline pair to ask for the exact contractual deadline and unit.

| Verifier | Correct supported claims | Correct abstentions | Unsupported claims accepted | Local p95 |
| --- | --- | --- | --- | --- |
| Quantized DeBERTa v3 XSmall | 6/8 | 4/8 | 4 | 12 ms |
| Quantized DeBERTa v3 Small Tasksource | 6/8 | 7/8 | 1 | 2.11 s |

The Small model rejected the second-renewal, accepted-invitation, refund, and changed-deadline claims. It still accepted a claim that pausing a schedule cancels a manual run already in progress. The source only described prevention of future timer runs and the behavior of starting a run manually.

The benchmark also tests the calibrated RoBERTa reader on its previous 16 held-out questions, followed by each claim verifier. Each question uses a review-authored sentence template that preserves its conditions. The reader's extracted words fill the template. This checks candidate support with the conditions present. Automatic claim construction and live retrieval were outside the test.

| Pipeline | Correct supported answers | Correct abstentions | Unsupported citations | Local inference p95 |
| --- | --- | --- | --- | --- |
| RoBERTa alone | 4/8 | 5/8 | 3 | [See extractive benchmark](#extractive-qa-and-abstention-benchmark) |
| RoBERTa with DeBERTa XSmall | 3/8 | 6/8 | 2 | 0.20 s |
| RoBERTa with DeBERTa Small Tasksource | 3/8 | 7/8 | 1 | 2.06 s |

The runs used two CPU threads. Nearest-rank p95 on 16 observations is the slowest result. Pipeline timings sum the extractive request and the claim check when applied. Model assets were pinned to the [DeBERTa XSmall export](https://huggingface.co/onnx-community/nli-deberta-v3-xsmall-ONNX/tree/e8b96a58cbfed9e8d43932208db32a2a74a98e51) and [DeBERTa Small Tasksource export](https://huggingface.co/techtheist/deberta-v3-small-tasksource-nli-onnx/tree/15a02c00bd7c8c210f9d9b1d41cfff6369b2ebcf).

The draft continues to use its validated lookup rules. For policy questions with high-impact qualifiers, the next candidate is an explicit comparison of action, state, exception, and unit against authored source fields. A missing or mismatched qualifier should produce an abstention.

### Structured policy verifier benchmark

The [benchmark](../../services/core/scripts/benchmark_structured_policy.py) takes an authored rule and a structured claim. It checks the action, required conditions, answer field, value, and unit. A citation also needs an exact excerpt from a current authorized source. If current authorized rules disagree, the check abstains. The benchmark uses synthetic fixtures and a supplied map of authorized passages.

All 28 checks passed. Nine supported cases returned verified excerpts and nineteen abstained. The checks covered first and second renewals, unused and accepted invitations, rush charges and refunds, acknowledgement and resolution, calendar and business days, legal holds, and already-running manual work. They also covered the exact 300 USD boundary, missing qualifiers, stale or revoked sources, and conflicting authorized rules.

The benchmark starts with authored rules and structured claims. The permissioned trial below measures the question and source checks separately.

### Permissioned policy library trial

The [prototype](../../services/core/scripts/benchmark_policy_library.py) interprets a bounded set of contractor-access questions. It preserves the renewal number, the grant state, whether an incident was declared, whether an invitation was used, and the requested unit. It requires explicit fields before matching an authored rule. Qualifiers outside the supported question patterns cause an abstention.

The trial put three synthetic policies in one private, indexed draft Knowledge library shared with two disposable accounts. It found the policy references through the authenticated Search API and revalidated them against NortPole's live evidence resolver for each question. The restricted account could read the ordinary renewal and invitation rules. Only the full-access account could initially read the incident renewal exception.

| Access scenario | Cited answers | Abstentions |
| --- | --- | --- |
| Full access | 7 | 9 |
| Restricted account | 5 | 11 |
| Full-access account after revoking its incident grant | 5 | 11 |

All 48 question and access combinations passed. A direct request with the restricted incident reference returned no evidence. After revocation, the original chunk references could no longer resolve the incident policy, and Search also withheld it. The earlier 28 structured-field checks passed. The trial exercises a scoped interpreter and the permissioned evidence path.

### Authored policy answers in the draft

Knowledge collection editors can open **Policy rules** in the collection details. Each rule records complete accepted question phrasings, an action, any required conditions, an answer field, a value and optional unit, and an exact quote from a selected indexed passage. Editors review how each question maps to its rule. NortPole verifies that the quote and answer appear in the current passage.

Enabling **Require authored policy answers** on a collection switches both pilots that use it to authored answers from their enabled collections. Document Analysis still requires users to select the matching passage. Question matching ignores case, whitespace differences, and a trailing question mark. Additional qualifiers and unauthored phrasings receive an abstention. Collections start with policy mode disabled.

The pilots recheck current access and the source fingerprint for matching rules. Stale evidence and conflicting applicable answers cause an abstention. Evidence the caller cannot access is excluded. Successful answers include the quoted passage and a citation. Continuing the thread rechecks access and the fingerprint of that passage. Editors can replace rules when a changed source is still available to them.

Private draft previews passed 64 question and access combinations across both pilots. Live checks also covered a direct restricted selection, conflicting rules, access revocation, citation-history replay, stale source redaction, and rule replacement. An authenticated Chromium check covered finding a passage, adding, editing, and removing a rule, and toggling policy mode.

### Existing Knowledge collection retest

The draft collection **Sample knowledge — travel policy** contains a sample travel rule for expenses above 25 dollars and a QA expense rule for expenses strictly over $75. The retest used copies of both live indexed passages in a private test collection. It kept their original source links and used two disposable accounts with different source access. The questions were written for the test.

| Pilot and access | Correct citations | Abstentions |
| --- | ---: | ---: |
| Research, full access | 4 | 8 |
| Research, restricted access | 2 | 10 |
| Document Analysis, full access | 4 | 8 |
| Document Analysis, restricted access | 2 | 10 |

All 48 initial cases met expectations. Both pilots withheld evidence for unauthored paraphrases and unsupported qualifiers about currency, travel location, emergencies, and exception authority. The exact-amount question and the ambiguous company-wide question also produced abstentions. Document Analysis rejected a direct restricted selection and abstained when the caller selected only the other passage.

Revoking access to the QA policy blocked citation reuse in existing chats. Fresh chats withheld the QA policy and still answered the travel question. Both pilots answered a phrasing that an editor added to the travel rule. When the private QA copy was reindexed with an $80 threshold, both pilots abstained until the editor refreshed the rule. The original collection settings were verified and the private fixtures were removed.

The remaining answer-quality work includes paraphrases drawn from actual pilot questions, explicit treatment of boundary cases such as an expense equal to the threshold, and broader structured comparisons.

### Authored threshold questions

In **Knowledge → Collections → Policy rules**, choose a threshold comparison and use `{amount}` once per question. For example, use `Does a travel expense of ${amount} meet the receipt threshold?`. Enter `25` as the answer value and `dollars` as the unit, then quote the source clause containing `above 25 dollars`. The rule editor validates the quote against the current indexed passage when saving.

Both pilots compare decimal amounts to the cited limit using the authored operator. With a strict limit of 25, an expense of 25 does not meet it and an expense of 25.01 does. An inclusive operator gives a different result at exactly 25. The reply explains whether the amount meets the quoted threshold and cites the supporting passage.

The surrounding wording still has to match an authored question. Additional qualifiers, changed currency wording, conflicting evidence, and unavailable passages can cause an abstention. Unrelated literal rules continue to work in the same collection.

### Cited table comparisons

Document Analysis compares Markdown tables found in the two selected Knowledge passages. A table must have a header, a separator row, and visible outer pipes for each row. The first column identifies the row. Matching uses that column’s header, the row label, and the compared field’s header. Values can appear in a different column order. Naming a row in the question focuses the comparison on that row.

The comparison shows up to six fields side by side with citations to the selected passages. Equivalent decimal values in the same units are marked as equal. Different currencies, time units, or unclear units are displayed as written and flagged. Missing or clipped cells and duplicate rows are marked as evidence gaps. Document Analysis uses its existing permission and citation-history checks for table evidence.

The threshold-rule editor browser walkthrough also passed on retry. Chromium created a rule and reopened it with the saved comparison.

### Five-agent pilot rehearsal

Two disposable accounts tested private Chat previews on the local **qwen2.5:1.5b** route. Both could open an indexed test collection. The full-access account could read two synthetic Support documents, and the limited account could read one. Each account used its own upload or notes for the input-only agents. The rehearsal removed the disposable accounts, agents, files, collection, source documents, and Project after scoring. These cases used private previews. The regression tests exercised version pinning and rollback in isolated fixtures.

**Result.** The review passed 27 of 32 first-pass checks after comparing generated claims with the source text. The automated checks initially counted 28 passes because they verified source selection and citation IDs without checking every Reporting claim. A separate retry confirmed that a fresh Reporting preview rejects missing period and source inputs with HTTP 400 before saving a user turn. It does not change the first-pass score.

| Agent | Passed / checked | Reviewed outcome |
| --- | ---: | --- |
| Research | 7 / 7 | Both response targets appeared with their corresponding citations for the full-access account. The limited account received only its permitted source. The unsupported travel-allowance question abstained. Authorized follow-up, revocation, and fresh-chat checks passed. |
| Document Analysis | 8 / 8 | Selected passages supported both targets. A selection that included the restricted passage was rejected before a user turn was saved. Supported lookup, abstention, and revocation checks passed. |
| Reporting | 1 / 6 | Both initial reports exceeded the 110-second client window, so the owner obtained no completed test candidate. The next request on the busy limited-access preview returned a processing conflict. Revocation blocked the existing full-access conversation. The fresh report used only the remaining allowed source but added unsupported facts. |
| Spreadsheet Analysis | 4 / 4 | The two CSVs produced totals of 16 and 8. The first report identified a missing value and a duplicate row. The server denied the limited account's attempt to use the other account's upload. |
| Meeting Recap | 4 / 4 | Labelled notes returned the expected decision, commitment, and open question with line references. Unlabelled notes returned the stated owner and due date. Blank notes were rejected before saving a user turn. |
| Shared checks | 3 / 3 | Search withheld the restricted source. The peer could not read the other account's private preview. The Project owner reopened the saved output and the peer's read and write attempts were denied. |

All three Knowledge agents denied follow-ups on conversations whose earlier turns had retrieved subsequently revoked evidence. The scored responses contained no observed restricted-source disclosure or agent tool calls. The Reporting issue was unsupported claims in the answer. The available source supported 43 service tickets and a four-business-hour response target. The report invented 25 priority tickets, a 68-ticket total, a 1.75-hour average, and ticket-specific blockers. Its citation pointed to the permitted source, which contained none of those facts.

| Agent | Completed chat requests | Median local API time | p95 local API time |
| --- | ---: | ---: | ---: |
| Research | 5 | 0.318 s | 0.773 s |
| Document Analysis | 5 | 0.210 s | 0.468 s |
| Reporting | 1 | 39.841 s | 39.841 s |
| Spreadsheet Analysis | 2 | 0.255 s | 0.281 s |
| Meeting Recap | 2 | 12.559 s | 24.929 s |

Timings include all HTTP 200 chat requests, including the Reporting answer that failed review. The nearest-rank p95 equals the maximum at these sample sizes. The two Reporting timeouts are recorded separately. The later request reached embedding while the first expired run was still active. Embedding returned after that run was cancelled. This establishes an overlap during the rehearsal. The deployment still needs a latency test on its intended route and hardware. Recorded usage was 2,012 input tokens, 902 output tokens, and zero provider charges. Infrastructure cost was outside the measurement. The focused access, version, and output regression run passed 48 tests.

The first pass called for a fresh full-access and limited-access Reporting retest with claim-level citation checks. Enrollment also needs the real pilot audience, allowed libraries, release owner, and review criteria. Live Drive is outside this indexed Knowledge rehearsal.

### Reporting grounding and latency retest

Reporting now assembles a fixed-format report from verbatim Knowledge excerpts tied to the selected period. Each finding carries its citation, and sections without dated evidence show a gap. The report uses a date in the statement or an ISO date heading in the same block. It skips the model generation step. Earlier Reporting test candidates require a new test before publication because the renderer changed.

The full five-agent rerun passed **33 of 33 checks** with the restored local PostgreSQL, Redis, OpenSearch, and model services. The Reporting score checked each displayed quote against the exact cited source. The full-access report showed 43 service and 71 priority tickets. The limited-access and post-revocation reports showed 43 service tickets and flagged evidence gaps. An existing conversation that had used the revoked source returned HTTP 403 before saving a user turn. Missing inputs returned HTTP 400. The owner obtained a completed test candidate for the new configuration.

| Successful Reporting request | Local API time |
| --- | ---: |
| Full-access report | 0.353 s |
| Limited-access report | 0.388 s |
| Authorized follow-up | 0.446 s |
| Fresh conversation after revocation | 0.431 s |

The four local observations include Knowledge retrieval. Deployment latency and real teammate enrollment remain open. The backend regression run passed 1,110 tests.

### Internal pilot enrollment runbook

The five-agent retest passed all 33 checks with disposable accounts. Use a named internal audience and approved data for the next run. The proposed starting audience is two teammates who can both use the agents and have different access to one test passage. [Local retest](#reporting-grounding-and-latency-retest)

**Venkata Anil Kumar** owns and published version 1 of Research, Document Analysis, Reporting, Spreadsheet Analysis, and Meeting Recap in the local NortPole workspace using the tested versions in **Version history**. The releases are private. The two synthetic members of **NortPole Pilot Participants** each received a direct **Can use** grant because this edition supports individual agent sharing. Changes to the cohort require updating those grants on each agent. The previous owner retains editor access.

Both participants launched all five published agents in Chat and completed representative tasks. Search and the Knowledge-backed agents showed both synthetic Support documents to Pilot 01 and only the shared service-ticket document to Pilot 02. The **NortPole Pilot Knowledge (Synthetic)** collection remains private. Real teammate enrollment is pending.

#### Confirm before enrollment

| Decision | Accountable owner | Record for the pilot |
| --- | --- | --- |
| Participants and access | Workspace owner | The two participants, their workspace identities or pilot group, and who has full and limited access to the test passage. |
| Knowledge and inputs | Knowledge owner | The approved collection, the source grant that can be revoked for testing, and the approved spreadsheet and meeting notes. |
| Agent release and recovery | Venkata Anil Kumar | Ownership and access to Version history are verified. Record the approved pilot rollout and who handles support. |
| Scoring and review | Pilot reviewer | Expected answers and citations, completion time and cost targets for the intended deployment, and the review date. |

#### Prepare and release

1. Run **Test in Chat** for each agent in the intended workspace. Record the exact candidate and model route. Reporting needs a fresh test with dated evidence after its renderer change.
2. In Search, verify which test passages each participant can access. Use a dedicated test grant for the revocation check and a private Project for the output check.
3. Once the workspace owner approves the audience and authorizes publication, use **Version history → Publish tested version**. Review the agent's existing audience before activation and confirm that its usage grants match the named participants. Both participants open each agent from **Agents** in a fresh chat. Record the version each chat uses.
4. Collect one representative task and its expected answer from each participant. Score the input and access controls independently from answer quality.

| Agent | Representative task | What to verify |
| --- | --- | --- |
| Research | Compare two sources, then ask for a fact outside the collection. | Each supported finding cites the correct source. The limited account sees only the permitted source. The unsupported question abstains. |
| Document Analysis | Compare the selected documents and try a selection that includes a restricted passage. | The comparison carries the relevant qualifiers and citations. The restricted selection is rejected before saving a user turn. |
| Reporting | Report for a defined period with one dated metric per source. | The full-access report shows both metrics. The limited-access report shows only the permitted metric and flags gaps. Every claim matches its citation. The report completes within the agreed window. |
| Spreadsheet Analysis | Upload a CSV or XLSX with known totals, a blank value, and a duplicate row. | The totals and row references match independent calculations. The second participant's attempt to use the first participant's upload is denied. |
| Meeting Recap | Paste approved notes with a decision, an action item, and an open question. | Each item points to its supporting line. Owners and due dates are recorded when supported by the notes. A new turn uses the notes supplied for that turn. |

#### Score and recover

For Research, Document Analysis, and Reporting, revoke the dedicated test grant after an authorized turn. Verify that the conversation rejects a follow-up before saving a user turn. Start a fresh chat and check that it serves the still-permitted evidence. Save and reopen a completed output in the private Project, then check that the other participant's access is denied.

Record agent and version ID, task ID, participant access level, expected outcome, actual outcome, citation verdict, elapsed time, and available usage and cost. Retain sensitive source identifiers and test details in a location with equivalent access. Score supported-task completion separately from abstention. Record median and p95 latency with the sample size, and gather the two participants' feedback on whether they could use each result.

Pause the affected agent if it exposes restricted evidence, cites a source that does not support a finding, or runs an unexpected version. Remove the pilot participants' grant on that agent and verify that their follow-ups are denied. If an earlier tested release is eligible, the release owner can use **Version history → Restore version**. For a first release, keep pilot access paused while the owner prepares and tests a corrected candidate. Record the incident and verify the fix before restoring access.

## Competitive references

- Glean informs catalog discovery and preview before rollout. [Agent Library](https://docs.glean.com/agents/concepts/agent-library) · [Test and launch](https://docs.glean.com/agents/agent-development-lifecycle/test-and-launch-your-agent)
- Cohere North informs exact-version evaluation, draft isolation, and rollback. [North Agents](https://cohere.com/north/agents)
- WRITER informs repeatable work and comparison of quality, latency, and usage. [Playbooks](https://writer.com/product/playbooks/)
- Microsoft Copilot Studio informs controlled publishing and runtime data policy. [Publishing](https://learn.microsoft.com/en-us/microsoft-copilot-studio/publication-fundamentals-publish-channels) · [Data policies](https://learn.microsoft.com/en-us/microsoft-copilot-studio/admin-data-loss-prevention)
- Hebbia informs permissioned collaboration on evidence and deliverables. Salesforce and ServiceNow inform governed actions and operational oversight. [Hebbia Projects](https://www.hebbia.com/blog/introducing-projects) · [Agentforce guardrails](https://trailhead.salesforce.com/content/learn/modules/trusted-agentic-ai/explore-agentforce-guardrails-and-trust-patterns) · [ServiceNow AI Agents](https://www.servicenow.com/products/ai-agents.html)
