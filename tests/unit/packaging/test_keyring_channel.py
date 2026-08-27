"""
The keyring package's two scripts, which are what let a machine choose its suite.

They are run here rather than read, because what matters is what they do to two files, and
a shell script that reads correctly and writes the wrong line is exactly the bug this has
to catch. Both take their paths from the environment for that reason, the same way
install.sh takes its preflight paths.

The failure that would hurt: a station left on a suite it did not ask for, or with no
source file at all, which is a station that stops receiving updates and says nothing.
"""

import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
APT_DIR = REPO_ROOT / "packaging" / "apt"
POSTINST = APT_DIR / "postinst"
POSTRM = APT_DIR / "postrm"
MANIFEST = REPO_ROOT / "packaging" / "nfpm" / "backyardchirps-archive-keyring.yaml"

SHIPPED_SOURCE = """\
# A comment the package ships.
Types: deb
URIs: https://apt.example.com
Suites: stable
Components: main
Architectures: arm64
Signed-By: /usr/share/keyrings/backyardchirps-archive-keyring.gpg
"""


@pytest.fixture
def station(tmp_path: Path) -> Path:
    """
    A machine mid-install: dpkg has just restored the source file, and the postinst has not
    run yet.
    """
    source = tmp_path / "backyardchirps.sources"
    source.write_text(SHIPPED_SOURCE, encoding="utf-8")
    return tmp_path


def configure(station: Path, script: Path = POSTINST, argument: str = "configure") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(script), argument],
        env={
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "CHANNEL_FILE": str(station / "channel"),
            "SOURCE_FILE": str(station / "backyardchirps.sources"),
        },
        capture_output=True,
        text=True,
        check=False,
    )


def suite_in(station: Path) -> str:
    for line in (station / "backyardchirps.sources").read_text(encoding="utf-8").splitlines():
        if line.startswith("Suites: "):
            return line.removeprefix("Suites: ")
    raise AssertionError("the source file has no Suites line")


def test_a_machine_that_has_never_chosen_gets_stable(station: Path) -> None:
    """
    The default has to survive a station that knows nothing about any of this, which is
    every station an owner installs.
    """
    result = configure(station)

    assert result.returncode == 0, result.stderr
    assert (station / "channel").read_text(encoding="utf-8").strip() == "stable"
    assert suite_in(station) == "stable"


def test_the_chosen_suite_replaces_the_one_the_package_shipped(station: Path) -> None:
    (station / "channel").write_text("unstable\n", encoding="utf-8")

    result = configure(station)

    assert result.returncode == 0, result.stderr
    assert suite_in(station) == "unstable"


def test_the_choice_survives_the_upgrade_that_restored_the_file(station: Path) -> None:
    """
    The whole point. dpkg puts the shipped file back on every upgrade, so without this the
    address could never change under a station and a suite could never stay chosen.
    """
    (station / "channel").write_text("unstable\n", encoding="utf-8")
    configure(station)

    (station / "backyardchirps.sources").write_text(SHIPPED_SOURCE, encoding="utf-8")
    configure(station)

    assert suite_in(station) == "unstable"


def test_nothing_else_in_the_source_file_is_touched(station: Path) -> None:
    """
    The address and the key path are the package's to change. A rewrite that lost either
    would leave a station reading nothing.
    """
    (station / "channel").write_text("unstable\n", encoding="utf-8")

    configure(station)

    written = (station / "backyardchirps.sources").read_text(encoding="utf-8")
    assert written == SHIPPED_SOURCE.replace("Suites: stable", "Suites: unstable")


def test_a_suite_that_does_not_exist_leaves_the_station_on_stable(station: Path) -> None:
    """
    A typo must not point a station at a suite the archive does not publish, which reads as
    "the repository is broken" on a machine that is fine.
    """
    (station / "channel").write_text("untsable\n", encoding="utf-8")

    result = configure(station)

    assert result.returncode == 0, result.stderr
    assert suite_in(station) == "stable"
    assert "untsable" in result.stdout


def test_an_empty_channel_file_leaves_the_station_on_stable(station: Path) -> None:
    (station / "channel").write_text("\n\n", encoding="utf-8")

    result = configure(station)

    assert result.returncode == 0, result.stderr
    assert suite_in(station) == "stable"


def test_a_comment_in_the_channel_file_is_not_the_suite(station: Path) -> None:
    (station / "channel").write_text("# set by install.sh\nunstable\n", encoding="utf-8")

    configure(station)

    assert suite_in(station) == "unstable"


def test_a_source_file_with_no_suites_line_is_left_alone(station: Path) -> None:
    """
    Not a file this understands, and guessing would be worse than leaving a station reading
    what it already reads.
    """
    (station / "backyardchirps.sources").write_text("Types: deb\nURIs: https://apt.example.com\n", encoding="utf-8")
    (station / "channel").write_text("unstable\n", encoding="utf-8")

    result = configure(station)

    assert result.returncode == 0, result.stderr
    assert "Suites" not in (station / "backyardchirps.sources").read_text(encoding="utf-8")


def test_nothing_happens_when_dpkg_is_not_configuring(station: Path) -> None:
    (station / "channel").write_text("unstable\n", encoding="utf-8")

    configure(station, argument="abort-upgrade")

    assert suite_in(station) == "stable"


def test_removing_the_package_keeps_the_choice(station: Path) -> None:
    """
    A reinstall should come back on the suite the machine was following, not quietly on
    stable.
    """
    (station / "channel").write_text("unstable\n", encoding="utf-8")

    configure(station, script=POSTRM, argument="remove")

    assert (station / "channel").is_file()


def test_purging_the_package_takes_the_choice_with_it(station: Path) -> None:
    (station / "channel").write_text("unstable\n", encoding="utf-8")

    result = configure(station, script=POSTRM, argument="purge")

    assert result.returncode == 0, result.stderr
    assert not (station / "channel").exists()


def test_the_channel_file_is_not_shipped_by_the_package() -> None:
    """
    Shipping it would make it dpkg's, and dpkg meeting a copy install.sh wrote before the
    package arrived is a prompt with nobody there to answer it.
    """
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))

    shipped = [entry["dst"] for entry in manifest["contents"]]
    assert "/etc/backyardchirps/channel" not in shipped
    assert manifest["scripts"]["postinstall"].endswith("/postinst")
    assert manifest["scripts"]["postremove"].endswith("/postrm")
