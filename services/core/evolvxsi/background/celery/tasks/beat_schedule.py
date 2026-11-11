import copy
from datetime import timedelta
from typing import Any

from celery.schedules import crontab

from evolvxsi.configs.app_configs import (
    AUTO_LLM_CONFIG_URL,
    DISABLE_TELEMETRY,
    DISABLE_VECTOR_DB,
    SCHEDULED_EVAL_DATASET_NAMES,
    TABULAR_RECHUNK_ENABLED,
)
from evolvxsi.configs.constants import (
    EVOLVXSI_CLOUD_CELERY_TASK_PREFIX,
    EvolvXSICeleryPriority,
    EvolvXSICeleryQueues,
    EvolvXSICeleryTask,
)
from evolvxsi.document_index.opensearch.constants import (
    RESOURCE_CHECK_INTERVAL_SECONDS,
)
from evolvxsi.server.features.build.configs import SANDBOX_IDLE_CLEANUP_INTERVAL_SECONDS
from evolvxsi.utils.fleet_telemetry import COLLECTION_INTERVAL_SECONDS
from evolvxsi.utils.variable_functionality import is_ee_available
from shared_configs.configs import AUTO_LLM_UPDATE_INTERVAL_SECONDS, MULTI_TENANT

# choosing 15 minutes because it roughly gives us enough time to process many tasks
# we might be able to reduce this greatly if we can run a unified
# loop across all tenants rather than tasks per tenant

# we set expires because it isn't necessary to queue up these tasks
# it's only important that they run relatively regularly
BEAT_EXPIRES_DEFAULT = 15 * 60  # 15 minutes (in seconds)

# Under the re-chunk interval: the tick resumes from a stored cursor, so one
# that waited longer than that has no value.
TABULAR_RECHUNK_EXPIRES = 4 * 60  # 4 minutes (in seconds)

# hack to slow down task dispatch in the cloud until
# we have a better implementation (backpressure, etc)
# Note that DynamicTenantScheduler can adjust the runtime value for this via Redis
CLOUD_BEAT_MULTIPLIER_DEFAULT = 8.0
CLOUD_DOC_PERMISSION_SYNC_MULTIPLIER_DEFAULT = 1.0

