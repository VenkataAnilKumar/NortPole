#!/usr/bin/env python3
"""Make an existing user an administrator (recovery tool).

Run this on the server, with the same database settings as the app, when no
administrator can sign in, for example after the first account was created in the
wrong group. It uses the app's own group and permission functions, so cached
permissions are recomputed. Access to this command is access to the database.

    PYTHONPATH=. python scripts/grant_admin.py someone@example.com

It adds the user to the default Admin group, removes them from the default Basic
group, and recomputes their permissions. It never creates users.
"""
import sys

from nortpole.db.engine.sql_engine import SqlEngine, get_session_with_current_tenant
from nortpole.db.models import User, User__UserGroup, UserGroup
from nortpole.db.permissions import recompute_user_permissions__no_commit
from nortpole.db.users import DEFAULT_ADMIN_GROUP_NAME, DEFAULT_BASIC_GROUP_NAME


def grant_admin(email: str) -> str:
    with get_session_with_current_tenant() as db:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise SystemExit(f"No user with email {email!r}. Nothing changed.")

        def default_group(name: str) -> UserGroup:
            g = db.query(UserGroup).filter(UserGroup.name == name, UserGroup.is_default.is_(True)).first()
            if g is None:
                raise SystemExit(f"Default group {name!r} not found. Run the database migrations first.")
            return g

        admin = default_group(DEFAULT_ADMIN_GROUP_NAME)
        basic = default_group(DEFAULT_BASIC_GROUP_NAME)
        db.query(User__UserGroup).filter(
            User__UserGroup.user_id == user.id, User__UserGroup.user_group_id == basic.id
        ).delete()
        exists = (
            db.query(User__UserGroup)
            .filter(User__UserGroup.user_id == user.id, User__UserGroup.user_group_id == admin.id)
            .first()
        )
        if exists is None:
            db.add(User__UserGroup(user_id=user.id, user_group_id=admin.id))
            db.flush()
        recompute_user_permissions__no_commit(user.id, db)
        db.commit()
        return str(user.id)


def main() -> None:
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        raise SystemExit("usage: grant_admin.py <email>")
    SqlEngine.init_engine(pool_size=2, max_overflow=0)
    uid = grant_admin(sys.argv[1])
    print(f"{sys.argv[1]} ({uid}) is now an administrator.")


if __name__ == "__main__":
    main()
