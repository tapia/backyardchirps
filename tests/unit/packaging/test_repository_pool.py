"""
The two decisions tools/build_repository.py makes on its own: which suite a version belongs
in, and which pooled files survive a prune.

Both are pure, so they run anywhere. What they cannot check is that apt-ftparchive and gpg
were driven correctly, which is what the publish job's own verification does against the
live site.

The bug class here is a prune that deletes something a suite still offers. The published
Packages index would name a file that is not there, and every station reading that suite
would fail its next update at the download rather than at the index.
"""

import shutil
import subprocess

import pytest

from tools.build_repository import STABLE
from tools.build_repository import UNSTABLE
from tools.build_repository import DebianVersion
from tools.build_repository import keyring_files_that_changed
from tools.build_repository import plan_additions
from tools.build_repository import plan_pool
from tools.build_repository import stanzas_for
from tools.build_repository import suites_for

ARCHITECTURE = "arm64"


def pooled(*packages: tuple[str, str]) -> dict[str, tuple[str, str]]:
    """
    Name each (package, version) the way a pooled file is named, which is the only place a
    file in the pool says what it is.
    """
    return {f"{name}_{version}_{ARCHITECTURE}.deb": (name, version) for name, version in packages}


def test_a_release_is_offered_to_both_suites() -> None:
    assert suites_for("0.3.0") == (STABLE, UNSTABLE)


def test_a_build_off_main_is_offered_to_unstable_alone() -> None:
    """
    The local version is the whole difference between a push to main and a cut release, and
    this is where that difference stops a contributor's commit from reaching a station.
    """
    assert suites_for("0.3.0+main.abc1234") == (UNSTABLE,)


def test_the_pool_keeps_one_virtualenv_per_suite() -> None:
    kept, pruned = plan_pool(pooled(("backyardchirps-deps", "1.40"), ("backyardchirps-deps", "1.41")))

    assert kept == ["backyardchirps-deps_1.41_arm64.deb"]
    assert pruned == ["backyardchirps-deps_1.40_arm64.deb"]


def test_the_pool_keeps_several_app_versions() -> None:
    kept, pruned = plan_pool(pooled(*[("backyardchirps", f"0.{minor}.0") for minor in range(1, 8)]))

    assert len(kept) == 5
    assert "backyardchirps_0.7.0_arm64.deb" in kept
    assert pruned == ["backyardchirps_0.1.0_arm64.deb", "backyardchirps_0.2.0_arm64.deb"]


def test_a_release_survives_even_when_newer_main_builds_crowd_it_out() -> None:
    """
    The case that would break a station. unstable gets a build per commit, so five of them
    outnumber the release they came after. Pruning per suite is what keeps the release: it
    is the newest thing stable offers, whatever unstable has been doing.
    """
    main_builds = [("backyardchirps", f"0.3.0+main.{marker}") for marker in ("a1", "b2", "c3", "d4", "e5", "f6")]
    kept, _ = plan_pool(pooled(("backyardchirps", "0.3.0"), *main_builds))

    assert "backyardchirps_0.3.0_arm64.deb" in kept


def test_every_suite_a_kept_file_serves_still_has_something_to_offer() -> None:
    """
    The property the whole prune exists to preserve: no suite is left with no version of a
    package it had one of.
    """
    everything = pooled(
        ("backyardchirps", "0.3.0"),
        ("backyardchirps", "0.3.0+main.a1"),
        ("backyardchirps-deps", "1.40"),
        ("backyardchirps-deps", "1.41"),
        ("backyardchirps-species-data", "1.20260101"),
        ("backyardchirps-archive-keyring", "1.3"),
    )
    kept, _ = plan_pool(everything)

    for suite in (STABLE, UNSTABLE):
        offered = {everything[name][0] for name in kept if suite in suites_for(everything[name][1])}
        wanted = {package for package, version in everything.values() if suite in suites_for(version)}
        assert offered == wanted, f"{suite} lost a package entirely"


