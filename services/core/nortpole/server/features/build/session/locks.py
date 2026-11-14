from collections.abc import Generator
from contextlib import contextmanager
from uuid import UUID

from redis.lock import Lock as RedisLock

from nortpole.configs.constants import NortPoleRedisLocks
from nortpole.redis.redis_pool import get_redis_client
from nortpole.redis.tenant_redis_client import TenantRedisClient
from nortpole.server.features.build.timeouts import SESSION_FLOW_LOCK_LEASE_SECONDS
from shared_configs.contextvars import get_current_tenant_id

# How long a creator blocks on another create/reap of the same user's sandbox.
SESSION_FLOW_LOCK_WAIT_SECONDS = 60


class SessionCreationLockAcquisitionError(RuntimeError):
    """Raised when session creation cannot acquire its per-user lock."""


def get_session_creation_lock(
    redis_client: TenantRedisClient,
    user_id: UUID,
) -> RedisLock:
    return redis_client.lock(
        f"{NortPoleRedisLocks.SESSION_CREATE_LOCK_PREFIX}:{user_id}",
        timeout=SESSION_FLOW_LOCK_LEASE_SECONDS,
    )


@contextmanager
def session_creation_lock(user_id: UUID) -> Generator[RedisLock, None, None]:
    """Serialize session creation for one user in the current tenant."""
    redis_client = get_redis_client(tenant_id=get_current_tenant_id())
    lock = get_session_creation_lock(redis_client, user_id)
    if not lock.acquire(
        blocking=True,
        blocking_timeout=SESSION_FLOW_LOCK_WAIT_SECONDS,
    ):
        raise SessionCreationLockAcquisitionError(
            f"Timed out waiting to create a session for user {user_id}"
        )

    try:
        yield lock
    finally:
        if lock.owned():
            lock.release()
