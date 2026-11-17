# Decision 0008: integrations as signed declarative data

Date: 2026-11-16, updated 2026-11-17. Status: **accepted** by the product owner; phases 1 to 4 are built and the definitions are not yet verified (see Phases). It extends
[decision 0006](0006-scalable-repository-structure.md) (packs as source) to connectors and plugins.

## Context

The owner wants Sources to work like a catalog: people search it and **Install** or **Connect** from the card, as in
Claude's Customize, other integration catalogs and MiniMax's plugins. The first version grouped the catalog Horizontal
(Engineering, Design, Product, Code, Automations, Legal, Sales, GTM) and Vertical (Law, Finance, Health, Bio, Life
Science, Voice, Video, Media, Entertainment and more); on 2026-11-17 the owner asked for the Sources screens to drop
that grouping and show Connectors, Plugins, Skills and Discover. The two groups stay in the definitions and on the
administrator's Integrations page, not on the person's screens.

## Decision

1. **Definitions are NortPole's own.** Each integration is written for NortPole as data, from the vendor's published API
   reference, in NortPole's own declarative format. NortPole's governance (route policy, redaction, audit,
   approvals) lives in the Python core, and no code or definition is taken from another project.
2. **A definition is data, not code** (`services/core/nortpole/work/integrations/manifest.py`). It lists the exact
   hosts it may call and never lets a placeholder fill the host. A secret can only come from the person's connected
   account (`{credential.access_token}` or `{credential.api_key}`), only in a header. Each parameter says who fills it (the person, the model or
   either). Each action is a read or a write, and an integration with a write action can only start as "needs
   approval". Output paths use a small fixed path language, so no definition runs code.
3. **Where it lives.** `integrations/horizontal/<category>/<id>/integration.yaml` and
   `integrations/vertical/<category>/<id>/integration.yaml`, registered in `modules.json`. The folder must match the
   definition's group and category, ids are unique, and the category must be one of the reviewed lists in the model
   (adding a category is a one-line change). The JSON Schema is generated into
   `packages/contracts/schemas/integration.schema.json` and a test fails on drift.
4. **Two kinds, and skills.** A *plugin* and a *connector* are both sets of actions written the same way; the kind is a
   label that decides which tab shows them (a connector is a system whose data a person reads, such as a mailbox or a
   drive; a plugin is a tool). Neither brings documents into the search index: that is the inherited document
   connectors' job (Google Drive permission sync, A5). *Skills* are not definitions: they are the inherited personal
   skills, and a definition may suggest up to five (name, one line, instructions) that a person adds with one click.
5. **Policy per item** (as Claude's organisation policy): "allowed" shows Install or Connect to people; "needs
   approval" shows Request. Writes always need approval. Installing a skill or plugin is per person; connecting an
   outside system uses the person's own account after an administrator has allowed it.

## Phases

| Phase | What | State | Tests that close it |
|---|---|---|---|
| **1. Format** | The model, the JSON Schema, registration in `modules.json`, the structure check, CI. | Done. Since extended: all five methods, JSON bodies, form bodies, `object` parameters, `number` outputs, suggested skills. | Unit tests, including the cases the format must refuse; drift and structure tests. |
| **2a. Executor** | `executor.py` runs an action: who may set each parameter, caps and defaults, URL-encoded paths, the exact-host rule again, the credential only in a header, no redirects, a time and size limit, JSON only, status-only errors, one audit row per call. | Done | Unit tests with mock transports. |
| **2b-1. Accounts and policy** | `service.py`: install, remove, connect, disconnect and call, per person. Policy per integration or category (allowed, needs approval, blocked; blocked wins; a damaged setting blocks everything); an approval is one person's; accounts sealed at rest. | Done | Database tests. |
| **2b-2. Routes** | Person routes (catalog, detail, install, remove, connect, disconnect, sign-in start and complete) and administrator routes (the policy page and its change). | Done | Route and endpoint-security tests; the route contract pins every gate. |
| **2b-3. Sign-in and renewal** | OAuth with PKCE (`oauth.py`): sealed state, the code traded through the safe transport, renewal before a call. Ten providers described; set up per service by an administrator (staging README). | Built; tried only against a local fake provider. | Unit, database and browser tests with a fake provider. |
| **3. Sources screens** | Connectors, Plugins, Skills and Discover tabs; the catalog (search, category dropdown, "Yours" first, rows that open to the full card, logos); the administrator's Integrations page; Request through the existing Approvals queue. | Done | Browser checks, axe, type check. |
| **4. Connectors and skills** | Five connector definitions (GitHub, Slack, Google Drive, Gmail, Google Calendar). Skills reuse the inherited personal-skills system; a definition can suggest up to five, added with one click. | Done for the first set | Tests and browser checks. |
| **5. Verification and more definitions** | Check every definition against the vendor's published documentation, call each with a test account and remove what cannot be verified; then add services in small batches, written for NortPole. | **Open. Nothing is verified yet.** | Per service: a documented check and one real call. |

## Known limits of the format

- A body is a JSON tree (at most six levels and 200 parts); there are no decimal numbers in a body, no arrays as
  parameters (an `object` parameter carries free-form JSON), no multipart bodies and no file uploads or downloads.
- A response is read by path only (`$.a.b[0]`, `$.items[*]`); a result that must be combined or computed in code cannot
  be described. XML responses are not supported.
- A service that reports errors inside a successful response (Slack) shows empty outputs, not a clear message.
- OAuth endpoints are described for ten providers; Slack's two-token response and Stripe Connect are not handled, and
  there is no background renewal (a token is renewed when a call needs it).
- Chat can call the **read** actions of integrations a person installed and connected (`chat_tools.py`, default chat only, up to 40 tools, results cut at 20,000 characters); **write actions are never offered to chat**, because chat has no step where a person approves one call. Workflows do not call integrations yet. A write from chat needs an approval step (the agent runtime has a before-call hook for it, but chat does not use it and the screen has no approve button yet).
- The integrations in the repository were written from knowledge of each vendor's API and have not been checked
  against current documentation or called against a real service.
