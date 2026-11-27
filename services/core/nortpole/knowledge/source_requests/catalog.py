"""What the Discover page offers: things this workspace supports but has not turned on. Only known items are listed:
connector types the product supports, packs an administrator has uploaded, and tools that already exist. People can
request them; nothing here turns anything on."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from nortpole.configs.app_configs import SHOW_EXTRA_CONNECTORS
from nortpole.configs.constants import DocumentSource
from nortpole.configs.constants import DocumentSourceDescription
from nortpole.connectors.registry import CONNECTOR_CLASS_MAP
from nortpole.db.models import Connector
from nortpole.work.packs.models import NortPolePackVersion

KINDS = ("connector", "skill", "plugin")

# Display names whose product spelling differs from the source identifier.
_CONNECTOR_NAMES = {
    DocumentSource.AZURE_DATALAKE: "Azure Data Lake Storage",
    DocumentSource.BOOKSTACK: "BookStack",
    DocumentSource.CLICKUP: "ClickUp",
    DocumentSource.FRESHDESK: "Freshdesk",
    DocumentSource.GITBOOK: "GitBook",
    DocumentSource.GITHUB: "GitHub",
    DocumentSource.GITLAB: "GitLab",
    DocumentSource.HIGHSPOT: "Highspot",
    DocumentSource.HUBSPOT: "HubSpot",
    DocumentSource.IMAP: "Email",
    DocumentSource.LUMAPPS: "LumApps",
    DocumentSource.MEDIAWIKI: "MediaWiki",
    DocumentSource.OCI_STORAGE: "Oracle Storage",
    DocumentSource.ONEDRIVE: "OneDrive",
    DocumentSource.PRODUCTBOARD: "Productboard",
    DocumentSource.R2: "Cloudflare R2",
    DocumentSource.S3: "Amazon S3",
    DocumentSource.SALESFORCE: "Salesforce",
    DocumentSource.SHAREPOINT: "SharePoint",
    DocumentSource.TEAMS: "Microsoft Teams",
    DocumentSource.TESTRAIL: "TestRail",
    DocumentSource.WEB: "Website",
    DocumentSource.XENFORO: "XenForo",
    DocumentSource.YOUTRACK: "YouTrack",
}
CONNECTORS = {
    source.value: (
        _CONNECTOR_NAMES.get(source, source.value.replace("_", " ").title()),
        DocumentSourceDescription.get(source, ""),
    )
    for source in CONNECTOR_CLASS_MAP
    if source is not DocumentSource.MOCK_CONNECTOR
}
CONNECTOR_APPROVAL = (
    "An administrator connects the source and sets who can access its documents."
)

@dataclass
class Item:
    kind: str
    key: str
    name: str
    description: str
    why_approval: str  # why an administrator has to turn it on


def connector_options() -> dict[str, tuple[str, str]]:
    return {
        key: metadata
        for key, metadata in CONNECTORS.items()
        if SHOW_EXTRA_CONNECTORS or key != DocumentSource.BRAINTRUST.value
    }


def connectors(db: Session) -> list[Item]:
    configured = set(db.scalars(select(Connector.source).distinct()))
    return [
        Item("connector", key, name, description, CONNECTOR_APPROVAL)
        for key, (name, description) in connector_options().items()
        if key not in configured
    ]

def skills(db: Session) -> list[Item]:
    rows = db.scalars(select(NortPolePackVersion).order_by(NortPolePackVersion.installed_at)).all()
    active = {r.pack_id for r in rows if r.active}
    latest: dict[str, NortPolePackVersion] = {}
    for r in rows:
        if r.pack_id not in active:
            latest[r.pack_id] = r
    out = []
    for pid, r in latest.items():
        m = r.manifest
        out.append(Item("skill", pid, str(m.get("name", pid)), str(m.get("description", "")),
                        "An administrator turns a pack on after checking it passes evaluation on the current model."))
    return sorted(out, key=lambda i: i.name.lower())


def plugins(db: Session) -> list[Item]:
    from nortpole.governance.tool_catalog import api as cat_api
    from nortpole.governance.tool_catalog import catalog as cat

    out = []
    for t in cat_api.build(db).tools:
        key = t.workspace_request_key
        if key is None:
            continue
        why = "Calls a system outside the workspace; its definition has to be approved." if t.kind == "outside" else \
            "Runs code the model writes." if t.kind == "code" else "Turned off for this workspace by an administrator."
        out.append(Item("plugin", key, t.name, cat.LABEL[t.kind], why))
    return sorted(out, key=lambda i: i.name.lower())


def discover(db: Session) -> list[Item]:
    return connectors(db) + skills(db) + plugins(db)


INTEGRATION_PREFIX = "integration:"


def integration_key(integration_id: str) -> str:
    """The request key for an integration, kept apart from connector types, packs and tools so keys never clash."""
    return INTEGRATION_PREFIX + integration_id


def _integration(kind: str, key: str) -> Item | None:
    """An integration an administrator has set to "needs approval" can be requested; one that is allowed or blocked
    has nothing to request."""
    from nortpole.work.integrations import policy, registry

    definition = registry.get(key.removeprefix(INTEGRATION_PREFIX))
    if definition is None or definition.kind != kind or policy.resolve(definition) != "needs_approval":
        return None
    return Item(kind, key, definition.name, definition.description, "An administrator approves this before you can install it.")


def find(db: Session, kind: str, key: str) -> Item | None:
    if key.startswith(INTEGRATION_PREFIX):
        return _integration(kind, key) if kind in ("connector", "plugin") else None
    items = {"connector": connectors, "skill": skills, "plugin": plugins}.get(kind)
    return next((i for i in items(db) if i.key == key), None) if items else None
