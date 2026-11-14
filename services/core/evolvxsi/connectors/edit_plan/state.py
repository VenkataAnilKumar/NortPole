from sqlalchemy.orm import Session

from evolvxsi.connectors.edit_plan.models import CurrentPairState, ProposedPairState
from evolvxsi.connectors.factory import assert_user_can_use_credential
from evolvxsi.db.connector_credential_pair import get_connector_credential_pair_from_id
from evolvxsi.db.credentials import credential_usable_for_source, fetch_credential_by_id
from evolvxsi.db.models import Credential, User, UserGroup
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError


def fetch_current_pair_state(db_session: Session, cc_pair_id: int) -> CurrentPairState:
    """The pair's stored state, in the shape an edit proposes. Data-access
    groups are an EE feature; CE pairs have none.

    Raises:
        EvolvXSIError: CONNECTOR_NOT_FOUND when the pair does not exist.
    """
    cc_pair = get_connector_credential_pair_from_id(
        db_session, cc_pair_id, eager_load_connector=True
    )
    if cc_pair is None:
        raise EvolvXSIError(
            EvolvXSIErrorCode.CONNECTOR_NOT_FOUND,
            f"Connector-credential pair {cc_pair_id} does not exist.",
        )
    # NortPole: read the real groups (the community copy returned none).
    from evolvxsi.knowledge.knowledge_access.source_groups import fetch_data_access_groups_for_cc_pair

    data_access_groups: list[UserGroup] = fetch_data_access_groups_for_cc_pair(db_session, cc_pair_id)
    connector = cc_pair.connector
    return CurrentPairState(
        cc_pair_id=cc_pair.id,
        connector_id=connector.id,
        status=cc_pair.status,
        source=connector.source,
        input_type=connector.input_type,
        connector_specific_config=connector.connector_specific_config,
        access_type=cc_pair.access_type,
        data_access_group_ids=[group.id for group in data_access_groups],
        credential_id=cc_pair.credential_id,
        indexing_start=connector.indexing_start,
        name=cc_pair.name,
        refresh_freq=connector.refresh_freq,
        prune_freq=connector.prune_freq,
        check_freq=connector.check_freq,
    )


def fetch_proposed_credential(
    db_session: Session,
    *,
    user: User,
    current: CurrentPairState,
    proposed: ProposedPairState,
) -> Credential:
    """The credential the edit leaves the pair with, after
    ``assert_user_can_use_credential`` with the proposed config. The pair's own
    credential with unchanged bound values needs nothing more than the pair
    access the caller checked.

    Raises:
        EvolvXSIError: CREDENTIAL_NOT_FOUND when the credential does not exist or
            the user cannot see it; INVALID_INPUT when the source cannot use
            it; INSUFFICIENT_PERMISSIONS when the user may not use it with the
            proposed config.
    """
    credential = fetch_credential_by_id(proposed.credential_id, db_session)
    if credential is None:
        raise EvolvXSIError(
            EvolvXSIErrorCode.CREDENTIAL_NOT_FOUND,
            f"Credential {proposed.credential_id} does not exist.",
        )
    if not credential_usable_for_source(credential, current.source):
        raise EvolvXSIError(
            EvolvXSIErrorCode.INVALID_INPUT,
            f"Credential {credential.id} cannot be used by a "
            f"{current.source.value} connector.",
        )
    assert_user_can_use_credential(
        db_session,
        user=user,
        credential=credential,
        source=current.source,
        connector_specific_config=proposed.connector_specific_config,
        current_pair=get_connector_credential_pair_from_id(
            db_session, current.cc_pair_id, eager_load_connector=True
        ),
    )
    return credential
