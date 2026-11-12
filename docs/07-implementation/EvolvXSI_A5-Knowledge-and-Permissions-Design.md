# A5 design — knowledge, evidence and permissions

Status: **proposed** · Date: 2026-11-11 · Phase: A5 in the [delivery plan](EvolvXSI_Adopted-Core-Delivery-Plan.md)

## What the adopted core already gives us

Read from `services/core/evolvxsi` on 2026-11-11:

- **An access model per document.** `access/models.py` defines `DocumentAccess` with EvolvXSI user emails, user groups, external user emails, external group ids and an `is_public` flag. It converts to a list of access-control strings (`to_acl`) that retrieval filters on.
- **Many source connectors** (Google Drive, Confluence, Box, Dropbox, GitHub, Gmail, Jira, Linear, Slack-type sources and more) under `connectors/`.
- **A retrieval index interface** (`document_index/`) with an OpenSearch implementation and a disabled stub used by lite mode.
- **Not present:** automatic per-user permission sync from a source. Upstream keeps that in its enterprise edition, which we excluded. Connectors can record who a document is shared with, but nothing keeps that in step with the source over time.

- **Groups are not applied for the asking user.** The community `_get_acl_for_user` returns the user's email addresses and the public marker only. Group and external-group access is added by the excluded enterprise code, so EvolvXSI has to supply it.

Lite mode runs with `DISABLE_VECTOR_DB=true`, so nothing can be indexed or retrieved there. Any retrieval test needs a real index service.

## Proposed approach

1. **Treat the access list as the single source of truth for what a user may see.** Retrieval filters by the asking user's emails and groups, as upstream does. Citations and exports re-check the same list at open time.
2. **Build our own permission sync, one source at a time.** For the first source, read the source's own sharing data, map people to EvolvXSI users and groups, and refresh on a schedule and on change events where the source offers them. Unmapped people get no access.
3. **Fail closed.** A document with no known access list is visible to administrators only. A sync that fails or times out leaves the last known list in place and raises an alert; it never widens access.
4. **Revocation withholds.** When access to a source is removed, answers and reports that depended on it are withheld until regenerated. Downloaded files cannot be recalled; say so in the pilot agreement.

## First slice, in order

| Step | Deliverable | Needs |
| --- | --- | --- |
| 1 | A fixed test set: a permitted document, a restricted document, a superseded version and an unanswerable question, with the expected cited answers | Nothing external; can use plain text fixtures |
| 2 | A permission test harness: given a user and a document set, assert what retrieval returns and what citations resolve | A retrieval index in the test environment |
| 3 | The first connector with permission sync | The first source system (open decision) |
| 4 | Cited search screen replacing the stubbed search view | A model route that can answer; the mock is enough for plumbing |
| 5 | Revocation and freshness behaviour | Steps 2 and 3 |

## Open decisions

1. **First source system.** Shared drive, wiki or document store. This sets the permission semantics.
2. **Where the retrieval index runs** (managed, customer cloud or on premises) and who operates it.
3. **Identity mapping.** How source identities map to EvolvXSI users and groups (email match, SSO subject, SCIM).

## Risks

- Permission meanings differ between sources (inherited folders, link sharing, group nesting). Each connector needs its own tests.
- Index and permission data can drift. The sync interval is a trade-off between freshness and load.
- This was read from source, not run. No retrieval has been tested in this environment.

## Progress (2026-11-11)

Step 1 is done and part of step 2 exists without an index:

- `services/core/evolvxsi/knowledge_access/decisions.py` holds the access rules as pure functions: the viewer's access strings (emails, groups, external groups), who may see a document, evidence filtering that counts hidden documents without describing them, citation re-checks, and the withhold rule.
- `services/core/tests/unit/evolvxsi/knowledge_access/a5_test_set.json` is the fixed test set (invented content): a permitted document, a restricted one, a superseded version, a public one, a document with unknown access and an unanswerable question.
- The unit tests pass (39 passed with the existing access tests, 4 skipped as not applicable).

Two rules the tests pin down: unknown access is visible to administrators only, and the administrator role does not open a document that has a known access list.

Not done: nothing calls these functions yet. Retrieval, citations and export still use the upstream paths, and no answer quality has been tested because there is no index or real model here.

## Progress (2026-11-12): permission harness on a real index

Step 2 runs. `services/core/tests/evolvxsi_integration/test_retrieval_acl.py` writes the fixed test set into a throwaway OpenSearch 3.6.0 index with each document's real access list, then runs the core's own keyword and semantic retrieval as each test viewer (analyst, contractor, admin, anonymous):

- Semantic retrieval returns exactly the documents each viewer may see.
- Keyword retrieval never returns a hidden document, and finds the permitted one when it should.
- A document with unknown access (stored as an empty access list) is returned to nobody, the administrator included. This is stricter than the rule in `decisions.py`, which lets an administrator see it; any administrator view of unsynced documents has to come from somewhere other than normal search.

21 checks passed. A control run with the access filter switched off returned the restricted board memo, so the harness does catch a leak.

Limits: embeddings are deterministic test vectors because the embedding model host is blocked here, so this checks access filtering only, not answer quality. Group access works because the harness builds the viewer's access list with groups (`viewer_acl`); the community user path (`_get_acl_for_user`) still adds only email addresses, so wiring `viewer_acl` into real search is the next step.

