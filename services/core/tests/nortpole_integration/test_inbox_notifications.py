"""Inbox filters and counts against the real notifications table."""

from uuid import uuid4

import pytest

from nortpole.configs.constants import NotificationType
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import User
from nortpole.db.notification import InboxTab, create_notification
from nortpole.server.features.notifications import api
from tests.nortpole_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")


def test_inbox_counts_and_pages_include_older_private_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api, "_ensure_system_announcement_notification", lambda *_: True
    )
    monkeypatch.setattr(api, "_ensure_license_expiry_notification", lambda *_: True)
    with get_session_with_current_tenant() as db:
        user, other = (
            User(id=uuid4(), email=f"inbox-{uuid4()}@example.com", hashed_password="x")
            for _ in range(2)
        )
        db.add_all([user, other])
        db.flush()

        def make(
            kind: NotificationType, title: str, *, owner: User = user, **metadata: str
        ):
            return create_notification(
                owner.id,
                kind,
                db,
                title,
                additional_data={"key": title, **metadata},
                autocommit=False,
            )

        approval = make(NotificationType.APPROVAL_REQUESTED, "Older approval")
        review = make(NotificationType.DOCUMENT_REVIEW_NEEDS_REVIEW, "Older review")
        make(NotificationType.APPROVAL_REQUESTED, "Other user", owner=other)
        make(
            NotificationType.APPROVAL_REQUESTED,
            "Craft notification",
            approval_id=str(uuid4()),
        )
        task = str(uuid4())
        plan = make(NotificationType.WORKFLOW_PLAN_READY, "Plan ready", task_id=task)
        draft = make(NotificationType.WORKFLOW_RUN_COMPLETE, "Draft ready", task_id=task)
        decision = make(NotificationType.WORKFLOW_DECISION_RECORDED, "Accepted", task_id=task)
        make(NotificationType.WORKFLOW_DECISION_RECORDED, "Other decision", owner=other)
        standalone = make(NotificationType.WORKFLOW_RUN_COMPLETE, "Review finished")
        plan.dismissed = True
        db.flush()
        for i in range(55):
            make(NotificationType.WORKFLOW_RUN_FAILED, f"Update {i}")

        counts = api.get_inbox_summary_api(user=user, db_session=db)
        assert counts.model_dump() == {
            "approve": 1,
            "review": 1,
            "updates": 57,
            "dismissed": 0,
            "history": 3,
        }
        for tab, expected in ((InboxTab.APPROVE, approval), (InboxTab.REVIEW, review)):
            page = api.get_notifications_api(
                0, 50, user=user, db_session=db, inbox_tab=tab
            )
            assert [n.id for n in page.notifications] == [expected.id]
            assert not page.has_more

        page = api.get_notifications_api(
            1, 50, user=user, db_session=db, inbox_tab=InboxTab.UPDATES
        )
        assert len(page.notifications) == 7
        assert page.total_items == 57
        assert not page.has_more

        workflow_history = api.get_notifications_api(
            0, 50, user=user, db_session=db, inbox_tab=InboxTab.HISTORY
        )
        assert {n.id for n in workflow_history.notifications} == {plan.id, draft.id, decision.id}
        updates = api.get_notifications_api(
            0, 100, user=user, db_session=db, inbox_tab=InboxTab.UPDATES
        )
        assert standalone.id in {n.id for n in updates.notifications}

        approval.dismissed = True
        db.flush()
        counts = api.get_inbox_summary_api(user=user, db_session=db)
        assert counts.approve == 0
        assert counts.dismissed == 1
        history = api.get_notifications_api(
            0, 50, user=user, db_session=db, inbox_tab=InboxTab.DISMISSED
        )
        assert [n.id for n in history.notifications] == [approval.id]
        assert history.undismissed_count == 0