# tasks that run in either self-hosted on cloud
beat_task_templates: list[dict] = [
    {
        "name": "cleanup-oauth-provider-grants",
        "task": EvolvXSICeleryTask.CLEANUP_OAUTH_PROVIDER_GRANTS,
        "schedule": timedelta(days=1),
        "options": {
            "queue": EvolvXSICeleryQueues.PRIMARY,
            "priority": EvolvXSICeleryPriority.LOW,
            "expires": BEAT_EXPIRES_DEFAULT,
            "skip_gated": False,
            "work_gated": True,
        },
    },
    {
        "name": "check-for-user-file-processing",
        "task": EvolvXSICeleryTask.CHECK_FOR_USER_FILE_PROCESSING,
        "schedule": timedelta(seconds=20),
        "options": {
            "priority": EvolvXSICeleryPriority.MEDIUM,
            "expires": BEAT_EXPIRES_DEFAULT,
        },
    },
    {
        "name": "check-for-incognito-file-cleanup",
        "task": EvolvXSICeleryTask.CHECK_FOR_INCOGNITO_FILE_CLEANUP,
        "schedule": timedelta(minutes=10),
        "options": {
            "priority": EvolvXSICeleryPriority.LOW,
            "expires": BEAT_EXPIRES_DEFAULT,
            # Run on gated tenants too, their registries hold blob handles.
            "skip_gated": False,
            "work_gated": True,
        },
    },
    {
        "name": "check-for-user-file-project-sync",
        "task": EvolvXSICeleryTask.CHECK_FOR_USER_FILE_PROJECT_SYNC,
        "schedule": timedelta(seconds=20),
        "options": {
            "priority": EvolvXSICeleryPriority.MEDIUM,
            "expires": BEAT_EXPIRES_DEFAULT,
        },
    },
    {
        "name": "check-for-user-file-delete",
        "task": EvolvXSICeleryTask.CHECK_FOR_USER_FILE_DELETE,
        "schedule": timedelta(seconds=20),
        "options": {
            "priority": EvolvXSICeleryPriority.MEDIUM,
            "expires": BEAT_EXPIRES_DEFAULT,
        },
    },
    {
        "name": "check-for-indexing",
        "task": EvolvXSICeleryTask.CHECK_FOR_INDEXING,
        "schedule": timedelta(seconds=15),
        "options": {
            "priority": EvolvXSICeleryPriority.MEDIUM,
            "expires": BEAT_EXPIRES_DEFAULT,
            "work_gated": True,
        },
    },
    {
        "name": "check-for-port",
        "task": EvolvXSICeleryTask.CHECK_FOR_PORT,
        "schedule": timedelta(seconds=30),
        "options": {
            "priority": EvolvXSICeleryPriority.MEDIUM,
            "expires": BEAT_EXPIRES_DEFAULT,
            # Intentionally gated (skip_gated defaults True): don't run the port's
            # expensive re-embed for non-paying tenants; it pauses and self-heals on un-gate.
            "work_gated": True,
        },
    },
    {
        "name": "check-for-old-index-reclaim",
        "task": EvolvXSICeleryTask.CHECK_FOR_OLD_INDEX_RECLAIM,
        "schedule": timedelta(minutes=30),
        "options": {
            "priority": EvolvXSICeleryPriority.MEDIUM,
            "expires": BEAT_EXPIRES_DEFAULT,
            # Run on gated tenants too — freeing our storage matters most for non-paying
            # tenants. Safe because the PAST + is_active_port_backfill_source gates only
            # reclaim an index once its reindex has truly completed (a gated tenant's
            # deferred reindex never swaps / never drains, so it's never fetched).
            "skip_gated": False,
            "work_gated": True,
        },
    },
    {
        "name": "check-for-checkpoint-cleanup",
        "task": EvolvXSICeleryTask.CHECK_FOR_CHECKPOINT_CLEANUP,
        "schedule": timedelta(hours=1),
        "options": {
            "priority": EvolvXSICeleryPriority.LOW,
            "expires": BEAT_EXPIRES_DEFAULT,
            # Run on gated tenants too — they may still have stale checkpoints to clean.
            "skip_gated": False,
            "work_gated": True,
        },
    },
    {
        "name": "check-for-staged-connector-file-cleanup",
        "task": EvolvXSICeleryTask.CHECK_FOR_STAGED_CONNECTOR_FILE_CLEANUP,
        "schedule": timedelta(hours=1),
        "options": {
            "priority": EvolvXSICeleryPriority.LOW,
            "expires": BEAT_EXPIRES_DEFAULT,
            # Gated tenants may still hold staged uploads to delete.
            "skip_gated": False,
            "work_gated": True,
        },
    },
    {
        # Runs monthly (x8 in cloud, with the beat multiplier) because it rarely
        # has work. It selects by age, so the cadence does not decide what is stale.
        "name": "cleanup-stale-draft-credentials",
        "task": EvolvXSICeleryTask.CLEANUP_STALE_DRAFT_CREDENTIALS,
        "schedule": timedelta(days=30),
        "options": {
            "queue": EvolvXSICeleryQueues.PRIMARY,
            "priority": EvolvXSICeleryPriority.LOW,
            "expires": BEAT_EXPIRES_DEFAULT,
            "skip_gated": False,
            "work_gated": True,
        },
    },
    {
        # Daily: the retention window selects by age, so the cadence only bounds
        # how far past the window a run can live.
        "name": "cleanup-old-capability-check-runs",
        "task": EvolvXSICeleryTask.CLEANUP_OLD_CAPABILITY_CHECK_RUNS,
        "schedule": timedelta(days=1),
        "options": {
            "queue": EvolvXSICeleryQueues.PRIMARY,
            "priority": EvolvXSICeleryPriority.LOW,
            "expires": BEAT_EXPIRES_DEFAULT,
            "skip_gated": False,
            "work_gated": True,
        },
    },
    {
        "name": "check-for-stale-capability-runs",
        "task": EvolvXSICeleryTask.CHECK_FOR_STALE_CAPABILITY_RUNS,
        "schedule": timedelta(minutes=10),
        "options": {
            "priority": EvolvXSICeleryPriority.LOW,
            "expires": BEAT_EXPIRES_DEFAULT,
            # Gated tenants may still hold dead RUNNING marks to retire.
            "skip_gated": False,
            "work_gated": True,
        },
    },
    {
        "name": "check-for-scheduled-capability-checks",
        "task": EvolvXSICeleryTask.CHECK_FOR_SCHEDULED_CAPABILITY_CHECKS,
        "schedule": timedelta(minutes=5),
        "options": {
            "priority": EvolvXSICeleryPriority.LOW,
            "expires": BEAT_EXPIRES_DEFAULT,
            "work_gated": True,
        },
    },
    {
        "name": "check-for-index-attempt-cleanup",
        "task": EvolvXSICeleryTask.CHECK_FOR_INDEX_ATTEMPT_CLEANUP,
        "schedule": timedelta(minutes=30),
        "options": {
            "priority": EvolvXSICeleryPriority.MEDIUM,
            "expires": BEAT_EXPIRES_DEFAULT,
            # Run on gated tenants too — they may still have stale index attempts.
            "skip_gated": False,
            "work_gated": True,
        },
    },
    {
        "name": "check-for-connector-deletion",
        "task": EvolvXSICeleryTask.CHECK_FOR_CONNECTOR_DELETION,
        "schedule": timedelta(seconds=20),
        "options": {
            "priority": EvolvXSICeleryPriority.MEDIUM,
            "expires": BEAT_EXPIRES_DEFAULT,
            # Gated tenants may still have connectors awaiting deletion.
            "skip_gated": False,
            "work_gated": True,
        },
    },
    {
        "name": "check-for-vespa-sync",
        "task": EvolvXSICeleryTask.CHECK_FOR_VESPA_SYNC_TASK,
        "schedule": timedelta(seconds=20),
        "options": {
            "priority": EvolvXSICeleryPriority.MEDIUM,
            "expires": BEAT_EXPIRES_DEFAULT,
            "work_gated": True,
        },
    },
    {
        "name": "check-for-pruning",
        "task": EvolvXSICeleryTask.CHECK_FOR_PRUNING,
        "schedule": timedelta(seconds=20),
        "options": {
            "priority": EvolvXSICeleryPriority.MEDIUM,
            "expires": BEAT_EXPIRES_DEFAULT,
            "work_gated": True,
        },
    },
    {
        "name": "check-for-hierarchy-fetching",
        "task": EvolvXSICeleryTask.CHECK_FOR_HIERARCHY_FETCHING,
        "schedule": timedelta(hours=1),  # Check hourly, but only fetch once per day
        "options": {
            "priority": EvolvXSICeleryPriority.LOW,
            "expires": BEAT_EXPIRES_DEFAULT,
        },
    },
    # Craft scheduled tasks (per-tenant dispatcher + stuck-run sweeper).
    # Both are lightweight DB-only coordination tasks and run on the
    # primary queue. The dedicated `scheduled_tasks` worker is reserved
    # for the long-running executor (`run_scheduled_task`); routing the
    # dispatcher there would let a saturated executor pool stall dispatch.
    {
        "name": "dispatch-due-scheduled-tasks",
        "task": EvolvXSICeleryTask.SCHEDULED_TASKS_DISPATCH_DUE,
        # 30 s is the spec's contract: 60 s is too coarse for a minute-
        # cadence cron schedule; 15 s would over-load the FOR UPDATE
        # SKIP LOCKED path for tenants with no due tasks.
        "schedule": timedelta(seconds=30),
        "options": {
            "priority": EvolvXSICeleryPriority.MEDIUM,
            # Drop redundant ticks aggressively; if a tick is more than
            # ~2 schedules behind, the next one supersedes it.
            "expires": 60,
            "queue": EvolvXSICeleryQueues.PRIMARY,
        },
    },
    {
        "name": "cleanup-stuck-scheduled-runs",
        "task": EvolvXSICeleryTask.SCHEDULED_TASKS_CLEANUP_STUCK,
        "schedule": timedelta(hours=1),
        "options": {
            "priority": EvolvXSICeleryPriority.LOW,
            "expires": 60 * 60,
            "queue": EvolvXSICeleryQueues.PRIMARY,
        },
    },
    # Sandbox sweep: background-snapshot changed sessions, sleep idle sandboxes.
    {
        "name": "cleanup-idle-sandboxes",
        "task": EvolvXSICeleryTask.CLEANUP_IDLE_SANDBOXES,
        # Ticks are cheap (DB-only when nothing is stale); snapshot pacing is
        # gated inside the task at idle_timeout/4. With the cloud x8 multiplier
        # the effective interval is SANDBOX_IDLE_CLEANUP_INTERVAL_SECONDS * 8;
        # keep that product under ~15 min to stay within the data-loss bound.
        "schedule": timedelta(seconds=SANDBOX_IDLE_CLEANUP_INTERVAL_SECONDS),
        "options": {
            "priority": EvolvXSICeleryPriority.LOW,
            "expires": BEAT_EXPIRES_DEFAULT,
            "queue": EvolvXSICeleryQueues.SANDBOX,
            "work_gated": True,
        },
    },
]

