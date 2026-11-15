"""A document the pipeline fails to index must not be reported as ingested."""

from unittest.mock import MagicMock, patch

import pytest

from nortpole.connectors.models import DocumentBase, TextSection
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.indexing.indexing_pipeline import IndexingPipelineResult
from nortpole.server.nortpole_api import ingestion
from nortpole.server.nortpole_api.models import IngestionDocument


def _call(result: IndexingPipelineResult):  # type: ignore[no-untyped-def]
    doc = IngestionDocument(
        document=DocumentBase(id="d1", sections=[TextSection(text="hello", link="x")], semantic_identifier="D", metadata={}),
        cc_pair_id=5,
    )
    cc_pair = MagicMock(connector_id=1, credential_id=1)
    p = "nortpole.server.nortpole_api.ingestion."
    with patch(p + "get_connector_credential_pair_from_id", return_value=cc_pair), \
         patch(p + "verify_user_has_access_to_cc_pair", return_value=True), \
         patch(p + "get_cc_pair_ids_for_document", return_value=[]), \
         patch(p + "verify_user_can_manage_all_cc_pairs", return_value=True), \
         patch(p + "get_user_file_by_id", return_value=None), \
         patch(p + "get_active_search_settings", return_value=MagicMock(primary=MagicMock(id=1), secondary=None)), \
         patch(p + "get_default_document_index"), \
         patch(p + "DefaultIndexingEmbedder"), \
         patch(p + "DocumentIndexingBatchAdapter"), \
         patch(p + "get_current_tenant_id", return_value="public"), \
         patch(p + "run_indexing_pipeline", return_value=result):
        return ingestion.upsert_ingestion_doc(doc, user=MagicMock(id="u"), db_session=MagicMock())


def test_an_embedding_failure_is_an_error_not_a_success() -> None:
    from nortpole.connectors.models import ConnectorFailure, DocumentFailure

    failure = ConnectorFailure(
        failed_document=DocumentFailure(document_id="d1", document_link=None), failure_message="embed failed"
    )
    failed = IndexingPipelineResult(new_docs=0, total_docs=1, total_chunks=0, failures=[failure])
    with pytest.raises(NortPoleError) as err:
        _call(failed)
    assert "could not be indexed" in err.value.detail


def test_a_clean_run_still_succeeds() -> None:
    ok = IndexingPipelineResult(new_docs=1, total_docs=1, total_chunks=1, failures=[])
    assert _call(ok).document_id == "d1"
