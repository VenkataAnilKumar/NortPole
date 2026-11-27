from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from nortpole.chat.agent_releases import (
    AgentPublishRequest,
    AgentRollbackRequest,
    AgentVerificationRequest,
    pinned_agent_release,
    publish_agent_release,
    rollback_agent_release,
    set_agent_verification,
    validate_agent_release_dependencies,
)
from nortpole.db.agent_preview import AgentPreview, AgentPreviewDraft
from nortpole.db.enums import Permission
from nortpole.db.models import AgentRelease, ChatSession, Persona, User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError


def _release(version: int, *, is_active: bool) -> AgentRelease:
    timestamp = datetime.now(timezone.utc)
    user_id = uuid4()
    return AgentRelease(
        id=version, version=version, persona_id=10, is_active=is_active,
        configuration=AgentPreview(name="Research", system_prompt="Answer from sources", model_configuration_id=2),
        dependency_fingerprint="stored", test_chat_id=uuid4(), test_response_id=42,
        tested_at=timestamp, published_at=timestamp, tested_by=user_id, published_by=user_id,
    )


def test_pinned_versions_survive_new_publication_and_stop_after_withdrawal() -> None:
    db = MagicMock(spec=Session)
    chat = ChatSession(persona_id=10, agent_release_id=1)
    previous = _release(1, is_active=False)
    db.get.return_value = previous

    assert pinned_agent_release(chat, db) is previous

    previous.withdrawn_at = datetime.now(timezone.utc)
    with pytest.raises(NortPoleError, match="Start a new chat"):
        pinned_agent_release(chat, db)


def test_rollback_withdraws_active_version_after_validating_target() -> None:
    db = MagicMock(spec=Session)
    owner = User(id=uuid4(), email="owner@example.test")
    db.get.return_value = Persona(id=10, user_id=owner.id)
    latest, target = _release(2, is_active=True), _release(1, is_active=False)
    db.scalar.side_effect = [latest, target]

    with patch("nortpole.chat.agent_releases.validate_agent_release_dependencies") as validate:
        restored = rollback_agent_release(10, AgentRollbackRequest(version=1, expected_active_version=2), owner, db)

    assert restored.version == 1
    assert target.is_active is True
    assert not latest.is_active and latest.withdrawn_by == owner.id
    validate.assert_called_once()
    db.commit.assert_called_once()


def test_publish_checks_saved_draft_before_activating_test() -> None:
    db = MagicMock(spec=Session)
    owner = User(id=uuid4(), email="owner@example.test")
    active = _release(1, is_active=True)
    persona = Persona(id=10, user_id=owner.id, agent_release_draft=AgentPreviewDraft(
        name="Research", system_prompt="Untested change", model_configuration_id=2,
    ))
    chat = ChatSession(id=uuid4(), persona_id=10, user_id=owner.id,
        agent_preview=active.configuration, agent_preview_fingerprint="stored")
    db.get.side_effect = [persona, chat]
    db.scalar.return_value = active
    db.execute.return_value.one_or_none.return_value = MagicMock()

    with pytest.raises(NortPoleError, match="saved draft differs") as denied:
        publish_agent_release(10, AgentPublishRequest(
            expected_active_version=1, preview_chat_id=chat.id, test_response_id=42,
        ), owner, db)

    assert denied.value.error_code == NortPoleErrorCode.CONFLICT
    assert active.is_active
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_changed_dependency_rejects_earlier_test() -> None:
    release = _release(1, is_active=True)
    with (
        patch("nortpole.chat.agent_releases.preview_library_names", return_value=[]),
        patch("nortpole.chat.agent_releases.require_preview_model"),
        patch("nortpole.chat.agent_releases.agent_configuration_fingerprint", return_value="new"),
        pytest.raises(NortPoleError, match="Test the configuration again"),
    ):
        validate_agent_release_dependencies(release.configuration, release.dependency_fingerprint,
            Persona(id=10), User(id=uuid4()), MagicMock(spec=Session))


def test_only_global_agent_managers_can_verify_a_release() -> None:
    db = MagicMock(spec=Session)
    owner = User(id=uuid4(), email="owner@example.test", effective_permissions=[])
    with pytest.raises(NortPoleError) as denied:
        set_agent_verification(10, AgentVerificationRequest(version=1, verified=True), owner, db)

    assert denied.value.error_code == NortPoleErrorCode.INSUFFICIENT_PERMISSIONS
    db.get.assert_not_called()


def test_verification_records_exact_release_and_retries_are_idempotent() -> None:
    db = MagicMock(spec=Session)
    admin = User(
        id=uuid4(), email="admin@example.test",
        effective_permissions=[Permission.MANAGE_AGENTS.value],
    )
    db.get.return_value = Persona(id=10, is_public=True, is_listed=True)
    release = _release(2, is_active=True)
    db.scalar.return_value = release
    grant = AgentVerificationRequest(version=2, verified=True)
    with (
        patch("nortpole.chat.agent_releases.validate_agent_release_dependencies") as validate,
        patch("nortpole.chat.agent_releases.record_audit") as audit,
    ):
        marked = set_agent_verification(10, grant, admin, db)
        retried = set_agent_verification(10, grant, admin, db)
        assert marked.verified_by == admin.id
        assert marked.verified_at is not None and retried.verified_at == marked.verified_at
        assert audit.call_count == 1

        # An administrator can revoke a historical review before a rollback.
        release.is_active = False
        db.get.return_value.is_listed = False
        removed = set_agent_verification(10, AgentVerificationRequest(version=2, verified=False), admin, db)
        assert removed.verified_at is None and removed.verified_by is None
        assert audit.call_count == 2

    assert validate.call_count == 2
    assert db.commit.call_count == 2


@pytest.mark.parametrize(
    ("listed", "active", "code"),
    [
        (False, True, NortPoleErrorCode.INVALID_INPUT),
        (True, False, NortPoleErrorCode.CONFLICT),
    ],
)
def test_grant_rejects_unlisted_or_inactive_versions(listed, active, code) -> None:
    db = MagicMock(spec=Session)
    admin = User(id=uuid4(), effective_permissions=[Permission.MANAGE_AGENTS.value])
    db.get.return_value = Persona(id=10, is_public=True, is_listed=listed)
    db.scalar.return_value = _release(1, is_active=active)
    with pytest.raises(NortPoleError) as rejected:
        set_agent_verification(10, AgentVerificationRequest(version=1, verified=True), admin, db)
    assert rejected.value.error_code == code
    db.commit.assert_not_called()