# These tasks live in the Enterprise Edition code, so only a build that ships it
# can run them.
if is_ee_available():
    beat_task_templates.extend(
        [
            {
                "name": "check-for-doc-permissions-sync",
                "task": EvolvXSICeleryTask.CHECK_FOR_DOC_PERMISSIONS_SYNC,
                "schedule": timedelta(seconds=30),
                "options": {
                    "priority": EvolvXSICeleryPriority.MEDIUM,
                    "expires": BEAT_EXPIRES_DEFAULT,
                    "work_gated": True,
                },
            },
            {
                "name": "check-for-external-group-sync",
                "task": EvolvXSICeleryTask.CHECK_FOR_EXTERNAL_GROUP_SYNC,
                "schedule": timedelta(seconds=20),
                "options": {
                    "priority": EvolvXSICeleryPriority.MEDIUM,
                    "expires": BEAT_EXPIRES_DEFAULT,
                    "work_gated": True,
                },
            },
        ]
    )

# Add the Auto LLM update task if the config URL is set (has a default)
if AUTO_LLM_CONFIG_URL:
    beat_task_templates.append(
        {
            "name": "check-for-auto-llm-update",
            "task": EvolvXSICeleryTask.CHECK_FOR_AUTO_LLM_UPDATE,
            "schedule": timedelta(seconds=AUTO_LLM_UPDATE_INTERVAL_SECONDS),
            "options": {
                "priority": EvolvXSICeleryPriority.LOW,
                "expires": BEAT_EXPIRES_DEFAULT,
            },
        }
    )

