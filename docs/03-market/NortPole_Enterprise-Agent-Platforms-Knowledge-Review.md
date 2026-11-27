# Enterprise agent platforms and NortPole Knowledge

Status: Product research and recommendations · Reviewed November 18, 2026

NortPole should first make it possible to manage a Knowledge domain, find its documents with citations, and use those documents in an agent. Cohere North is the closest reference for the management experience. Glean informs how to reuse connected context, Hebbia shows how to present evidence during research, and WRITER shows how to package repeatable work. The comparison draws on public product pages. Authenticated workflows, permission behavior, and deployment claims still need hands-on evaluation.

| Platform | How Knowledge works | What NortPole can apply |
| --- | --- | --- |
| Hebbia | Matrix organizes analysis across entities and documents. Max uses firm materials, filings, and external data for finance workflows. The platform examples show findings linked to source passages. | Put the supporting passage beside each finding in policy comparisons and research briefs. [Matrix](https://www.hebbia.com/matrix/) · [Max](https://www.hebbia.com/max/) · [Platform](https://www.hebbia.com/platform/) |
| Cohere North | Libraries curate files from connected sources or uploads, support resync, and can be attached to chats, agents, and automations. Compass supplies parsing, indexing, and retrieval. | Make domains easy to create, manage, and select. Show source permissions and sync status where people work. [Libraries](https://cohere.com/north/libraries) · [Compass](https://cohere.com/compass) |
| Glean | Enterprise Context maps people, content, and relationships across systems. Its research workflow combines business data and company context in cited outputs. | Reuse the same permission-aware source context across Search, chat, and agents. Defer a relationship graph until a workflow needs it. [Enterprise Context](https://www.glean.com/platform/enterprise-context) · [Research and analysis](https://www.glean.com/ai-assistant/research-and-analysis) |
| WRITER | Enterprise Brain combines company standards and agent memory. Playbooks bring knowledge, skills, and connectors into reusable workflows. | Keep source documents, approved instructions, and saved research distinct. Use existing workflow packs to package repeatable work and defer automatic shared memory. [Enterprise Brain](https://writer.com/product/enterprise-brain/) · [Playbooks](https://writer.com/product/playbooks/) |

## NortPole today

Knowledge displays existing document sets as cards with a visibility label and a sync indicator. Administrators manage connectors and document sets in separate views. Agents already reference document-set IDs. In the development sandbox, a sample travel policy was indexed and retrieved with its source link, a demo collection appeared in Knowledge, and 21 retrieval permission tests passed. A live company connector and permission changes in its source system remain unverified. [Knowledge page](../../apps/workspace/src/sections/libraries/LibrariesPage.tsx) · [Agent models](../../services/core/nortpole/server/features/persona/models.py) · [Pending work](../07-implementation/NortPole_Pending-Work-Checklist.md)

## Recommended first release

Use **domain** as the working term from R7. Each domain should build on an existing document set and expose its sources, owners, access, and sync state. Introduce management links for authorized users and let readers open a domain to inspect its documents and sources. Keep sync completion, the source’s last-modified date, and owner verification as separate signals. [R7 Knowledge design](../05-design/NortPole_Workflows-and-Knowledge-Design.md#4-knowledge-r7)

1. Connect one source or use the file connector to validate the flow. Give personal uploads a private starting point and use the existing R7 approval flow for additions to shared domains.
2. Create a domain, inspect processing, and search it for a document with a citation that opens the supporting passage.
3. Attach that domain to an agent and verify it retrieves the same permitted evidence.
4. Test with a reader who has access and a second person who lacks it. Check both domain-scoped and all-knowledge queries, then revoke the reader’s access and verify that subsequent retrieval is denied across Search, chat, and agents. Collection visibility alone only controls whether the collection appears in pickers. Resolve the R7 access-sync window before promising immediate revocation. [R7 access rules and risks](../05-design/NortPole_Workflows-and-Knowledge-Design.md#45-prerequisites-and-risks)

## Research and web search

Once that journey works, let users run a research task against selected domains and optionally search the web. Show internal and external evidence separately in the report. Make **Save to Knowledge** an explicit action with a target domain, a visibility choice, and review before adding findings to shared knowledge. Retain the original URL, retrieval date, publication date when available, cited passage, and review status. The vendor pages support these design comparisons but do not establish equivalent live web search across all four products.