def test_stanzas_are_split_by_suite_rather_than_indexed_twice() -> None:
    """
    Both suites share one pool, so apt-ftparchive walks it once and the result is cut up
    here. A stanza reaches a suite only when its version belongs there.
    """
    packages_text = (
        "Package: backyardchirps\nVersion: 0.3.0\n"
        "Filename: pool/main/b/backyardchirps/backyardchirps_0.3.0_arm64.deb\n"
        "\n"
        "Package: backyardchirps\nVersion: 0.3.0+main.a1\n"
        "Filename: pool/main/b/backyardchirps/backyardchirps_0.3.0+main.a1_arm64.deb\n"
    )
    entries = pooled(("backyardchirps", "0.3.0"), ("backyardchirps", "0.3.0+main.a1"))

    assert "0.3.0+main.a1" not in stanzas_for(packages_text, entries, STABLE)
    assert "0.3.0+main.a1" in stanzas_for(packages_text, entries, UNSTABLE)
    assert "Version: 0.3.0\n" in stanzas_for(packages_text, entries, UNSTABLE)


ORDERED_PAIRS = [
    ("0.2.0", "0.3.0"),
    ("0.9.0", "0.10.0"),
    ("0.2.0", "0.2.0+main.abc1234"),
    ("0.2.0+main.abc1234", "0.2.1"),
    ("0.2.0+main.abc1234", "0.2.0+main.bcd2345"),
    ("1.9", "1.10"),
    ("1.20260101", "1.20260102"),
    ("1.0~rc1", "1.0"),
    ("1.0", "1.0-2"),
]


@pytest.mark.parametrize(("older", "newer"), ORDERED_PAIRS)
def test_versions_sort_the_way_dpkg_sorts_them(older: str, newer: str) -> None:
    assert DebianVersion(older) < DebianVersion(newer)


@pytest.mark.skipif(shutil.which("dpkg") is None, reason="dpkg is not installed on this machine")
@pytest.mark.parametrize(("older", "newer"), ORDERED_PAIRS)
def test_dpkg_agrees(older: str, newer: str) -> None:
    """
    dpkg is the authority. This is what stops the ordering written out in Python from
    drifting away from it: a developer laptop skips, and CI runs on Debian and does not.
    """
    compared = subprocess.run(["dpkg", "--compare-versions", older, "lt", newer], check=False, capture_output=True)
    assert compared.returncode == 0


def test_one_version_survives_even_when_the_pool_store_renamed_it() -> None:
    """
    The pool is kept as the assets of a GitHub release, and that store turns a + into a dot.
    So the same build can come back under a name it was never uploaded with, and be
    uploaded again beside itself. Both files say the same thing about themselves, and only
    one of them may reach an index: two identical stanzas is a repository apt has to
    arbitrate, for no reason.
    """
    same_build = ("backyardchirps", "0.3.0+main.abc1234")
    kept, pruned = plan_pool(
        {
            "backyardchirps_0.3.0+main.abc1234_arm64.deb": same_build,
            "backyardchirps_0.3.0.main.abc1234_arm64.deb": same_build,
        }
    )

    assert len(kept) == 1
    assert len(pruned) == 1


def test_a_rebuild_of_a_published_version_is_not_added_again() -> None:
    """
    The case that broke the first working publish. Most pushes rebuild a package whose
    version has not moved: the venv package is versioned by commit count over uv.lock and
    the keyring package by commit count over packaging/apt, and an ordinary commit changes
    neither. Those rebuilds must leave the published file alone.
    """
    published = {("backyardchirps-archive-keyring", "1.1"), ("backyardchirps-deps", "1.41")}

    assert plan_additions(published, [("backyardchirps-archive-keyring", "1.1")]) == set()


def test_a_version_that_moved_is_added() -> None:
    published = {("backyardchirps-deps", "1.41")}

    assert plan_additions(published, [("backyardchirps-deps", "1.42")]) == {("backyardchirps-deps", "1.42")}


