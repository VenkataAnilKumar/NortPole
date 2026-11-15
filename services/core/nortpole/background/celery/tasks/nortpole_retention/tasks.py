from celery import shared_task

from nortpole.configs.constants import NortPoleCeleryTask
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.governance.retention.prune import prune
from nortpole.utils.logger import setup_logger

logger = setup_logger()


@shared_task(name=NortPoleCeleryTask.NORTPOLE_RETENTION_PRUNE, ignore_result=True, trail=False)
def nortpole_retention_prune(*, tenant_id: str) -> None:  # noqa: ARG001
    with get_session_with_current_tenant() as db_session:
        out = prune(db_session)
    logger.info("retention prune: %s", out)
