"""
Hold the nfpm configurations to what the build actually stages, and to each other.

These read the YAML rather than a built package, so they run in the fast suite and on any
machine. What a real build proves is different and complementary: nfpm fails when a src is
missing, so the CI build is what says the staging step and these files agree.

The bug class this is here for is two packages claiming the same path. dpkg refuses to
unpack that, and the failure lands on a station mid-upgrade rather than on a PR.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGING = REPO_ROOT / "packaging"
NFPM_DIR = PACKAGING / "nfpm"

# Every staging root tools/build_packages.py hands to nfpm. A src outside these is a file
# taken from somewhere the builder does not control.
STAGING_VARIABLES = ("${STAGING_APP}", "${STAGING_DEPS}", "${STAGING_DATA}", "${STAGING_KEYRING}")

# The only two files a station's owner may edit and keep across an upgrade. The sudoers
# policy is deliberately not among them: a privilege grant dpkg refuses to overwrite is a
# stale privilege grant.
EXPECTED_CONFIG_FILES = {
    "/etc/nginx/sites-available/backyardchirps",
    "/etc/default/backyardchirps",
}


def configurations() -> list[Path]:
    return sorted(NFPM_DIR.glob("*.yaml"))


def load(configuration: Path) -> dict[str, Any]:
    with configuration.open(encoding="utf-8") as handle:
        return dict(yaml.safe_load(handle))


@pytest.fixture(scope="module")
def packages() -> dict[str, dict[str, Any]]:
    return {configuration.stem: load(configuration) for configuration in configurations()}


def test_there_is_one_configuration_for_each_package(packages: dict[str, dict[str, Any]]) -> None:
    assert set(packages) == {
        "backyardchirps",
        "backyardchirps-deps",
        "backyardchirps-species-data",
        "backyardchirps-archive-keyring",
    }


def test_the_file_name_is_the_package_name(packages: dict[str, dict[str, Any]]) -> None:
    for stem, package in packages.items():
        assert package["name"] == stem


@pytest.mark.parametrize("field", ["arch", "platform", "maintainer", "license", "description"])
def test_every_package_carries_the_fields_a_debian_package_needs(
    packages: dict[str, dict[str, Any]], field: str
) -> None:
    for package in packages.values():
        assert package.get(field), f"{package['name']} has no {field}"


def test_versions_are_taken_literally(packages: dict[str, dict[str, Any]]) -> None:
    """
    Under nfpm's default semver schema, the +main.abc1234 half of a build off main is build
    metadata and is dropped, so two different builds would package as the same version.
    """
    for package in packages.values():
        assert package.get("version_schema") == "none", f"{package['name']} would have its version parsed as semver"


def test_no_destination_is_claimed_by_two_packages(packages: dict[str, dict[str, Any]]) -> None:
    """
    dpkg refuses to unpack a file another package owns, and the report arrives on a station
    in the middle of an upgrade.

    The one shared path is deliberate and stays legal: the app package drops a single .pth
    file inside the venv directory the deps package owns. dpkg tracks files rather than
    directories, so two packages inside one directory is fine as long as no file is in both.
    """
    claimed: dict[str, str] = {}
    for package in packages.values():
        for entry in package["contents"]:
            owner = claimed.get(entry["dst"])
            assert owner is None, f"{entry['dst']} is claimed by both {owner} and {package['name']}"
            claimed[entry["dst"]] = package["name"]


def test_every_source_comes_out_of_the_staged_tree(packages: dict[str, dict[str, Any]]) -> None:
    """
    A package holds what the builder put in a staging tree, and nothing else. That is what
    makes the contents list an allowlist rather than a hope, the property the tarball's
    RELEASE_PATHS was written to have.
    """
    for package in packages.values():
        for entry in package["contents"]:
            assert entry["src"].startswith(STAGING_VARIABLES), f"{entry['src']} is not staged by the builder"


def test_the_staged_path_mirrors_the_installed_path(packages: dict[str, dict[str, Any]]) -> None:
    """
    A staging tree is the filesystem it will become, so every src ends with its own dst.
    Reading a package then needs one rule rather than a mapping table.
    """
    for package in packages.values():
        for entry in package["contents"]:
            staged = re.sub(r"^\$\{STAGING_[A-Z]+\}", "", entry["src"])
            assert staged == entry["dst"], f"{entry['src']} is staged somewhere other than {entry['dst']}"


def test_only_the_two_intended_files_are_conffiles(packages: dict[str, dict[str, Any]]) -> None:
    configured = {
        entry["dst"]
        for package in packages.values()
        for entry in package["contents"]
        if str(entry.get("type", "")).startswith("config")
    }
    assert configured == EXPECTED_CONFIG_FILES


def test_the_sudoers_policy_ships_read_only_and_is_not_a_conffile(packages: dict[str, dict[str, Any]]) -> None:
    entries = [
        entry for entry in packages["backyardchirps"]["contents"] if entry["dst"] == "/etc/sudoers.d/backyardchirps"
    ]
    assert len(entries) == 1
    assert "config" not in str(entries[0].get("type", ""))
    # sudo ignores a file in sudoers.d that anyone but root can write, and says nothing.
    assert entries[0]["file_info"]["mode"] == 0o440


def test_the_maintainer_scripts_the_app_package_names_are_there(packages: dict[str, dict[str, Any]]) -> None:
    """
    nfpm's names on the left, the Debian ones on the right. The builder copies each one
    out of packaging/scripts/ into the staging tree on its way past, which is where the
    version gate gets written into preinst.
    """
    scripts = packages["backyardchirps"].get("scripts", {})
    assert set(scripts) == {"preinstall", "postinstall", "preremove", "postremove"}
    for path in scripts.values():
        name = path.replace("${SCRIPTS}/", "")
        assert (PACKAGING / "scripts" / name).exists(), f"{path} is named but not in the repository"


def test_the_app_package_depends_on_the_other_two(packages: dict[str, dict[str, Any]]) -> None:
    """
    Both are versioned, so a station cannot end up running new code against an old
    virtualenv or a taxonomy that predates the species it names.
    """
    depends = packages["backyardchirps"]["depends"]
    assert "backyardchirps-deps (>= ${DEPS_VERSION})" in depends
    assert "backyardchirps-species-data (>= ${DATA_VERSION})" in depends


def test_the_virtualenv_names_the_interpreter_it_was_built_against(packages: dict[str, dict[str, Any]]) -> None:
    """
    The venv is bound to one Python minor version: the .pth path, the shebangs and the
    bytecode all carry it. Depending on python3.13 is what makes the move to the next
    Debian loud instead of silent.
    """
    assert "python3.13" in packages["backyardchirps-deps"]["depends"]


def test_the_keyring_package_ships_the_key_and_the_source(packages: dict[str, dict[str, Any]]) -> None:
    """
    Two files, and they only work as a pair: the source names the keyring by absolute path
    in Signed-By, so shipping one without the other leaves apt reading a source it cannot
    verify.
    """
    destinations = {entry["dst"] for entry in packages["backyardchirps-archive-keyring"]["contents"]}
    assert "/usr/share/keyrings/backyardchirps-archive-keyring.gpg" in destinations
    assert "/etc/apt/sources.list.d/backyardchirps.sources" in destinations


def test_the_source_names_the_keyring_this_package_ships() -> None:
    """
    The path in Signed-By and the path the keyring installs to are written in two files, so
    a rename of one has to be a rename of both.
    """
    source = (PACKAGING / "apt" / "backyardchirps.sources").read_text(encoding="utf-8")
    keyring = load(NFPM_DIR / "backyardchirps-archive-keyring.yaml")
    shipped = [entry["dst"] for entry in keyring["contents"] if entry["dst"].startswith("/usr/share/keyrings/")]
    assert len(shipped) == 1
    assert f"Signed-By: {shipped[0]}" in source


def test_the_source_is_not_globally_trusted() -> None:
    """
    Signed-By scopes a key to one repository. A key in /etc/apt/trusted.gpg.d, or a source
    marked Trusted, would let it vouch for anything the machine reads.
    """
    source = (PACKAGING / "apt" / "backyardchirps.sources").read_text(encoding="utf-8")
    assert "trusted.gpg.d" not in source
    assert "Trusted:" not in source


def test_the_source_ships_pointing_at_stable() -> None:
    """
    stable is releases only. The deploy Pi follows main through a file no package owns, so
    that this one can be rewritten without moving it back.
    """
    source = (PACKAGING / "apt" / "backyardchirps.sources").read_text(encoding="utf-8")
    assert "Suites: stable" in source


def test_the_base_url_is_the_only_thing_the_build_fills_in() -> None:
    """
    Moving the repository to another host is meant to cost a DNS change, and this is what
    keeps that true: nothing else in the source file varies per build, so one variable in
    the publish job is the whole publish target.
    """
    source = (PACKAGING / "apt" / "backyardchirps.sources").read_text(encoding="utf-8")
    assert set(re.findall(r"\$\{([A-Z_]+)\}", source)) == {"APT_BASE_URL"}
