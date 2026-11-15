import os

from shared_configs.env_compat import apply as _apply_env_compat

_apply_env_compat()  # old NORTPOLE_* setting names still work

__version__ = os.environ.get("NORTPOLE_VERSION", "") or "Development"
