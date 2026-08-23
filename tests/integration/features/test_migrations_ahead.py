"""
Which migrations the database has that this release does not ship.

Small, and load-bearing out of proportion to its size: this is what decides whether a
rollback restores the pre-update database, and restoring it drops every detection recorded
since the update. Answering "nothing is ahead" when something is leaves old code reading a
schema it has never seen; answering the other way round throws data away for no reason.
"""

import pytest
from django.db import connection

from backyardchirps.shared.migrations import migrations_ahead_of_this_release

pytestmark = pytest.mark.django_db

# A name no release carries, which is what a migration from a newer release looks like from
# an older one's side.
FROM_A_NEWER_RELEASE = "0099_only_in_the_newer_release"


def record_applied(app: str, name: str) -> None:
    """
    Write straight into django_migrations, which is the one table Django's own machinery
    owns and no model of ours covers.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into django_migrations (app, name, applied) values (%s, %s, datetime('now'))",
            [app, name],
        )


def test_a_station_whose_code_and_database_agree_has_nothing_ahead() -> None:
    """
    The ordinary case, and the one that has to stay quiet: an update that changed no schema
    must not make a rollback restore anything.
    """
    assert migrations_ahead_of_this_release() == []


def test_a_migration_the_release_does_not_ship_is_reported() -> None:
    record_applied("birds_recorder", FROM_A_NEWER_RELEASE)

    assert migrations_ahead_of_this_release() == [f"birds_recorder.{FROM_A_NEWER_RELEASE}"]


def test_every_migration_ahead_is_reported_not_just_the_first() -> None:
    """
    An update can carry several. A rollback needs the whole answer, since one of the others
    could be the destructive one.
    """
    record_applied("birds_recorder", FROM_A_NEWER_RELEASE)
    record_applied("birds_recorder", "0100_and_another")

    # Sorted, so 0099 comes before 0100.
    assert migrations_ahead_of_this_release() == [
        f"birds_recorder.{FROM_A_NEWER_RELEASE}",
        "birds_recorder.0100_and_another",
    ]


def test_a_migration_from_any_app_counts() -> None:
    """
    Django's own apps migrate too, and a station is as broken by an auth table it does not
    understand as by one of ours.
    """
    record_applied("auth", "0099_from_a_newer_django")

    assert migrations_ahead_of_this_release() == ["auth.0099_from_a_newer_django"]


def test_a_migration_the_release_ships_is_not_ahead() -> None:
    """
    The guard against the obvious wrong implementation, which is to report every applied
    migration rather than the difference.
    """
    ahead = migrations_ahead_of_this_release()

    assert not any(name.endswith("0001_initial") for name in ahead), ahead
