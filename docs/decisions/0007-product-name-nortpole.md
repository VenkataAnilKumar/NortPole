# Decision 0007: product name NortPole

Date: 2026-11-14. Status: **accepted** by the product owner.

## Decision

The product is called **NortPole** (one word, capital N and P; the spelling is deliberate). It replaces the working name
NortPole everywhere people see the product: the web app, notifications, skill text, the README, documents and
screenshots.

## Why this name

The owner wanted "North" in the name and a name no one else uses. North+, NorthX, NorthWave, North AI and NorthPole were
set aside: "North" alone is Cohere's competing product, NorthWave and North AI are used by other software companies, and
NorthPole is IBM's AI chip. A web search found no company or product called NortPole. That is not a trademark search:
check the trademark registers (software, classes 9 and 42) and the `.com` and `.ai` domains before launch.

## Done and not yet done

- **Step 1 (done):** the visible name, renamed by script wherever "NortPole" stood alone; a migration updates the one
  stored text that named it (a built-in skill description). The dated review log and applied migrations keep the old
  name as history, and links to the GitHub repository keep its current name.
- **Step 2 (done):** code names. The Python package is `nortpole` (was `nortpole`), test folders are
  `tests/unit/nortpole` and `tests/nortpole_integration`, identifiers are `NortPole*`, settings are `NORTPOLE_*`, document
  files are `NortPole_*.md`, the pack SDK is `nortpole_pack_sdk` and the API description is `nortpole-api.json`.
  **Old setting names still work:** `shared_configs/env_compat.py` copies each `NORTPOLE_*` setting to its `NORTPOLE_*`
  name at start-up when the new one is not set (the new one wins); the web app and the staging Compose profile read the
  old names as a fallback too. Remove the fallbacks once deployments have moved.
- **Kept on purpose (stored or shared data):** database table and key names (`nortpole_*`), the sign-in token audience
  and the Craft provider id `nortpole`, browser storage keys, the `nortpole.audit` log stream, the `nortpole.mcp_oauth`
  token scope key, the Postgres user and database names and image names in the Compose profiles, the Kubernetes
  namespace and labels, the `nortpole.local` placeholder domain, migration file names, the `uv` project name, and some
  inherited internal module names (`nortpolebot`, `nortpole_retention`). Changing these would sign people out, reset
  preferences or break existing data, and needs its own migration plan if ever wanted.
- **Still to do by the owner:** rename the GitHub repository (Settings, General, Repository name; GitHub redirects old
  links).
