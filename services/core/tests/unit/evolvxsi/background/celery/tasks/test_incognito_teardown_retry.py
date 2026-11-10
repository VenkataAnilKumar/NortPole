from unittest.mock import MagicMock, patch

import pytest

from evolvxsi.background.celery.tasks.user_file_processing.tasks import (
    check_for_incognito_file_cleanup,
)
from evolvxsi.chat.incognito_context import _enqueue_incognito_teardown_retry
from evolvxsi.configs.constants import EvolvXSICeleryTask

TASK_MODULE: str = "evolvxsi.background.celery.tasks.user_file_processing.tasks"


def test_retry_is_queued_for_the_current_tenant_after_the_lock_lease() -> None:
    app: MagicMock
    with patch("evolvxsi.background.celery.versioned_apps.client.app") as app:
        with patch(
            "shared_configs.contextvars.get_current_tenant_id", return_value="tenant-a"
        ):
            _enqueue_incognito_teardown_retry()
    app.send_task.assert_called_once_with(
        EvolvXSICeleryTask.CHECK_FOR_INCOGNITO_FILE_CLEANUP,
        kwargs={"tenant_id": "tenant-a"},
        countdown=60.0,
        expires=600,
    )


@pytest.mark.parametrize("database_fails", [False, True])
def test_cleanup_retries_context_before_generated_files(database_fails: bool) -> None:
    redis_client: MagicMock
    retry: MagicMock
    session: MagicMock
    with (
        patch(f"{TASK_MODULE}.get_redis_client") as redis_client,
        patch(f"{TASK_MODULE}.retry_incognito_teardowns") as retry,
        patch(f"{TASK_MODULE}.get_session_with_current_tenant") as session,
        patch(f"{TASK_MODULE}.sweep_incognito_generated_files"),
    ):
        if database_fails:
            session.side_effect = RuntimeError("database unavailable")
            with pytest.raises(RuntimeError, match="database unavailable"):
                check_for_incognito_file_cleanup.run(tenant_id="tenant-a")  # ty: ignore[invalid-argument-type]
        else:
            check_for_incognito_file_cleanup.run(tenant_id="tenant-a")  # ty: ignore[invalid-argument-type]
        retry.assert_called_once_with()
        redis_client.return_value.lock.return_value.release.assert_called_once_with()
