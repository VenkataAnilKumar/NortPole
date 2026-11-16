# Decision 0008: integrations as signed declarative data

Date: 2026-11-16. Status: **accepted** by the product owner (phase 1 built). It extends
[decision 0006](0006-scalable-repository-structure.md) (packs as source) to connectors and plugins.

## Context

The owner wants Sources to work like a catalog: people search it and **Install** or **Connect** from the card, as in
Claude's Customize, Sim's integrations and MiniMax's plugins, grouped Horizontal (Engineering, Design, Product, Code,
Automations, Legal, Sales, GTM) and Vertical (Law, Finance, Health, Bio, Life Science, Voice, Video, Media,
Entertainment and more). Sim, an open-source workflow builder, already describes hundreds of services this way, and the
owner asked to build on its definitions.

## Decision

1. **Reuse Sim's definitions, not its engine.** Sim's tools are TypeScript tied to its own workflow engine, database
   and sign-in code. NortPole's governance (route policy, redaction, audit, approvals) lives in the Python core, so
   each Sim tool is rewritten into NortPole's own declarative format. Sim is Apache-2.0: `integrations/NOTICE` and
   `integrations/LICENSE-APACHE-2.0` carry its notice, and each adapted file names the Sim file it follows. Nothing
   from Sim's separately licensed `ee` folder is used.
2. **A definition is data, not code** (`services/core/nortpole/work/integrations/manifest.py`). It lists the exact
   hosts it may call and never lets a placeholder fill the host. A secret can only come from the person's connected
   account (`{credential.access_token}`), only in a header. Each parameter says who fills it (the person, the model or
   either). Each action is a read or a write, and an integration with a write action can only start as "needs
   approval". Output paths use a small fixed path language, so no definition runs code.
3. **Where it lives.** `integrations/horizontal/<category>/<id>/integration.yaml` and
   `integrations/vertical/<category>/<id>/integration.yaml`, registered in `modules.json`. The folder must match the
   definition's group and category, ids are unique, and the category must be one of the reviewed lists in the model
   (adding a category is a one-line change). The JSON Schema is generated into
   `packages/contracts/schemas/integration.schema.json` and a test fails on drift.
4. **Two kinds.** A *plugin* is an action tool. A *connector* brings documents into search and will carry a
   permission-scoped listing flag; its definitions come in a later phase. *Skills* stay in packs and get the same
   category field.
5. **Policy per item** (as Claude's organisation policy): "allowed" shows Install or Connect to people; "needs
   approval" shows Request. Writes always need approval. Installing a skill or plugin is per person; connecting an
   outside system uses the person's own account after an administrator has allowed it.

## Phases

| Phase | What | Tests that close it |
|---|---|---|
| **1. Format and first definitions** (done) | The model, the schema, two integrations adapted from Sim (Wikipedia, Airtable), registration and the structure check, CI. | 43 unit tests, including 29 cases the format must refuse; drift and structure tests. |
| **2. Executor and accounts** | A fixed executor runs an action: fills placeholders, URL-encodes paths, applies caps and defaults, keeps to the listed hosts, calls through route policy and the audit log, and fills the token from a stored credential. OAuth sign-in and refresh. | Tests with a local fake service; a call to an unlisted host is refused; the audit row has no arguments. |
| **3. Sources screens** | The catalog (search, type and category filters), Install, Connect, Request and statuses, per-item policy in the admin area. | Browser checks in light and dark; contrast and overflow checks. |
| **4. Connectors and skills** | Connector definitions (list, get, check, content hash), permission-scoped listing, the category on packs. | Tests that a person's own token limits what is listed. |
| **5. More definitions** | Port more of Sim's services in batches, with a helper for the common shapes. | Each definition validates; reviewed in batches. |

## Known limits of the format (phase 1)

- A request body can only hold flat text fields, so write actions that need a JSON array (for example creating
  Airtable records) are not described yet. Airtable's write tools were left out for that reason.
- A response can be read by path only. Sim's Wikipedia search zips four arrays together in code; NortPole's search
  action uses the standard MediaWiki query instead.
- XML responses (arXiv) are not supported.
- Nothing runs yet: the executor is phase 2.
