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

## Progress (2026-11-12): group access wired into real search

The community code left groups out on both sides: users' access lists carried only email addresses, documents were indexed with no groups, and the query-time source check returned false for groups. EvolvXSI now fills all three (`services/core/evolvxsi/knowledge_access/groups.py`, used from `access/access.py` and `db/connector_credential_pair.py`):

- A person's access list includes every group they belong to, read on each request.
- A document's access list includes the data-access groups of the PRIVATE sources it came from (`UserGroup__CCPairDataAccess`).
- Only data-access links grant reading. The other link table (`UserGroup__ConnectorCredentialPair`, roles editor and operator) decides who may manage a source and grants no reading.
- SYNC_RESTRICTED sources grant nothing through groups. The core defines them as "group member and allowed by the source's own permissions", which a group entry cannot express, so they fail closed until a per-source permission sync exists.

Checked end to end on the sandbox database and OpenSearch (`tests/evolvxsi_integration/test_group_access.py`): the member finds the document, an outsider does not, a group that only manages the source does not, a data-access group on a SYNC_RESTRICTED source does not, and removing the member from the group hides the document on the next search. With the earlier harness, 26 checks pass. A first version of this change used the management link table by mistake; the integration test exposed it before commit.

Not done: removing a group from a source changes stored document access lists only on re-index (no re-sync job yet); the query-time source check is only active when its rollout flag is on and was not exercised here; there is still no screen or API to manage groups or link them to sources, since that was enterprise-only upstream.

## Progress (2026-11-12): managing groups

The community code already lets an administrator add reading groups to a source from the source's own settings, and refuses the built-in role groups there. What was missing was managing the groups themselves, which upstream kept in its enterprise edition. Added:

- `services/core/evolvxsi/knowledge_access/group_admin.py`: `GET` and `POST /admin/access-groups`, `PATCH` and `DELETE /admin/access-groups/{id}` (needs the manage-user-groups permission). Each change is audited.
- Safety rules: a group that reads any source cannot be renamed or deleted, because documents carry the group's name on their access lists and a new group given the old name would inherit that access. Names are unique whatever the case. Built-in role groups are not managed here. Unknown users are refused.
- `apps/workspace/src/views/admin/AccessGroupsPage.tsx` at `/admin/access-groups`, listed as Groups in the admin sidebar: create a group, pick members, rename, delete, and see which sources each group reads.

Checked: six integration tests on the real database pass (32 in the integration folder in total). The page had not been type-checked or opened in a browser when this was committed; see `docs/REVIEW.md` for the follow-up.

## Progress (2026-11-12): changing who reads a source

(Corrected 2026-11-12: community code does have an edit path for a source's reading groups, the connector edit form; see the next section. Its saving step was a no-op.) Added `PUT /admin/access-groups/sources/{cc_pair_id}` (in `group_admin.py`), which replaces a source's reading groups and marks every document from that source as modified. The core's existing background metadata sync then rewrites each document's access list in the index from the current groups, using the group-aware access functions added earlier.

Rules: only private and permission-synced sources take reading groups; a permission-synced source needs at least one; built-in role groups and unknown groups are refused; setting the same groups again marks nothing. Each change is audited with the groups added and removed and the number of documents marked.

Checked on the sandbox database and OpenSearch (34 integration checks pass): removing the group marked the document, the member could still find it until the sync step ran, and after the sync step (run directly in the test, since background workers do not run in lite mode) the member could not.

Known window: between the change and the background sync, the index still holds the old access list, so a removed group keeps reading for that time. The query-time source check (behind a rollout setting, not exercised here) would close that window. There is no screen for this yet; it is an API only.

## Progress (2026-11-12): search-time source check on by default

The core can decide at search time which sources a person may read, from the database, instead of relying only on the access list stored on each document. Upstream shipped it switched off. EvolvXSI now turns it on and enforces it by default (`ENABLE_CC_PAIR_ACCESS_FILTER` and `ENFORCE_CC_PAIR_ACCESS_FILTER`, both default true; set either to `false` to turn it off; a cache override still wins).

Enforcement takes effect only once every indexed chunk carries its source ids (the core's backfill). Until then search stays in shadow mode: results still use the document access list, as before, and a second comparison query is logged per search. So the new default is never less strict than the old one.

Checked against the real database and OpenSearch (`tests/evolvxsi_integration/test_source_access_enforced.py`, 37 integration checks pass in total):

- Private source: a reading-group member finds its documents, others do not.
- Removing the group from the source hides the documents at once when enforced, before any re-sync; the old filter still showed them, which is the window this closes.
- Permission-synced source: visible only to someone who is both in a reading group and named on the document; being named alone, or in the group alone, is not enough.

The rollout gate itself (flag plus backfill state) was stubbed in that test and covered by unit tests. The backfill task needs background workers, so it has not run in this sandbox.

## Progress (2026-11-12): the connector edit form now saves reading groups

Correction to an earlier note: the community copy does have a way to change a source's reading groups after creation, the connector edit form and its edit plan. But the three functions that path calls for groups were enterprise-only and fell back to no-ops in the community copy:

- reading the source's current groups returned none, so the form compared against an empty list;
- saving the new groups did nothing, while the edit reported success;
- the check that a permission-synced source keeps at least one group was skipped.

Documents were also re-synced only when the source's access type changed, not when only its groups changed.

EvolvXSI now implements all three (`services/core/evolvxsi/knowledge_access/source_groups.py`), called directly from `connectors/edit_plan/state.py` and `db/connector_edit_requests.py`. Saving marks the source's documents for the access re-sync whenever the groups change. A scoped editor changes only the groups they can see, and the groups they cannot see are kept.

Checked on the real database (42 integration checks pass, 5 new): the edit reads the real current groups; a scoped editor replaced one group while a group they could not see stayed; adding an unseen group was refused; a permission-synced source with no group was refused and left unchanged; making a source public removed its groups. The 234 existing unit tests for the edit flow pass. The edit form itself was not opened in a browser, because no source can be connected in the lite sandbox.

`PUT /admin/access-groups/sources/{id}` (added earlier) does the same job with its own checks and duplicates part of this; it can be folded into this path later.

