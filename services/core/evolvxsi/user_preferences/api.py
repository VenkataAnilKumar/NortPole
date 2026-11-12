from __future__ import annotations

from fastapi import APIRouter, Depends

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User
from evolvxsi.user_preferences.store import (
    UserPreferences,
    load_preferences,
    save_preferences,
)

router = APIRouter()


@router.get("/user-preferences")
def get_user_preferences(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
) -> UserPreferences:
    return load_preferences(str(user.id))


@router.put("/user-preferences")
def put_user_preferences(
    body: UserPreferences,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
) -> UserPreferences:
    """Each person can read and change only their own preferences."""
    return save_preferences(str(user.id), body)
