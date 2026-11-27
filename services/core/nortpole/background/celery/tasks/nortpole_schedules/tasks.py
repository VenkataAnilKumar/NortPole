from uuid import UUID

from celery import shared_task

from nortpole.configs.constants import NortPoleCeleryTask
from nortpole.utils.logger import setup_logger
from nortpole.work.workflow_schedules.proposals import process_confirmed
from nortpole.work.workflow_schedules.runner import run_due

logger = setup_logger()


@shared_task(name=NortPoleCeleryTask.NORTPOLE_WORKFLOW_SCHEDULES, ignore_result=True, trail=False)
def nortpole_workflow_schedules(*, tenant_id: str) -> None:  # noqa: ARG001
    """Fire scheduled workflows that are due. Each run drafts a plan for its owner and stops there."""
    fired = run_due()
    if fired:
        logger.info("scheduled workflows fired: %d", fired)
    process_confirmed()


@shared_task(name=NortPoleCeleryTask.NORTPOLE_EXECUTE_SCHEDULE_PROPOSAL, ignore_result=True, trail=False)
def execute_schedule_proposal(*, tenant_id: str, proposal_id: str) -> None:  # noqa: ARG001
    process_confirmed(UUID(proposal_id))