def test_an_empty_pool_takes_everything() -> None:
    incoming = [("backyardchirps", "0.3.0"), ("backyardchirps-deps", "1.41")]

    assert plan_additions(set(), incoming) == set(incoming)


# ---------------------------------------------------------------------------
# The keyring package, whose version does not track its own content
# ---------------------------------------------------------------------------
# Every other version scheme here moves when its input moves. This one counts commits over
# packaging/apt while the key comes from a secret and the host from a repository variable,
# so it is the only package that can change while its version does not. Publishing that
# silently would leave every station reading a dead host or trusting only a retired key.

KEY = "./usr/share/keyrings/backyardchirps-archive-keyring.gpg"
SOURCE = "./etc/apt/sources.list.d/backyardchirps.sources"


def test_a_rebuilt_keyring_with_the_same_content_is_not_a_change() -> None:
    """
    The ordinary case, and the one that must stay quiet: nearly every publish rebuilds this
    package without changing either file.
    """
    same = {KEY: "aaa", SOURCE: "bbb"}
    assert keyring_files_that_changed(same, dict(same)) == []


def test_a_changed_host_is_caught() -> None:
    assert keyring_files_that_changed({KEY: "aaa", SOURCE: "new"}, {KEY: "aaa", SOURCE: "old"}) == [SOURCE]


def test_a_rotated_key_is_caught() -> None:
    """
    The sharper of the two. A rotation changes nothing in git at all, so the version cannot
    move on its own, and the first publish signed with the new key fails verification on
    every station at once.
    """
    assert keyring_files_that_changed({KEY: "new", SOURCE: "bbb"}, {KEY: "old", SOURCE: "bbb"}) == [KEY]


def test_both_changing_together_reports_both() -> None:
    """
    A change of host and a rotation travel together, which is the case the docstring on
    _keyring_version calls usual.
    """
    changed = keyring_files_that_changed({KEY: "new", SOURCE: "new"}, {KEY: "old", SOURCE: "old"})
    assert changed == sorted([KEY, SOURCE])


def test_what_a_run_just_built_survives_its_own_prune() -> None:
    """
    The failure this exists for, seen on a real publish.

    A build off main is told apart from the ones before it by its local version, and that
    used to be a bare commit sha, which does not order. So a package could be built, put in
    the pool, and thrown straight back out for being the lowest version there, leaving the
    publish trying to upload a file it had just deleted and the deploy waiting for a version
    the repository would never offer.
    """
    just_built = "backyardchirps_0.2.0+main.4daccd0_arm64.deb"
    everything = pooled(
        ("backyardchirps", "0.2.0+main.4daccd0"),
        *[("backyardchirps", f"0.2.0+main.f{digit}00000") for digit in range(6)],
    )

    kept, pruned = plan_pool(everything, just_built=[just_built])

    assert just_built in kept
    assert just_built not in pruned


def test_the_extra_copy_is_pruned_by_the_run_after_it() -> None:
    """
    Keeping the new build is for the run that made it and no longer. Otherwise every publish
    would add one to the count and the pool would grow for good, which is the thing the 1 GB
    limit on the published site does not allow.
    """
    everything = pooled(
        ("backyardchirps", "0.2.0+main.4daccd0"),
        *[("backyardchirps", f"0.2.0+main.f{digit}00000") for digit in range(6)],
    )

    kept, pruned = plan_pool(everything)

    assert "backyardchirps_0.2.0+main.4daccd0_arm64.deb" in pruned
    assert len(kept) == 5


def test_a_commit_count_orders_two_builds_of_one_release_and_a_sha_does_not() -> None:
    """
    Why the version a push publishes carries both. The count is the half that means "and then
    this one"; the sha is the half a person can look up.
    """
    assert DebianVersion("0.2.0+main.1200.f25d563") < DebianVersion("0.2.0+main.1201.4daccd0")
    assert not DebianVersion("0.2.0+main.f25d563") < DebianVersion("0.2.0+main.4daccd0")