# Add scheduled eval task if datasets are configured
if SCHEDULED_EVAL_DATASET_NAMES:
    beat_task_templates.append(
        {
            "name": "scheduled-eval-pipeline",
            "task": EvolvXSICeleryTask.SCHEDULED_EVAL_TASK,
            # run every Sunday at midnight UTC
            "schedule": crontab(
                hour=0,
                minute=0,
                day_of_week=0,
            ),
            "options": {
                "priority": EvolvXSICeleryPriority.LOW,
                "expires": BEAT_EXPIRES_DEFAULT,
            },
        }
    )

if not DISABLE_TELEMETRY:
    beat_task_templates.append(
        {
            "name": "collect-fleet-telemetry",
            "task": EvolvXSICeleryTask.COLLECT_FLEET_TELEMETRY,
            "schedule": timedelta(seconds=COLLECTION_INTERVAL_SECONDS),
            "options": {
                "priority": EvolvXSICeleryPriority.LOW,
                "expires": COLLECTION_INTERVAL_SECONDS,
                "queue": EvolvXSICeleryQueues.MONITORING,
            },
        }
    )

beat_task_templates.append(
    {
        "name": "backfill-cc-pair-ids",
        "task": EvolvXSICeleryTask.BACKFILL_CC_PAIR_IDS_TASK,
        "schedule": timedelta(minutes=5),
        "options": {
            "priority": EvolvXSICeleryPriority.LOW,
            "expires": BEAT_EXPIRES_DEFAULT,
            "queue": EvolvXSICeleryQueues.INDEX_RECLAIM,
        },
    }
)

# Gated here as well as in the task body, which would still cost one message
# per tenant every 5 minutes.
if TABULAR_RECHUNK_ENABLED:
    beat_task_templates.append(
        {
            "name": "tabular-rechunk",
            "task": EvolvXSICeleryTask.TABULAR_RECHUNK_TASK,
            "schedule": timedelta(minutes=5),
            "options": {
                # Level with a first-time index. The pool has no preemption, so
                # a lower tier is starved while a crawl keeps the queue busy.
                "priority": EvolvXSICeleryPriority.HIGH,
                "expires": TABULAR_RECHUNK_EXPIRES,
                "queue": EvolvXSICeleryQueues.DOCPROCESSING,
            },
        }
    )
# Beat task names that require a vector DB. Filtered out when DISABLE_VECTOR_DB.
_VECTOR_DB_BEAT_TASK_NAMES: set[str] = {
    "tabular-rechunk",
    "check-for-indexing",
    "check-for-port",
    "check-for-old-index-reclaim",
    "check-for-connector-deletion",
    "check-for-vespa-sync",
    "check-for-pruning",
    "check-for-hierarchy-fetching",
    "check-for-checkpoint-cleanup",
    "check-for-index-attempt-cleanup",
    "check-for-doc-permissions-sync",
    "check-for-external-group-sync",
    "backfill-cc-pair-ids",
}

