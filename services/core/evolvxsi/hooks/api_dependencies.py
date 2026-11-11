from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from shared_configs.configs import MULTI_TENANT


def require_hook_enabled() -> None:
    """FastAPI dependency that gates all hook management endpoints.

    Hooks are only available in single-tenant / self-hosted EE deployments.

    Use as: Depends(require_hook_enabled)
    """
    if MULTI_TENANT:
        raise EvolvXSIError(
            EvolvXSIErrorCode.SINGLE_TENANT_ONLY,
            "Hooks are not available in multi-tenant deployments",
        )
