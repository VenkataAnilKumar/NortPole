"""Registry mapping for connector classes."""

from pydantic import BaseModel

from evolvxsi.configs.constants import DocumentSource
from evolvxsi.connectors.airtable.config import AirtableConnectorConfig
from evolvxsi.connectors.asana.config import AsanaConnectorConfig
from evolvxsi.connectors.axero.config import AxeroConnectorConfig
from evolvxsi.connectors.azure_datalake.config import AzureDataLakeConnectorConfig
from evolvxsi.connectors.bitbucket.config import BitbucketConnectorConfig
from evolvxsi.connectors.blob.config import BlobStorageConnectorConfig
from evolvxsi.connectors.bookstack.config import BookstackConnectorConfig
from evolvxsi.connectors.box.config import BoxConnectorConfig
from evolvxsi.connectors.braintrust.config import BraintrustConnectorConfig
from evolvxsi.connectors.canvas.config import CanvasConnectorConfig
from evolvxsi.connectors.clickup.config import ClickupConnectorConfig
from evolvxsi.connectors.coda.config import CodaConnectorConfig
from evolvxsi.connectors.confluence.config import ConfluenceConnectorConfig
from evolvxsi.connectors.connector_config import ConnectorConfig
from evolvxsi.connectors.discord.config import DiscordConnectorConfig
from evolvxsi.connectors.discourse.config import DiscourseConnectorConfig
from evolvxsi.connectors.document360.config import Document360ConnectorConfig
from evolvxsi.connectors.dropbox.config import DropboxConnectorConfig
from evolvxsi.connectors.drupal_wiki.config import DrupalWikiConnectorConfig
from evolvxsi.connectors.egnyte.config import EgnyteConnectorConfig
from evolvxsi.connectors.file.config import LocalFileConnectorConfig
from evolvxsi.connectors.fireflies.config import FirefliesConnectorConfig
from evolvxsi.connectors.freshdesk.config import FreshdeskConnectorConfig
from evolvxsi.connectors.gitbook.config import GitbookConnectorConfig
from evolvxsi.connectors.github.config import GithubConnectorConfig
from evolvxsi.connectors.gitlab.config import GitlabConnectorConfig
from evolvxsi.connectors.gmail.config import GmailConnectorConfig
from evolvxsi.connectors.gong.config import GongConnectorConfig
from evolvxsi.connectors.google_drive.config import GoogleDriveConnectorConfig
from evolvxsi.connectors.google_site.config import GoogleSitesConnectorConfig
from evolvxsi.connectors.guru.config import GuruConnectorConfig
from evolvxsi.connectors.highspot.config import HighspotConnectorConfig
from evolvxsi.connectors.hubspot.config import HubSpotConnectorConfig
from evolvxsi.connectors.imap.config import ImapConnectorConfig
from evolvxsi.connectors.jira.config import JiraConnectorConfig
from evolvxsi.connectors.linear.config import LinearConnectorConfig
from evolvxsi.connectors.loopio.config import LoopioConnectorConfig
from evolvxsi.connectors.lumapps.config import LumAppsConnectorConfig
from evolvxsi.connectors.mediawiki.config import MediaWikiConnectorConfig
from evolvxsi.connectors.mock_connector.config import MockConnectorConfig
from evolvxsi.connectors.notion.config import NotionConnectorConfig
from evolvxsi.connectors.onedrive.config import OneDriveConnectorConfig
from evolvxsi.connectors.outline.config import OutlineConnectorConfig
from evolvxsi.connectors.outlook.config import OutlookConnectorConfig
from evolvxsi.connectors.productboard.config import ProductboardConnectorConfig
from evolvxsi.connectors.salesforce.config import SalesforceConnectorConfig
from evolvxsi.connectors.sharepoint.config import SharepointConnectorConfig
from evolvxsi.connectors.slab.config import SlabConnectorConfig
from evolvxsi.connectors.slack.config import SlackConnectorConfig
from evolvxsi.connectors.teams.config import TeamsConnectorConfig
from evolvxsi.connectors.testrail.config import TestRailConnectorConfig
from evolvxsi.connectors.web.config import WebConnectorConfig
from evolvxsi.connectors.wikipedia.config import WikipediaConnectorConfig
from evolvxsi.connectors.xenforo.config import XenforoConnectorConfig
from evolvxsi.connectors.youtrack.config import YouTrackConnectorConfig
from evolvxsi.connectors.zendesk.config import ZendeskConnectorConfig
from evolvxsi.connectors.zoom.config import ZoomConnectorConfig
from evolvxsi.connectors.zulip.config import ZulipConnectorConfig