if DISABLE_VECTOR_DB:
    beat_task_templates = [
        t for t in beat_task_templates if t["name"] not in _VECTOR_DB_BEAT_TASK_NAMES
    ]


def make_cloud_generator_task(task: dict[str, Any]) -> dict[str, Any]:
    cloud_task: dict[str, Any] = {}

    # constant options for cloud beat task generators
    task_schedule: timedelta = task["schedule"]
    cloud_task["schedule"] = task_schedule
    cloud_task["options"] = {}
    cloud_task["options"]["priority"] = EvolvXSICeleryPriority.HIGHEST
    cloud_task["options"]["expires"] = BEAT_EXPIRES_DEFAULT

    # settings dependent on the original task
    cloud_task["name"] = f"{EVOLVXSI_CLOUD_CELERY_TASK_PREFIX}_{task['name']}"
    cloud_task["task"] = EvolvXSICeleryTask.CLOUD_BEAT_TASK_GENERATOR
    cloud_task["kwargs"] = {}
    cloud_task["kwargs"]["task_name"] = task["task"]

    optional_fields = ["queue", "priority", "expires", "skip_gated", "work_gated"]
    for field in optional_fields:
        if field in task["options"]:
            cloud_task["kwargs"][field] = task["options"][field]

    return cloud_task


# tasks that only run in the cloud and are system wide
# the name attribute must start with EVOLVXSI_CLOUD_CELERY_TASK_PREFIX = "cloud" to be seen
# by the DynamicTenantScheduler as system wide task and not a per tenant task
beat_cloud_tasks: list[dict] = [
    {
        "name": f"{EVOLVXSI_CLOUD_CELERY_TASK_PREFIX}_cleanup-oauth-provider-clients",
        "task": EvolvXSICeleryTask.CLEANUP_OAUTH_PROVIDER_CLIENTS,
        "schedule": timedelta(days=1),
        "options": {
            "queue": EvolvXSICeleryQueues.PRIMARY,
            "priority": EvolvXSICeleryPriority.LOW,
            "expires": BEAT_EXPIRES_DEFAULT,
        },
    },
    # cloud specific tasks
    {
        "name": f"{EVOLVXSI_CLOUD_CELERY_TASK_PREFIX}_monitor-alembic",
        "task": EvolvXSICeleryTask.CLOUD_MONITOR_ALEMBIC,
        "schedule": timedelta(hours=1),
        "options": {
            "queue": EvolvXSICeleryQueues.MONITORING,
            "priority": EvolvXSICeleryPriority.HIGH,
            "expires": BEAT_EXPIRES_DEFAULT,
        },
    },
    {
        "name": f"{EVOLVXSI_CLOUD_CELERY_TASK_PREFIX}_monitor-celery-queues",
        "task": EvolvXSICeleryTask.CLOUD_MONITOR_CELERY_QUEUES,
        "schedule": timedelta(seconds=30),
        "options": {
            "queue": EvolvXSICeleryQueues.MONITORING,
            "priority": EvolvXSICeleryPriority.HIGH,
            "expires": BEAT_EXPIRES_DEFAULT,
        },
    },
    {
        "name": f"{EVOLVXSI_CLOUD_CELERY_TASK_PREFIX}_check-available-tenants",
        "task": EvolvXSICeleryTask.CLOUD_CHECK_AVAILABLE_TENANTS,
        "schedule": timedelta(minutes=2),
        "options": {
            "queue": EvolvXSICeleryQueues.MONITORING,
            "priority": EvolvXSICeleryPriority.HIGH,
            "expires": BEAT_EXPIRES_DEFAULT,
        },
    },
    {
        "name": f"{EVOLVXSI_CLOUD_CELERY_TASK_PREFIX}_monitor-celery-pidbox",
        "task": EvolvXSICeleryTask.CLOUD_MONITOR_CELERY_PIDBOX,
        "schedule": timedelta(hours=4),
        "options": {
            "queue": EvolvXSICeleryQueues.MONITORING,
            "priority": EvolvXSICeleryPriority.HIGH,
            "expires": BEAT_EXPIRES_DEFAULT,
        },
    },
]

