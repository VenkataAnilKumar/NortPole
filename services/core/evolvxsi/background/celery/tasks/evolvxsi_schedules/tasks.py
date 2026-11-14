from celery import shared_task

from evolvxsi.configs.constants import EvolvXSICeleryTask
from evolvxsi.utils.logger import setup_logger
from evolvxsi.workflow_schedules.runner import run_due

logger = setup_logger()


@shared_task(name=EvolvXSICeleryTask.EVOLVXSI_WORKFLOW_SCHEDULES, ignore_result=True, trail=False)
def evolvxsi_workflow_schedules(*, tenant_id: str) -> None:  # noqa: ARG001
    """Fire scheduled workflows that are due. Each run drafts a plan for its owner and stops there."""
    fired = run_due()
    if fired:
        logger.info("scheduled workflows fired: %d", fired)
