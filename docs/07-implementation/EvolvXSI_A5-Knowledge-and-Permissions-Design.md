# A5 design — knowledge, evidence and permissions

Status: **proposed** · Date: 2026-11-11 · Phase: A5 in the [delivery plan](EvolvXSI_Adopted-Core-Delivery-Plan.md)

## What the adopted core already gives us

Read from `services/core/evolvxsi` on 2026-11-11:

- **An access model per document.** `access/models.py` defines `DocumentAccess` with EvolvXSI user emails, user groups, external user emails, external group ids and an `is_public` flag. It converts to a list of access-control strings (`to_acl`) that retrieval filters on.
- **Many source connectors** (Google Drive, Confluence, Box, Dropbox, GitHub, Gmail, Jira, Linear, Slack-type sources and more) under `connectors/`.
- **A retrieval index interface** (`document_index/`) with an OpenSearch implementation and a disabled stub used by lite mode.
- **Not present:** automatic per-user permission sync from a source. Upstream keeps that in its enterprise edition, which we excluded. Connectors can record who a document is shared with, but nothing keeps that in step with the source over time.

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
