"""Rollout gate for query-time cc-pair access filtering."""

from sqlalchemy.orm import Session

from evolvxsi.context.search.models import CCPairAccessMode
from evolvxsi.document_index.opensearch.cc_pair_ids_backfill import (
    is_cc_pair_ids_backfill_complete,
)
from evolvxsi.server.runtime.evolvxsi_runtime import EvolvXSIRuntime


def get_cc_pair_access_mode(db_session: Session) -> CCPairAccessMode | None:
    """None when the cc-pair filter is off. ENFORCE only when the enforce flag
    is on and every cc-pair of this tenant's index has cc_pair_ids on its
    chunks; otherwise SHADOW."""
    if not EvolvXSIRuntime.get_cc_pair_access_filter_enabled():
        return None
    if EvolvXSIRuntime.get_cc_pair_access_filter_enforce() and (
        is_cc_pair_ids_backfill_complete(db_session)
    ):
        return CCPairAccessMode.ENFORCE
    return CCPairAccessMode.SHADOW