class ConnectorMapping(BaseModel):
    module_path: str
    class_name: str
    config_class: type[ConnectorConfig]


# Mapping of DocumentSource to connector details for lazy loading
CONNECTOR_CLASS_MAP = {
    DocumentSource.WEB: ConnectorMapping(
        module_path="evolvxsi.connectors.web.connector",
        class_name="WebConnector",
        config_class=WebConnectorConfig,
    ),
    DocumentSource.FILE: ConnectorMapping(
        module_path="evolvxsi.connectors.file.connector",
        class_name="LocalFileConnector",
        config_class=LocalFileConnectorConfig,
    ),
    DocumentSource.SLACK: ConnectorMapping(
        module_path="evolvxsi.connectors.slack.connector",
        class_name="SlackConnector",
        config_class=SlackConnectorConfig,
    ),
    DocumentSource.GITHUB: ConnectorMapping(
        module_path="evolvxsi.connectors.github.connector",
        class_name="GithubConnector",
        config_class=GithubConnectorConfig,
    ),
    DocumentSource.GMAIL: ConnectorMapping(
        module_path="evolvxsi.connectors.gmail.connector",
        class_name="GmailConnector",
        config_class=GmailConnectorConfig,
    ),
    DocumentSource.GITLAB: ConnectorMapping(
        module_path="evolvxsi.connectors.gitlab.connector",
        class_name="GitlabConnector",
        config_class=GitlabConnectorConfig,
    ),
    DocumentSource.GITBOOK: ConnectorMapping(
        module_path="evolvxsi.connectors.gitbook.connector",
        class_name="GitbookConnector",
        config_class=GitbookConnectorConfig,
    ),
    DocumentSource.GOOGLE_DRIVE: ConnectorMapping(
        module_path="evolvxsi.connectors.google_drive.connector",
        class_name="GoogleDriveConnector",
        config_class=GoogleDriveConnectorConfig,
    ),
    DocumentSource.BOOKSTACK: ConnectorMapping(
        module_path="evolvxsi.connectors.bookstack.connector",
        class_name="BookstackConnector",
        config_class=BookstackConnectorConfig,
    ),
    DocumentSource.OUTLINE: ConnectorMapping(
        module_path="evolvxsi.connectors.outline.connector",
        class_name="OutlineConnector",
        config_class=OutlineConnectorConfig,
    ),
    DocumentSource.CONFLUENCE: ConnectorMapping(
        module_path="evolvxsi.connectors.confluence.connector",
        class_name="ConfluenceConnector",
        config_class=ConfluenceConnectorConfig,
    ),
    DocumentSource.JIRA: ConnectorMapping(
        module_path="evolvxsi.connectors.jira.connector",
        class_name="JiraConnector",
        config_class=JiraConnectorConfig,
    ),
    DocumentSource.PRODUCTBOARD: ConnectorMapping(
        module_path="evolvxsi.connectors.productboard.connector",
        class_name="ProductboardConnector",
        config_class=ProductboardConnectorConfig,
    ),
    DocumentSource.SLAB: ConnectorMapping(
        module_path="evolvxsi.connectors.slab.connector",
        class_name="SlabConnector",
        config_class=SlabConnectorConfig,
    ),
    DocumentSource.CODA: ConnectorMapping(
        module_path="evolvxsi.connectors.coda.connector",
        class_name="CodaConnector",
        config_class=CodaConnectorConfig,
    ),
    DocumentSource.CANVAS: ConnectorMapping(
        module_path="evolvxsi.connectors.canvas.connector",
        class_name="CanvasConnector",
        config_class=CanvasConnectorConfig,
    ),
    DocumentSource.NOTION: ConnectorMapping(
        module_path="evolvxsi.connectors.notion.connector",
        class_name="NotionConnector",
        config_class=NotionConnectorConfig,
    ),
    DocumentSource.ZULIP: ConnectorMapping(
        module_path="evolvxsi.connectors.zulip.connector",
        class_name="ZulipConnector",
        config_class=ZulipConnectorConfig,
    ),
    DocumentSource.GURU: ConnectorMapping(
        module_path="evolvxsi.connectors.guru.connector",
        class_name="GuruConnector",
        config_class=GuruConnectorConfig,
    ),
    DocumentSource.LINEAR: ConnectorMapping(
        module_path="evolvxsi.connectors.linear.connector",
        class_name="LinearConnector",
        config_class=LinearConnectorConfig,
    ),
    DocumentSource.HUBSPOT: ConnectorMapping(
        module_path="evolvxsi.connectors.hubspot.connector",
        class_name="HubSpotConnector",
        config_class=HubSpotConnectorConfig,
    ),
    DocumentSource.DOCUMENT360: ConnectorMapping(
        module_path="evolvxsi.connectors.document360.connector",
        class_name="Document360Connector",
        config_class=Document360ConnectorConfig,
    ),
    DocumentSource.GONG: ConnectorMapping(
        module_path="evolvxsi.connectors.gong.connector",
        class_name="GongConnector",
        config_class=GongConnectorConfig,
    ),
    DocumentSource.GOOGLE_SITES: ConnectorMapping(
        module_path="evolvxsi.connectors.google_site.connector",
        class_name="GoogleSitesConnector",
        config_class=GoogleSitesConnectorConfig,
    ),
    DocumentSource.ZENDESK: ConnectorMapping(
        module_path="evolvxsi.connectors.zendesk.connector",
        class_name="ZendeskConnector",
        config_class=ZendeskConnectorConfig,
    ),
    DocumentSource.LOOPIO: ConnectorMapping(
        module_path="evolvxsi.connectors.loopio.connector",
        class_name="LoopioConnector",
        config_class=LoopioConnectorConfig,
    ),
    DocumentSource.BOX: ConnectorMapping(
        module_path="evolvxsi.connectors.box.connector",
        class_name="BoxConnector",
        config_class=BoxConnectorConfig,
    ),
    DocumentSource.DROPBOX: ConnectorMapping(
        module_path="evolvxsi.connectors.dropbox.connector",
        class_name="DropboxConnector",
        config_class=DropboxConnectorConfig,
    ),
    DocumentSource.SHAREPOINT: ConnectorMapping(
        module_path="evolvxsi.connectors.sharepoint.connector",
        class_name="SharepointConnector",
        config_class=SharepointConnectorConfig,
    ),
    DocumentSource.ONEDRIVE: ConnectorMapping(
        module_path="evolvxsi.connectors.onedrive.connector",
        class_name="OneDriveConnector",
        config_class=OneDriveConnectorConfig,
    ),
    DocumentSource.TEAMS: ConnectorMapping(
        module_path="evolvxsi.connectors.teams.connector",
        class_name="TeamsConnector",
        config_class=TeamsConnectorConfig,
    ),
    DocumentSource.OUTLOOK: ConnectorMapping(
        module_path="evolvxsi.connectors.outlook.connector",
        class_name="OutlookConnector",
        config_class=OutlookConnectorConfig,
    ),
    DocumentSource.SALESFORCE: ConnectorMapping(
        module_path="evolvxsi.connectors.salesforce.connector",
        class_name="SalesforceConnector",
        config_class=SalesforceConnectorConfig,
    ),
    DocumentSource.DISCOURSE: ConnectorMapping(
        module_path="evolvxsi.connectors.discourse.connector",
        class_name="DiscourseConnector",
        config_class=DiscourseConnectorConfig,
    ),
    DocumentSource.AXERO: ConnectorMapping(
        module_path="evolvxsi.connectors.axero.connector",
        class_name="AxeroConnector",
        config_class=AxeroConnectorConfig,
    ),
    DocumentSource.CLICKUP: ConnectorMapping(
        module_path="evolvxsi.connectors.clickup.connector",
        class_name="ClickupConnector",
        config_class=ClickupConnectorConfig,
    ),
    DocumentSource.MEDIAWIKI: ConnectorMapping(
        module_path="evolvxsi.connectors.mediawiki.wiki",
        class_name="MediaWikiConnector",
        config_class=MediaWikiConnectorConfig,
    ),
    DocumentSource.WIKIPEDIA: ConnectorMapping(
        module_path="evolvxsi.connectors.wikipedia.connector",
        class_name="WikipediaConnector",
        config_class=WikipediaConnectorConfig,
    ),
    DocumentSource.ASANA: ConnectorMapping(
        module_path="evolvxsi.connectors.asana.connector",
        class_name="AsanaConnector",
        config_class=AsanaConnectorConfig,
    ),
    DocumentSource.S3: ConnectorMapping(
        module_path="evolvxsi.connectors.blob.connector",
        class_name="BlobStorageConnector",
        config_class=BlobStorageConnectorConfig,
    ),
    DocumentSource.R2: ConnectorMapping(
        module_path="evolvxsi.connectors.blob.connector",
        class_name="BlobStorageConnector",
        config_class=BlobStorageConnectorConfig,
    ),
    DocumentSource.GOOGLE_CLOUD_STORAGE: ConnectorMapping(
        module_path="evolvxsi.connectors.blob.connector",
        class_name="BlobStorageConnector",
        config_class=BlobStorageConnectorConfig,
    ),
    DocumentSource.OCI_STORAGE: ConnectorMapping(
        module_path="evolvxsi.connectors.blob.connector",
        class_name="BlobStorageConnector",
        config_class=BlobStorageConnectorConfig,
    ),
    DocumentSource.XENFORO: ConnectorMapping(
        module_path="evolvxsi.connectors.xenforo.connector",
        class_name="XenforoConnector",
        config_class=XenforoConnectorConfig,
    ),
    DocumentSource.DISCORD: ConnectorMapping(
        module_path="evolvxsi.connectors.discord.connector",
        class_name="DiscordConnector",
        config_class=DiscordConnectorConfig,
    ),
    DocumentSource.FRESHDESK: ConnectorMapping(
        module_path="evolvxsi.connectors.freshdesk.connector",
        class_name="FreshdeskConnector",
        config_class=FreshdeskConnectorConfig,
    ),
    DocumentSource.FIREFLIES: ConnectorMapping(
        module_path="evolvxsi.connectors.fireflies.connector",
        class_name="FirefliesConnector",
        config_class=FirefliesConnectorConfig,
    ),
    DocumentSource.ZOOM: ConnectorMapping(
        module_path="evolvxsi.connectors.zoom.connector",
        class_name="ZoomConnector",
        config_class=ZoomConnectorConfig,
    ),
    DocumentSource.EGNYTE: ConnectorMapping(
        module_path="evolvxsi.connectors.egnyte.connector",
        class_name="EgnyteConnector",
        config_class=EgnyteConnectorConfig,
    ),
    DocumentSource.AIRTABLE: ConnectorMapping(
        module_path="evolvxsi.connectors.airtable.airtable_connector",
        class_name="AirtableConnector",
        config_class=AirtableConnectorConfig,
    ),
    DocumentSource.HIGHSPOT: ConnectorMapping(
        module_path="evolvxsi.connectors.highspot.connector",
        class_name="HighspotConnector",
        config_class=HighspotConnectorConfig,
    ),
    DocumentSource.DRUPAL_WIKI: ConnectorMapping(
        module_path="evolvxsi.connectors.drupal_wiki.connector",
        class_name="DrupalWikiConnector",
        config_class=DrupalWikiConnectorConfig,
    ),
    DocumentSource.IMAP: ConnectorMapping(
        module_path="evolvxsi.connectors.imap.connector",
        class_name="ImapConnector",
        config_class=ImapConnectorConfig,
    ),
    DocumentSource.BITBUCKET: ConnectorMapping(
        module_path="evolvxsi.connectors.bitbucket.connector",
        class_name="BitbucketConnector",
        config_class=BitbucketConnectorConfig,
    ),
    DocumentSource.TESTRAIL: ConnectorMapping(
        module_path="evolvxsi.connectors.testrail.connector",
        class_name="TestRailConnector",
        config_class=TestRailConnectorConfig,
    ),
    DocumentSource.BRAINTRUST: ConnectorMapping(
        module_path="evolvxsi.connectors.braintrust.connector",
        class_name="BraintrustConnector",
        config_class=BraintrustConnectorConfig,
    ),
    DocumentSource.LUMAPPS: ConnectorMapping(
        module_path="evolvxsi.connectors.lumapps.connector",
        class_name="LumAppsConnector",
        config_class=LumAppsConnectorConfig,
    ),
    DocumentSource.YOUTRACK: ConnectorMapping(
        module_path="evolvxsi.connectors.youtrack.connector",
        class_name="YouTrackConnector",
        config_class=YouTrackConnectorConfig,
    ),
    DocumentSource.AZURE_DATALAKE: ConnectorMapping(
        module_path="evolvxsi.connectors.azure_datalake.connector",
        class_name="AzureDataLakeConnector",
        config_class=AzureDataLakeConnectorConfig,
    ),
    # just for integration tests
    DocumentSource.MOCK_CONNECTOR: ConnectorMapping(
        module_path="evolvxsi.connectors.mock_connector.connector",
        class_name="MockConnector",
        config_class=MockConnectorConfig,
    ),
}