# tasks that only run self hosted
tasks_to_schedule: list[dict] = []
if not MULTI_TENANT:
    tasks_to_schedule.extend(
        [
            {
                "name": "cleanup-oauth-provider-clients",
                "task": EvolvXSICeleryTask.CLEANUP_OAUTH_PROVIDER_CLIENTS,
                "schedule": timedelta(days=1),
                "options": {
                    "queue": EvolvXSICeleryQueues.PRIMARY,
                    "priority": EvolvXSICeleryPriority.LOW,
                    "expires": BEAT_EXPIRES_DEFAULT,
                },
            },
            {
                "name": "monitor-celery-queues",
                "task": EvolvXSICeleryTask.MONITOR_CELERY_QUEUES,
                "schedule": timedelta(seconds=10),
                "options": {
                    "priority": EvolvXSICeleryPriority.MEDIUM,
                    "expires": BEAT_EXPIRES_DEFAULT,
                    "queue": EvolvXSICeleryQueues.MONITORING,
                },
            },
            {
                "name": "monitor-process-memory",
                "task": EvolvXSICeleryTask.MONITOR_PROCESS_MEMORY,
                "schedule": timedelta(minutes=5),
                "options": {
                    "priority": EvolvXSICeleryPriority.LOW,
                    "expires": BEAT_EXPIRES_DEFAULT,
                    "queue": EvolvXSICeleryQueues.MONITORING,
                },
            },
            {
                "name": "celery-beat-heartbeat",
                "task": EvolvXSICeleryTask.CELERY_BEAT_HEARTBEAT,
                "schedule": timedelta(minutes=1),
                "options": {
                    "priority": EvolvXSICeleryPriority.HIGHEST,
                    "expires": BEAT_EXPIRES_DEFAULT,
                    "queue": EvolvXSICeleryQueues.PRIMARY,
                },
            },
        ]
    )

    # `skip_gated` and `work_gated` are cloud-only hints consumed by
    # `cloud_beat_task_generator`. Strip them before extending the self-hosted
    # schedule so they don't leak into apply_async as unrecognised options on
    # every fired task message.
    for _template in beat_task_templates:
        _self_hosted_template = copy.deepcopy(_template)
        _self_hosted_template["options"].pop("skip_gated", None)
        _self_hosted_template["options"].pop("work_gated", None)
        tasks_to_schedule.append(_self_hosted_template)


if not DISABLE_VECTOR_DB:
    # Cluster-wide in cloud; never fan this probe out to each tenant.
    _resource_health_task: dict[str, Any] = {
        "name": f"{EVOLVXSI_CLOUD_CELERY_TASK_PREFIX}_monitor-opensearch-resources"
        if MULTI_TENANT
        else "monitor-opensearch-resources",
        "task": EvolvXSICeleryTask.MONITOR_OPENSEARCH_RESOURCES,
        "schedule": timedelta(seconds=RESOURCE_CHECK_INTERVAL_SECONDS),
        "options": {
            "queue": EvolvXSICeleryQueues.MONITORING,
            "priority": EvolvXSICeleryPriority.LOW,
            "expires": RESOURCE_CHECK_INTERVAL_SECONDS,
        },
    }
    if MULTI_TENANT:
        beat_cloud_tasks.append(_resource_health_task)
    else:
        tasks_to_schedule.append(_resource_health_task)


def generate_cloud_tasks(
    beat_tasks: list[dict], beat_templates: list[dict], beat_multiplier: float
) -> list[dict[str, Any]]:
    """
    beat_tasks: system wide tasks that can be sent as is
    beat_templates: task templates that will be transformed into per tenant tasks via
    the cloud_beat_task_generator
    beat_multiplier: a multiplier that can be applied on top of the task schedule
    to speed up or slow down the task generation rate. useful in production.

    Returns a list of cloud tasks, which consists of incoming tasks + tasks generated
    from incoming templates.
    """

    if beat_multiplier <= 0:
        raise ValueError("beat_multiplier must be positive!")

    cloud_tasks: list[dict] = []

    # generate our tenant aware cloud tasks from the templates
    for beat_template in beat_templates:
        cloud_task = make_cloud_generator_task(beat_template)
        cloud_tasks.append(cloud_task)

    # factor in the cloud multiplier for the above
    for cloud_task in cloud_tasks:
        cloud_task["schedule"] = cloud_task["schedule"] * beat_multiplier

    # add the fixed cloud/system beat tasks. No multiplier for these.
    cloud_tasks.extend(copy.deepcopy(beat_tasks))
    return cloud_tasks


def get_cloud_tasks_to_schedule(beat_multiplier: float) -> list[dict[str, Any]]:
    return generate_cloud_tasks(beat_cloud_tasks, beat_task_templates, beat_multiplier)


def get_tasks_to_schedule() -> list[dict[str, Any]]:
    return tasks_to_schedule
