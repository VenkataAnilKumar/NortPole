from celery import shared_task

from evolvxsi.configs.constants import EvolvXSICeleryTask
from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.governance.retention.prune import prune
from evolvxsi.utils.logger import setup_logger

logger = setup_logger()


@shared_task(name=EvolvXSICeleryTask.EVOLVXSI_RETENTION_PRUNE, ignore_result=True, trail=False)
def evolvxsi_retention_prune(*, tenant_id: str) -> None:  # noqa: ARG001
    with get_session_with_current_tenant() as db_session:
        out = prune(db_session)
    logger.info("retention prune: %s", out)
