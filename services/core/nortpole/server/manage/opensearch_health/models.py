from pydantic import BaseModel

from nortpole.document_index.opensearch.models import ResourceHealth


class ResourcePopupResponse(BaseModel):
    show_popup: bool
    health: ResourceHealth
