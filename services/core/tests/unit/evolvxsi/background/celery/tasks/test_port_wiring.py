"""Guards the Celery wiring of the reindex-port flow.

The port logic itself is covered by the external_dependency_unit `db/test_*port*`
suites (which run against real Postgres/OpenSearch). Those mock the celery app, so
nothing there proves a beat-enqueued port task actually reaches a worker. These
unit tests guard exactly that transport seam — the part a dropped autodiscover line
or `-Q` entry would silently break with every other test still green:

  beat schedules check_for_port  ->  docprocessing worker consumes the `port` queue
  ->  docprocessing worker has run_port_attempt registered to execute it.
"""

import re

from evolvxsi.background.celery.tasks.beat_schedule import beat_task_templates
from evolvxsi.configs.app_configs import DISABLE_VECTOR_DB
from evolvxsi.configs.constants import EvolvXSICeleryQueues, EvolvXSICeleryTask
from tests.common.paths import find_ancestor_containing


# NortPole deploys the workers from its own compose profile (upstream used supervisord): the retrieval profile
# starts each worker with a `celery -A ...<app> worker -Q a,b,c` line.
_RETRIEVAL_COMPOSE = (
    find_ancestor_containing("infrastructure/profiles/staging")
    / "infrastructure/profiles/staging/docker-compose.retrieval.yml"
)


def _worker_queues(app: str) -> set[str]:
    """The `-Q` queue set the compose profile's worker for celery app `app` consumes."""
    text = _RETRIEVAL_COMPOSE.read_text()
    match = re.search(rf"celery -A \S*\.{re.escape(app)} worker -Q\s+(\S+)", text)
    if match is None:
        raise AssertionError(f"no `{app}` worker with -Q queues in {_RETRIEVAL_COMPOSE.name}")
    return set(match.group(1).split(","))


def test_check_for_port_scheduled_in_beat() -> None:
    # check_for_port is the only producer of PortAttempts; if it falls out of the
    # beat schedule the whole flow stops with zero other test failures.
    scheduled = {t["task"] for t in beat_task_templates}
    if DISABLE_VECTOR_DB:
        # Vector-DB-gated: must be filtered out of minimal-mode deployments.
        assert EvolvXSICeleryTask.CHECK_FOR_PORT not in scheduled
    else:
        assert EvolvXSICeleryTask.CHECK_FOR_PORT in scheduled


def test_docprocessing_worker_consumes_port_queue() -> None:
    # run_port_attempt is enqueued to the PORT queue; the docprocessing worker is its
    # only consumer. Dropping `port` from this `-Q` list strands every port task.
    assert EvolvXSICeleryQueues.PORT in _worker_queues("docprocessing")


def test_docprocessing_worker_registers_port_tasks() -> None:
    # Consuming the queue is moot if autodiscovery doesn't register the task body:
    # the worker would reject it as unknown. Importing + loading the docprocessing app
    # mirrors worker bootstrap, so run_port_attempt must resolve by name.
    from evolvxsi.background.celery.apps.docprocessing import celery_app

    celery_app.loader.import_default_modules()
    registered = set(celery_app.tasks.keys())
    assert EvolvXSICeleryTask.RUN_PORT_ATTEMPT in registered
