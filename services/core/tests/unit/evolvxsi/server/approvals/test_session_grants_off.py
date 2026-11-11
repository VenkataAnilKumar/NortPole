"""Governed default: approving for the whole session is off, and each decision is audited."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from evolvxsi.db.enums import ApprovalDecidedVia, ApprovalDecision, GatedAppKind
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.server.features.build.approvals import api as approvals_api
from evolvxsi.utils.audit import AuditAction, AuditOutcome


def _view() -> approvals_api.ApprovalView:
    return approvals_api.ApprovalView.model_construct(
        approval_id=uuid4(),
        session_id=uuid4(),
        actions=[],
        app_name="gmail",
        payload={},
        created_at=datetime.now(timezone.utc),
        decision=None,
        decided_at=None,
        target_kind=GatedAppKind.EXTERNAL_APP,
    )


def test_session_grants_are_off_by_default() -> None:
    assert approvals_api.APPROVAL_SESSION_GRANTS_ENABLED is False
    assert _view().can_approve_for_session is False


def test_submit_decision_refuses_session_wide_approval() -> None:
    body = approvals_api.DecisionBody(decision=approvals_api.ApprovalChoice.APPROVE_SESSION)
    with pytest.raises(EvolvXSIError):
        approvals_api.submit_decision(uuid4(), body, user=MagicMock(), db_session=MagicMock())


def test_decision_is_audited_with_a_fingerprint_and_no_payload_text() -> None:
    row = MagicMock()
    row.approval_id = uuid4()
    row.actions = [{"action_type": "send_email"}]
    row.app_name = "gmail"
    row.payload = {"body": "secret text"}
    row.decision = ApprovalDecision.APPROVED
    row.decided_via = ApprovalDecidedVia.USER
    with patch.object(approvals_api, "record_audit") as rec:
        approvals_api._audit_decision(row, MagicMock())
    args, kwargs = rec.call_args
    assert args[0] is AuditAction.APPROVAL_DECISION and args[1] is AuditOutcome.SUCCESS
    assert len(kwargs["details"]["fingerprint"]) == 64
    assert "secret text" not in str(kwargs)
