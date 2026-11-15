"""Old setting names keep working after the product rename (decision 0007).

Settings were renamed from NORTPOLE_* to NORTPOLE_*. Deployments that still set an old name get it copied to the new
name at import time, unless the new name is set too (the new name wins). Remove once deployments have moved.
"""

import os

OLD_PREFIX = "NORTPOLE_"
NEW_PREFIX = "NORTPOLE_"
_applied: list[str] = []


def apply() -> list[str]:
    """Copy each NORTPOLE_X (and NEXT_PUBLIC_NORTPOLE_X) to its NORTPOLE_ name when that is unset; return what moved."""
    moved = []
    for key, value in list(os.environ.items()):
        idx = key.find(OLD_PREFIX)
        if idx == -1 or (idx > 0 and key[idx - 1] != "_"):
            continue
        new_key = key[:idx] + NEW_PREFIX + key[idx + len(OLD_PREFIX):]
        if new_key not in os.environ:
            os.environ[new_key] = value
            moved.append(key)
    _applied.extend(moved)
    return moved
