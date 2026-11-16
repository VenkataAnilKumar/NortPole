"""What the Discover page offers: things this workspace supports but has not turned on. Only known items are listed:
connector types the product supports, packs an administrator has uploaded, and tools that already exist. People can
request them; nothing here turns anything on."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from nortpole.configs.constants import DocumentSource
from nortpole.db.models import Connector
from nortpole.work.packs.models import NortPolePackVersion

KINDS = ("connector", "skill", "plugin")

# Connector types offered on Discover, with what each would read. A short, reviewed list rather than every connector
# the core has: these are the common company systems. Each would only show people documents they can open there.
CONNECTORS: dict[str, tuple[str, str]] = {
    DocumentSource.GOOGLE_DRIVE.value: ("Google Drive", "Reads files and folders in Google Drive."),
    DocumentSource.SHAREPOINT.value: ("SharePoint", "Reads SharePoint sites and document libraries."),
    DocumentSource.ONEDRIVE.value: ("OneDrive", "Reads files in OneDrive."),
    DocumentSource.CONFLUENCE.value: ("Confluence", "Reads Confluence spaces and pages."),
    DocumentSource.NOTION.value: ("Notion", "Reads Notion pages and databases."),
    DocumentSource.JIRA.value: ("Jira", "Reads Jira issues and comments."),
    DocumentSource.SLACK.value: ("Slack", "Reads messages in Slack channels."),
    DocumentSource.TEAMS.value: ("Microsoft Teams", "Reads messages in Teams channels."),
    DocumentSource.GMAIL.value: ("Gmail", "Reads email in Gmail."),
    DocumentSource.OUTLOOK.value: ("Outlook", "Reads email in Outlook."),
    DocumentSource.SALESFORCE.value: ("Salesforce", "Reads Salesforce records."),
    DocumentSource.HUBSPOT.value: ("HubSpot", "Reads HubSpot records."),
    DocumentSource.ZENDESK.value: ("Zendesk", "Reads Zendesk tickets and help articles."),
    DocumentSource.GITHUB.value: ("GitHub", "Reads GitHub issues, pull requests and files."),
    DocumentSource.BOX.value: ("Box", "Reads files in Box."),
    DocumentSource.DROPBOX.value: ("Dropbox", "Reads files in Dropbox."),
    DocumentSource.WEB.value: ("Website", "Reads pages from a website you choose."),
}


@dataclass
class Item:
    kind: str
    key: str
    name: str
    description: str
    why_approval: str  # why an administrator has to turn it on


def connectors(db: Session) -> list[Item]:
    have = {str(getattr(s, "value", s)) for s in db.scalars(select(Connector.source).distinct())}
    return [Item("connector", k, n, d, "Brings company documents into search; an administrator connects it and sets who can see what.")
            for k, (n, d) in CONNECTORS.items() if k not in have]


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
        if t.personal or (t.allowed and t.core_enabled):
            continue
        why = "Calls a system outside the workspace; its definition has to be approved." if t.kind == "outside" else \
            "Runs code the model writes." if t.kind == "code" else "Turned off for this workspace by an administrator."
        out.append(Item("plugin", str(t.id), t.name, cat.LABEL[t.kind], why))
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
