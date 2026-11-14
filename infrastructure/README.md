# EvolvXSI — infrastructure

Deployment profiles for EvolvXSI.

| Profile | What it is |
|---|---|
| [local](profiles/local/README.md) | Runbook for running the API and web app on one machine, in lite mode or with indexing. |
| [staging](profiles/staging/README.md) | Docker Compose profile with TLS, a retrieval overlay, backup and restore, and a release manifest. Checked in a sandbox. |

Kubernetes (Helm) and multi-tenant cloud profiles are planned in `modules.json` and will be added with their first
working version.
