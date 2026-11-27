# NortPole Enterprise Search

**Status** — Proposed product and interaction design, November 20, 2026. Requirements come from the product discussion, public platform documentation, and NortPole’s current code. Customer demand, benchmark targets, and connector-specific freshness still need pilot validation.

## Product decision

Give employees one place to find company knowledge, their conversations, and their workflow results. From a search result, they can open the original or ask a question in Chat using selected evidence. Search, Chat, agents, and packs use the same Knowledge layer and enforce the requesting user’s access.

The main competitive advantage is the path from **finding evidence** to **doing work with it**. For example, a user can find the travel policy, open the relevant section, and ask Chat to compare it with an expense review. A finance pack can suggest the policy library and a comparison action. The same search works for an IT or operations pack.

## Platform research and requirements

| Reference | Documented pattern | NortPole requirement |
| --- | --- | --- |
| Glean | Connector-backed, permission-aware search across tools. Its knowledge graph uses people, content, and interactions to personalize relevance. The public API accepts a query and filters. | Deliver fast ranked results with reliable source filters and direct links. Evaluate personalization after measuring search quality on a shared baseline. [Enterprise Search](https://www.glean.com/enterprise-search) · [Search API](https://developers.glean.com/api/client-api/search/search) |
| Cohere North | Libraries curate sources for people and agents, resync with connected systems, and retain original document permissions on supported connectors. Cohere also exposes reranking and cited generation APIs. | Let users and agents scope retrieval to libraries. Cite the passages used in generated answers and carry library scope into Chat. [North Libraries](https://cohere.com/north/libraries) · [Rerank](https://docs.cohere.com/docs/rerank-overview) · [Citations](https://docs.cohere.com/docs/retrieval-augmented-generation-rag) |
| Hebbia Matrix | Structured comparisons across many documents or entities trace findings to evidence. | Support comparison from selected Knowledge results in a later release. Keep source references at the finding level. [Matrix](https://www.hebbia.com/matrix) |
| WRITER | Agents query selected Knowledge Graphs. Graphs can be deployed org-wide or to specific teams. The query API returns supporting snippets and can include citations. | Support reusable, explicitly scoped knowledge for packs and agents. Workspace and source permissions still apply to each result. [Knowledge Graphs](https://dev.writer.com/home/knowledge-graph) · [Query API](https://dev.writer.com/api-reference/kg-api/question) |
| Amazon Q Business and Microsoft 365 Copilot | Amazon Q Business crawls document ACLs and maps source identities. Microsoft distinguishes synced, indexed connectors from federated connectors that retrieve from the source at request time. | Establish an access and freshness contract per connector. Add live retrieval for sources with a concrete freshness or indexing constraint. [Amazon Q connector concepts](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/connector-concepts.html) · [Microsoft Copilot connectors](https://learn.microsoft.com/en-us/plugins/overview-copilot-connector) |

## Users and jobs

| User | Job | Proof of success |
| --- | --- | --- |
| Employee | Find a known policy or discover relevant knowledge using everyday language. | Opens the right source and can tell what matched from the excerpt. |
| Returning contributor | Recover a decision buried in a conversation or find the result of a scheduled run. | Opens the matching message or run directly. |
| Analyst or pack user | Select authoritative evidence and use it to answer a question or compare options. | Sees which sources support the answer and can open them individually. |
| Workspace administrator | Understand which sources are searchable and protect restricted data as access changes. | Can inspect sync health and verify outcomes with users who have different permissions. |

## Search page

Add **Search** to the workspace sidebar. The desktop and mobile layouts use NortPole’s existing navigation, typography, and controls.

The sketch shows the page once all three tabs and the Chat handoff are available. The first release opens directly to Knowledge and exposes its available filters.

```text
Search
[ Search company knowledge, chats, and workflows             ]

  Knowledge     Chats     Workflows
  Library ▾   Source ▾   File type ▾   Updated ▾    Clear filters

  Travel and expense policy
  Finance Policies · SharePoint · Updated Nov 12
  “…international airfare requires approval before booking…”
  Open source                                      Select for Chat

  More results
```

- **Shared behavior.** Press Enter to search. Keep the query when switching among available tabs. Keep filters scoped to their own tab. Preserve the query, filters, and loaded results when users open an item and return. Keep query text out of shared URLs and analytics by default.
- **Knowledge.** Default to all accessible Knowledge. Narrow by library, connector/source, file type, and updated date. Group multiple matching passages into one result per document. Show the title, source, matching excerpt, and last updated date when available. Open the original document or the matching section when the source exposes a stable anchor. For uploaded files, use the authorized NortPole file viewer.
- **Chats.** Match conversation titles and accessible message contents. Group by conversation with the best matching message first. Show the conversation title, chat or project context, and message excerpt. Open the matching message when available. Use the conversation link when an anchor is unavailable.
- **Workflows.** Search visible workflow names and readable run metadata and outputs. Filter by workflow, status, and run date. Open a workflow for a name match and the exact run or result for a run match. Shared workflow definitions and private runs have independently enforced access.
- **States.** Support initial, loading, no matches, incomplete results, failure, and permission-changed states. When one source fails and others return results, show the available results and a retry for the failed portion where safe. Never distinguish a restricted match from a nonexistent one. Announce result updates to assistive technology, make tabs and result actions keyboard accessible, and preserve focus on retry and pagination.
- **Chat handoff.** After results ship, let users select results and choose **Ask in Chat**. Open a composer with the selected sources visible before sending. Use stable references and reauthorize them when the question runs. Return citation links to the supporting passages. If the evidence does not support an answer, say what could be found and let the user change the selection.

## Retrieval and permissions

1. **Index connected Knowledge.** Reuse NortPole’s connector and library access rules. Track stable source and document IDs, title, canonical URL, library membership, timestamps, document permissions, and searchable passages with location metadata when available. Handle updates, deletions, moves, and permission changes as sync events. A document may appear in several libraries with one result per search.
2. **Search as the user.** Resolve the tenant and requesting principal on the server. Agents use a scoped principal on the user’s behalf. Apply applicable source, library, document, chat, and run permissions before returning excerpts, counts, filters, previews, or evidence for generation. Recheck at follow-up retrieval and resource open. When required permissions are indeterminate, withhold the content. Filters and pack defaults can narrow scope within the principal’s access.
3. **Rank and page by document.** Combine lexical retrieval for titles, phrases, and identifiers with semantic retrieval for reworded questions. Tune exact-match boosts and reranking against the same relevance set. Group authorized passages before paging the results. Define stable ordering for a search session and use an opaque continuation bound to the user, query, and filters. Reapply access checks on each page. Return a restart path if the continuation expires. Surface lexical-only degradation when semantic retrieval is unavailable.
4. **Reuse retrieval across surfaces.** Keep search retrieval and evidence references reusable by Chat and agents. Use owner/share-aware providers for Chats and Workflows, where authorization follows their source records. Use allowed source URLs or typed internal routes for result navigation. Track latency, errors, result opens, zero-result searches, sync age, and permission-sync health without collecting raw queries or excerpts by default.
5. **Give packs defaults.** Horizontal and vertical packs can suggest approved library scopes, synonyms, and actions, such as comparing contracts. Display applied scope so users understand where they are searching and can change it within their permissions.

### Existing NortPole components and gaps

- The [Search API](../../services/core/nortpole/server/features/search/api.py) already uses the Chat search tool for hybrid retrieval, query expansion, and reranking. Its raw path uses hybrid retrieval without generation or query expansion and returns up to ten sections. Extend the shared retrieval path for document grouping and pagination. Preserve the response behavior of existing API callers.
- [Search request models](../../services/core/nortpole/server/features/search/models.py) already support source, document-set, and time filters. Map library selections to authorized stable IDs at the new page boundary. Verify file-type metadata coverage and the availability of canonical document IDs and anchors before exposing those filters or links.
- [OpenSearch retrieval](../../services/core/nortpole/document_index/opensearch/search.py) already applies document access filters. Validate enforcement and permission freshness on the enabled connectors in the launch configuration. For synced permissions, test both local access changes and upstream changes after a successful sync.
- The [chat search menu](../../apps/workspace/src/sections/sidebar/ChatSearchCommandMenu.tsx) establishes a navigation flow. Verify message indexing and anchoring for the full Chats tab. Reuse the [workflow run view](../../apps/workspace/src/sections/workflows/WorkflowRunsPage.tsx) and scheduled-run hooks after validating deep links, run ownership, and share rules.

## Release sequence and acceptance

| Release | Scope | Acceptance |
| --- | --- | --- |
| 1 — Knowledge | Search page, ranked documents, excerpts, library and source filters, file type and update filters where metadata is reliable, source links, pagination, access checks, and sync visibility | Find a known title or ID and a rephrased policy query. Results stay grouped when paging a corpus with more than 50 matching passages. A permission change is enforced at the appropriate boundary, including when opening an earlier result. Empty and degraded states guide the user to a safe retry or filter change. |
| 2 — Multi-tab search | Chats and Workflows in the same page | A query persists across tabs, opens an exact older message or run when available, and applies the correct private and shared access rules. Deleted messages and private runs from another user are absent from all search surfaces. |
| 3 — Evidence to Chat | Select results, ask with citations, and expose scoped retrieval to agents and packs | Authorized citations resolve to supporting passages. Revoked or deleted selected items are withheld, including after a selection has reached Chat. An unsupported question produces a clear evidence gap. |
| Later — Evidence at scale | Multi-document comparison, federated sources where required, and measured ranking refinements | Comparison findings link to their source passages. A slow or failed federated source does not block indexed results. Each ranking change shows measurable improvement on the relevance set. |

### Pilot scorecard

- **Access** — Zero restricted-content disclosures in the release test matrix. Test a document reader, non-reader, source manager without reading rights, and a user whose access was revoked. Check search results, counts, filters, Chat handoff as it ships, cached pages, and deep links.
- **Relevance** — Proposed starting targets of at least 90% top-three success for known-item queries and 80% top-five success for natural-language queries. Include exact identifiers, paraphrases, near-duplicates, ambiguous names, and queries with no supporting document. Compare lexical and hybrid configurations on the same permissions-aware judgments.
- **Speed** — Proposed p95 under two seconds for the first indexed results on an agreed pilot corpus and load profile. Measure generation and live-source retrieval independently.
- **Freshness** — Define a measurable content and access update window per launch connector. Check deletes, moves, share revocations, group membership changes, and degraded sync. Track the age of the last successful sync and the time to reflect upstream changes.
- **Usability** — In pilot sessions, observe whether people can find a document, verify its source, and return to their results without help. In the second release, add a deleted-message case and a completed-run lookup.

Confirm the launch corpus, connector permissions and freshness, and relevance judgments with pilot users and the workspace administrator before setting production targets.
