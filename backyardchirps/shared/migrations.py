from django.db import connections
from django.db.migrations.loader import MigrationLoader


def migrations_ahead_of_this_release() -> list[str]:
    """
    Migrations the database has applied that this release does not ship.

    Empty on a station whose code and database agree, which is the ordinary case. Not
    empty after an update has been swapped back without restoring the database, and that
    is the state this exists to name: old code against a newer schema, which Django will
    not complain about on its own until something reads a column that is no longer there.

    Read by the rollback script through the show_migrations_ahead command, with the *older*
    release's interpreter, since what matters is what that release knows about.
    """
    loader = MigrationLoader(connections["default"])
    ahead = set(loader.applied_migrations) - set(loader.disk_migrations)
    return sorted(f"{app_label}.{name}" for app_label, name in ahead)
